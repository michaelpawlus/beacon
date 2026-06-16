"""Unit tests for the AI-posture classifier (#46).

Posture splits ``ai_first_score`` into how a company *relates* to AI:
  • ai_native  — the product is AI (product_integration dominates)
  • ai_forward — company-wide adoption, no AI product (policy/mandate/leadership)
  • ai_curious — sparse/weak evidence (circle back)
"""

from beacon.db.connection import get_connection, init_db
from beacon.research.posture import (
    AI_CURIOUS,
    AI_FORWARD,
    AI_NATIVE,
    classify,
    classify_candidate,
    classify_company,
)

# ----- pure classify() -----

def test_no_evidence_is_curious():
    res = classify([], [], [])
    assert res.posture == AI_CURIOUS
    assert res.evidence_count == 0
    assert res.circle_back is True
    # A thin case must never read as a confident verdict.
    assert res.confidence <= 0.4


def test_product_integration_is_native():
    res = classify([("product_integration", 5), ("product_integration", 4)], [], [])
    assert res.posture == AI_NATIVE
    assert res.native_score > res.forward_score


def test_company_wide_adoption_is_forward():
    # No product signal — company policy + company-wide leadership + broad tools.
    res = classify(
        [("company_policy", 4), ("tool_mandate", 5), ("employee_report", 3)],
        ["company-wide"],
        ["required", "encouraged", "encouraged"],
    )
    assert res.posture == AI_FORWARD
    assert res.forward_score > res.native_score
    assert res.native_score == 0.0


def test_acceptance_forward_profile():
    """Issue #46 acceptance: company-wide mandate + tools + no AI product → forward."""
    res = classify(
        [("company_policy", 4)],
        ["company-wide"],
        ["encouraged", "encouraged"],
    )
    assert res.posture == AI_FORWARD


def test_heavy_adopter_with_token_product_stays_forward():
    """A single AI-feature mention shouldn't override overwhelming adoption."""
    res = classify(
        [("product_integration", 4)],  # native ≈ 5.3
        ["company-wide", "company-wide"],
        ["required", "required", "encouraged", "encouraged"],  # forward large
    )
    assert res.posture == AI_FORWARD


def test_ai_lab_with_internal_adoption_stays_native():
    """AI labs also mandate tools company-wide — that must not flip them."""
    res = classify(
        [("product_integration", 5), ("product_integration", 5), ("engineering_blog", 5)],
        ["company-wide"],
        ["required", "required"],
    )
    assert res.posture == AI_NATIVE


def test_weak_single_signal_is_curious():
    res = classify([("press_coverage", 1)], [], [])
    assert res.posture == AI_CURIOUS


def test_confidence_rises_with_evidence_volume():
    thin = classify([("company_policy", 4)], ["company-wide"], [])
    thick = classify(
        [("company_policy", 4), ("tool_mandate", 4), ("employee_report", 4)],
        ["company-wide", "engineering"],
        ["required", "encouraged"],
    )
    assert thick.confidence > thin.confidence


def test_unknown_signal_type_does_not_crash():
    res = classify([("some_future_type", 3)], [], [])
    assert res.posture in (AI_NATIVE, AI_FORWARD, AI_CURIOUS)


def test_none_strength_treated_as_neutral():
    res = classify([("product_integration", None)], [], [])
    # strength None → neutral (3) → native weight 3.0 → clears gate
    assert res.posture == AI_NATIVE


# ----- classify_candidate() -----

def test_classify_candidate_reads_forward_signals():
    signals = [
        {"signal_type": "company_policy", "signal_strength": 4},
        {"signal_type": "tool_mandate", "strength": 5},
    ]
    res = classify_candidate(signals)
    assert res.posture == AI_FORWARD


def test_classify_candidate_native():
    res = classify_candidate([{"signal_type": "product_integration", "signal_strength": 5}])
    assert res.posture == AI_NATIVE


def test_classify_candidate_empty():
    assert classify_candidate([]).posture == AI_CURIOUS
    assert classify_candidate(None).posture == AI_CURIOUS


# ----- classify_company() over the DB -----

def test_classify_company_end_to_end(tmp_path):
    init_db(tmp_path / "b.db")
    conn = get_connection(tmp_path / "b.db")
    cur = conn.execute("INSERT INTO companies (name) VALUES ('Acme Corp')")
    cid = cur.lastrowid
    conn.execute(
        "INSERT INTO ai_signals (company_id, signal_type, title, signal_strength) VALUES (?,?,?,?)",
        (cid, "company_policy", "Company-wide AI mandate", 4),
    )
    conn.execute(
        "INSERT INTO leadership_signals (company_id, leader_name, content, impact_level) VALUES (?,?,?,?)",
        (cid, "CEO", "AI is a baseline expectation", "company-wide"),
    )
    conn.execute(
        "INSERT INTO tools_adopted (company_id, tool_name, adoption_level) VALUES (?,?,?)",
        (cid, "ChatGPT Enterprise", "encouraged"),
    )
    conn.commit()
    res = classify_company(conn, cid)
    conn.close()
    assert res.posture == AI_FORWARD
    assert res.evidence_count == 3


def test_as_dict_shape():
    d = classify([("product_integration", 5)], [], []).as_dict()
    assert set(d) == {
        "ai_posture", "posture_confidence", "native_score",
        "forward_score", "evidence_count", "circle_back",
    }


# ----- migration backfill (#46): upgraded DBs must not hide NULL-posture rows -----

def test_backfill_posture_stamps_null_rows(tmp_path):
    import json

    from beacon.db.connection import _backfill_posture

    init_db(tmp_path / "b.db")
    conn = get_connection(tmp_path / "b.db")
    cid = conn.execute("INSERT INTO companies (name) VALUES ('Upgraded Co')").lastrowid
    conn.executemany(
        "INSERT INTO ai_signals (company_id, signal_type, title, signal_strength) VALUES (?,?,?,?)",
        [(cid, "company_policy", "mandate", 4), (cid, "tool_mandate", "rollout", 4)],
    )
    conn.execute(
        "INSERT INTO discovery_candidates (source, source_ref, name, signals_json) VALUES ('yaml','x','Cand', ?)",
        (json.dumps([{"signal_type": "product_integration", "signal_strength": 5}]),),
    )
    # Simulate the pre-#46 state: columns exist (migration added them) but NULL.
    conn.execute("UPDATE companies SET ai_posture = NULL, posture_confidence = NULL")
    conn.execute("UPDATE discovery_candidates SET ai_posture = NULL")
    conn.commit()

    _backfill_posture(conn)
    conn.commit()

    co = conn.execute("SELECT ai_posture, posture_confidence FROM companies WHERE id=?", (cid,)).fetchone()
    cand = conn.execute("SELECT ai_posture FROM discovery_candidates WHERE name='Cand'").fetchone()
    conn.close()
    assert co["ai_posture"] == "ai_forward"
    assert co["posture_confidence"] is not None
    assert cand["ai_posture"] == "ai_native"
