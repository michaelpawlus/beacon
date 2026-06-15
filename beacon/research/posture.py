"""Derive an AI *posture* for a company from the signal mix beacon already stores.

Issue #46: ``ai_first_score`` conflates two very different ways a company can
relate to AI, so an *AI-forward* employer (strong company-wide adoption, but no
AI product) never surfaced next to the *AI-native* labs. Posture splits them
apart along a three-point spectrum:

- ``ai_native``  — the product *is* AI; product-side signals dominate
  (``product_integration``, AI in the mission). The classic beacon target.
- ``ai_forward`` — not an AI-product company, but AI is adopted company-wide:
  ``leadership_signals.impact_level = 'company-wide'``, ``ai_signals`` of type
  ``company_policy`` / ``tool_mandate`` / ``employee_report``, and broad
  ``tools_adopted``. (The posture that made beacon miss the user's own employer.)
- ``ai_curious`` — sparse or weak signals; one story isn't a case yet, but it's
  a reason to circle back to the company occasionally.

The classifier is deterministic and inspectable — weighted sums over the signal
mix, no ML — so it can be *tuned by editing the weight tables below*. That's the
"attributes for fine-tuning later" hook the issue asks for.

Design rule (the discriminator): a company that ships AI products carries
``product_integration`` evidence, and that is treated as near-decisive. So
``native_score`` is built *only* from product-side signals; once it clears
``PRODUCT_GATE`` the company is ``ai_native`` even if it also mandates AI tools
internally. ``ai_forward`` is therefore reserved for companies with real
adoption evidence but little/no product-side AI.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass

AI_NATIVE = "ai_native"
AI_FORWARD = "ai_forward"
AI_CURIOUS = "ai_curious"
VALID_POSTURES = (AI_NATIVE, AI_FORWARD, AI_CURIOUS)

# ai_signals.signal_type -> (native_weight, forward_weight).
# product_integration is the strongest "the product IS AI" tell; company_policy
# / tool_mandate / employee_report are the company-wide-adoption tells. The
# ambiguous middle (blogs, talks, press) leans gently both ways.
SIGNAL_POSTURE_WEIGHTS: dict[str, tuple[float, float]] = {
    "product_integration": (3.0, 0.0),
    "github_activity": (1.5, 0.2),
    "engineering_blog": (0.9, 0.6),
    "conference_talk": (0.5, 0.5),
    "press_coverage": (0.6, 0.4),
    "leadership_statement": (0.4, 0.9),
    "job_posting_language": (0.3, 0.8),
    "employee_report": (0.0, 2.0),
    "company_policy": (0.0, 3.0),
    "tool_mandate": (0.0, 3.0),
}
# Fallback for unknown / future signal types — slightly forward-leaning since
# unknown signals are more often adoption chatter than a product claim.
_DEFAULT_SIGNAL_WEIGHT = (0.3, 0.4)

# leadership_signals.impact_level -> forward_weight. A company-wide mandate is
# the canonical ai_forward tell; personal enthusiasm barely moves the needle.
IMPACT_FORWARD_WEIGHTS: dict[str, float] = {
    "company-wide": 3.0,
    "engineering": 1.2,
    "team": 0.5,
    "personal": 0.1,
}

# tools_adopted.adoption_level -> forward_weight. Broad, mandated tool adoption
# is itself an AI-forward signal.
ADOPTION_FORWARD_WEIGHTS: dict[str, float] = {
    "required": 2.0,
    "encouraged": 1.5,
    "allowed": 0.7,
    "exploring": 0.3,
    "rumored": 0.1,
}

# Product-side evidence must clear this for the company to ship AI → ai_native.
PRODUCT_GATE = 3.0
# ...and be at least this fraction of the adoption (forward) score. This keeps a
# token "we added an AI feature" mention from overriding a company whose
# evidence is overwhelmingly company-wide *adoption* (e.g. Klarna, Shopify) —
# those stay ai_forward.
NATIVE_DOMINANCE = 0.6
# Below this dominant score, evidence is too thin/weak to call → ai_curious.
CURIOUS_THRESHOLD = 3.0
# "One story isn't enough." Building the AI-forward case for an older company is
# cumulative — a single adoption story is a reason to *circle back*, not a
# verdict — so ai_forward also requires at least this many pieces of evidence.
# (Product evidence is decisive on its own, so this gate applies to forward only.)
FORWARD_MIN_EVIDENCE = 2
# Strength 3 is "neutral"; the stored 1–5 strength scales each signal's weight.
_NEUTRAL_STRENGTH = 3.0


@dataclass
class PostureResult:
    """Outcome of a posture classification."""

    posture: str
    confidence: float
    native_score: float
    forward_score: float
    evidence_count: int

    @property
    def circle_back(self) -> bool:
        """True when the case is thin — a reason to revisit, not a verdict."""
        return self.posture == AI_CURIOUS

    def as_dict(self) -> dict:
        return {
            "ai_posture": self.posture,
            "posture_confidence": self.confidence,
            "native_score": round(self.native_score, 2),
            "forward_score": round(self.forward_score, 2),
            "evidence_count": self.evidence_count,
            "circle_back": self.circle_back,
        }


def _strength_factor(strength: float | int | None) -> float:
    """Scale a signal's contribution by its 1–5 strength (3 = neutral = 1.0x)."""
    try:
        s = float(strength) if strength is not None else _NEUTRAL_STRENGTH
    except (TypeError, ValueError):
        s = _NEUTRAL_STRENGTH
    return max(s, 0.0) / _NEUTRAL_STRENGTH


def classify(
    ai_signals: Iterable[tuple[str, float | int | None]],
    leadership_impacts: Iterable[str],
    tool_adoptions: Iterable[str],
) -> PostureResult:
    """Classify posture from already-fetched evidence.

    Args:
        ai_signals: ``(signal_type, signal_strength)`` pairs.
        leadership_impacts: ``impact_level`` values from ``leadership_signals``.
        tool_adoptions: ``adoption_level`` values from ``tools_adopted``.
    """
    native = 0.0
    forward = 0.0
    count = 0

    for stype, strength in ai_signals:
        count += 1
        nw, fw = SIGNAL_POSTURE_WEIGHTS.get(stype, _DEFAULT_SIGNAL_WEIGHT)
        factor = _strength_factor(strength)
        native += nw * factor
        forward += fw * factor

    for impact in leadership_impacts:
        count += 1
        forward += IMPACT_FORWARD_WEIGHTS.get(impact, 0.5)

    for adoption in tool_adoptions:
        count += 1
        forward += ADOPTION_FORWARD_WEIGHTS.get(adoption, 0.5)

    posture = _decide(native, forward, count)
    confidence = _confidence(posture, native, forward, count)
    return PostureResult(posture, confidence, native, forward, count)


def _decide(native: float, forward: float, count: int) -> str:
    """Priority rule: product-side evidence is decisive for ai_native.

    A company that ships AI products (``native`` clears ``PRODUCT_GATE`` *and*
    holds its own against the adoption score) is ``ai_native`` even when it also
    mandates AI tools internally — AI labs obviously have company-wide adoption
    too, and that must not flip them. But a heavy *adopter* with one token
    product mention (native well below ``NATIVE_DOMINANCE`` × forward) stays
    ``ai_forward``. The ``ai_forward`` call additionally requires accumulated
    evidence (``FORWARD_MIN_EVIDENCE``) — one adoption story is a circle-back
    cue, not a verdict. Everything thinner is ``ai_curious``.
    """
    if native >= PRODUCT_GATE and native >= forward * NATIVE_DOMINANCE:
        return AI_NATIVE
    if forward >= CURIOUS_THRESHOLD and count >= FORWARD_MIN_EVIDENCE:
        return AI_FORWARD
    return AI_CURIOUS


def _confidence(posture: str, native: float, forward: float, count: int) -> float:
    """Blend evidence volume with how strongly the deciding score clears its bar.

    ``ai_curious`` is deliberately capped low — a thin case should read as
    "circle back", never as a confident verdict.
    """
    volume = min(count / 6.0, 1.0)
    if posture == AI_CURIOUS:
        return round(0.2 + 0.2 * volume, 2)

    dominant = native if posture == AI_NATIVE else forward
    strength = min(dominant / 8.0, 1.0)  # how decisively the case is made
    return round(min(0.97, 0.35 + 0.40 * volume + 0.22 * strength), 2)


def classify_company(conn: sqlite3.Connection, company_id: int) -> PostureResult:
    """Classify a tracked company from its rows across the evidence tables."""
    ai_signals = [
        (r["signal_type"], r["signal_strength"])
        for r in conn.execute(
            "SELECT signal_type, signal_strength FROM ai_signals WHERE company_id = ?",
            (company_id,),
        ).fetchall()
    ]
    impacts = [
        r["impact_level"]
        for r in conn.execute(
            "SELECT impact_level FROM leadership_signals WHERE company_id = ?",
            (company_id,),
        ).fetchall()
        if r["impact_level"]
    ]
    adoptions = [
        r["adoption_level"]
        for r in conn.execute(
            "SELECT adoption_level FROM tools_adopted WHERE company_id = ?",
            (company_id,),
        ).fetchall()
        if r["adoption_level"]
    ]
    return classify(ai_signals, impacts, adoptions)


def classify_candidate(signals: Iterable[dict]) -> PostureResult:
    """Classify a discovery candidate from its raw ``signals`` list of dicts.

    Candidates carry only ``ai_signals``-shaped evidence (no leadership/tools
    tables yet), so adoption posture must be read from the signal types alone
    (``company_policy`` / ``tool_mandate`` / ``leadership_statement`` etc.).
    """
    pairs = [
        (
            (s.get("signal_type") if isinstance(s, dict) else None),
            (s.get("signal_strength") or s.get("strength") if isinstance(s, dict) else None),
        )
        for s in (signals or [])
    ]
    pairs = [(t, st) for t, st in pairs if t]
    return classify(pairs, [], [])
