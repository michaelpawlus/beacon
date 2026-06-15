"""Tests for the FDE success guide (beacon career guide, #45)."""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from beacon.career import add_win
from beacon.cli import app
from beacon.db.connection import get_connection, init_db
from beacon.db.profile import add_skill
from beacon.market import build_market_snapshot, persist_snapshot
from beacon.materials.success_guide import (
    build_guide,
    compute_strengths,
    high_signal_media,
    recommend_focus,
    render_guide_markdown,
)
from beacon.targets import add_target

runner = CliRunner()


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn, db_path
    conn.close()


def _invoke(db_path, *args):
    with patch("beacon.cli.get_connection") as mock:
        mock.side_effect = lambda *a, **k: get_connection(db_path)
        return runner.invoke(app, list(args))


def _add_media(conn, title, *, rating=None, shareable=False, why=None, tags=None):
    conn.execute(
        """INSERT INTO media_log (title, source_type, rating, team_shareable, why_it_matters, tags)
           VALUES (?, 'article', ?, ?, ?, ?)""",
        (title, rating, 1 if shareable else 0, why, json.dumps(tags) if tags else None),
    )
    conn.commit()


# ── Strengths ────────────────────────────────────────────────────────


class TestComputeStrengths:
    def test_empty_db_yields_no_strengths(self, db):
        conn, _ = db
        assert compute_strengths(conn, []) == []

    def test_advanced_skill_is_a_strength(self, db):
        conn, _ = db
        add_skill(conn, "Python", category="language", proficiency="advanced")
        add_skill(conn, "Bash", category="tool", proficiency="beginner")
        strengths = compute_strengths(conn, [])
        names = {s["skill"] for s in strengths}
        assert "Python" in names
        assert "Bash" not in names  # beginner is not a strength

    def test_win_backed_skill_sorts_first(self, db):
        conn, _ = db
        add_skill(conn, "Python", proficiency="advanced")
        add_win(conn, "Shipped pipeline", technologies=["Kafka", "Kafka-extra"])
        add_win(conn, "Shipped again", technologies=["Kafka"])
        strengths = compute_strengths(conn, _wins(conn))
        # Kafka has 2 wins → it sorts ahead of the proficiency-only Python.
        assert strengths[0]["skill"].lower() == "kafka"
        assert strengths[0]["win_evidence_count"] == 2

    def test_win_backed_unlisted_skill_flagged(self, db):
        conn, _ = db
        add_win(conn, "Built evals harness", technologies=["evals"])
        strengths = compute_strengths(conn, _wins(conn))
        evals = next(s for s in strengths if s["skill"] == "evals")
        assert evals["unlisted"] is True
        assert evals["example_win"] == "Built evals harness"

    def test_win_alias_matches_canonical_skill(self, db):
        # A win tagged `k8s` must credit the profile's `Kubernetes`, not be
        # mis-flagged as an unlisted skill to add (Codex P2 #r3410532984).
        conn, _ = db
        add_skill(conn, "Kubernetes", proficiency="intermediate")
        add_win(conn, "Migrated to k8s", technologies=["k8s"])
        strengths = compute_strengths(conn, _wins(conn))
        kube = next(s for s in strengths if s["skill"] == "Kubernetes")
        assert kube["win_evidence_count"] == 1
        assert all(s["skill"].lower() != "k8s" for s in strengths)

    def test_unlisted_win_skill_shown_canonical(self, db):
        conn, _ = db
        add_win(conn, "Shipped LLM feature", technologies=["llm"])
        strengths = compute_strengths(conn, _wins(conn))
        # Surfaced in canonical form (LLMs), not the raw alias.
        assert any(s["skill"] == "LLMs" and s.get("unlisted") for s in strengths)


# ── High-signal media ────────────────────────────────────────────────


class TestHighSignalMedia:
    def test_low_signal_excluded(self, db):
        conn, _ = db
        _add_media(conn, "Meh post", rating=2)
        assert high_signal_media(conn) == []

    def test_rating_or_shareable_or_why_included(self, db):
        conn, _ = db
        _add_media(conn, "Five star", rating=5)
        _add_media(conn, "Shareable", shareable=True)
        _add_media(conn, "Matters", why="team needs this")
        titles = {m["title"] for m in high_signal_media(conn)}
        assert titles == {"Five star", "Shareable", "Matters"}

    def test_on_thesis_sorts_first(self, db):
        conn, _ = db
        _add_media(conn, "Generic 5star", rating=5)
        _add_media(conn, "FDE adoption", rating=4, tags=["adoption"])
        items = high_signal_media(conn)
        assert items[0]["title"] == "FDE adoption"
        assert items[0]["on_thesis"] is True


# ── Recommendations heuristic ────────────────────────────────────────


class TestRecommendFocus:
    def test_empty_nudges_to_log_wins(self):
        recs = recommend_focus({"diffusion": 0, "delivery": 0}, [], None, [])
        assert any("win add" in r for r in recs)

    def test_delivery_skew_flagged(self):
        mix = {"diffusion": 1, "delivery": 5}
        recs = recommend_focus(mix, [], None, [])
        assert any("skews delivery" in r for r in recs)

    def test_market_rising_gap_is_top_signal(self):
        mix = {"diffusion": 2, "delivery": 2}
        gaps = [{"skill_name": "evals", "demand_count": 2, "priority": 7}]
        snapshot = {"diff_vs_previous": {"skills_rising": [{"skill": "evals"}], "skills_added": []}}
        recs = recommend_focus(mix, gaps, snapshot, [])
        assert any("evals" in r and "rising" in r for r in recs)

    def test_win_evidence_prompts_resume_add(self):
        mix = {"diffusion": 2, "delivery": 1}
        gaps = [{"skill_name": "Kubernetes", "demand_count": 1, "priority": 3,
                 "win_evidence_count": 2}]
        recs = recommend_focus(mix, gaps, None, [])
        assert any("resume" in r and "Kubernetes" in r for r in recs)

    def test_capped_at_four(self):
        mix = {"diffusion": 1, "delivery": 9}
        gaps = [
            {"skill_name": "a", "demand_count": 1, "priority": 9, "win_evidence_count": 1},
            {"skill_name": "b", "demand_count": 1, "priority": 8},
        ]
        snapshot = {"diff_vs_previous": {
            "skills_rising": [{"skill": "a"}, {"skill": "b"}], "skills_added": []}}
        recs = recommend_focus(mix, gaps, snapshot, [])
        assert len(recs) <= 4


# ── Assembly + rendering ─────────────────────────────────────────────


class TestBuildGuide:
    def test_empty_db_renders_all_sections(self, db):
        conn, _ = db
        guide = build_guide(conn)
        md = render_guide_markdown(guide)
        # All seven section headers present even with an empty DB.
        for header in [
            "## 1. Thesis",
            "## 2. This quarter's win mix",
            "## 3. Strengths",
            "## 4. Open target gaps",
            "## 5. Market direction",
            "## 6. Recommended focus",
            "## 7. Reading & sharing queue",
        ]:
            assert header in md
        assert guide["market_stale"] is True  # no snapshot → stale

    def test_populated_guide(self, db):
        conn, _ = db
        add_skill(conn, "Python", proficiency="expert")
        add_win(conn, "Drove team adoption", category="adoption", technologies=["Python"])
        add_target(conn, title="Forward Deployed Engineer", horizon="2y",
                   required_skills=["Kubernetes", "Evals"])
        persist_snapshot(conn, build_market_snapshot(conn, "solutions_fde", web=False))

        guide = build_guide(conn)
        assert guide["win_count"] == 1
        assert guide["win_mix"]["diffusion"] == 1
        assert guide["targets_analyzed"] == 1
        assert any(g["skill_name"].lower() == "kubernetes" for g in guide["gaps"])
        assert guide["market_snapshot"] is not None
        assert len(guide["strengths"]) >= 1

        md = render_guide_markdown(guide)
        assert "Python" in md
        assert "Forward Deployed" in guide["family_label"]

    def test_staleness_uses_selected_family_snapshot(self, db):
        # A fresh snapshot for a *different* family must not mask a months-old
        # one for the selected family (Codex P2 #r3410532981).
        conn, _ = db
        persist_snapshot(conn, build_market_snapshot(conn, "solutions_fde", web=False))
        # Age the solutions_fde snapshot well past the 90-day threshold.
        conn.execute(
            "UPDATE role_market_snapshots SET captured_at = '2026-01-01T00:00:00Z' "
            "WHERE archetype = 'solutions_fde'"
        )
        conn.commit()
        # A brand-new agentic snapshot (newest row across the whole table).
        persist_snapshot(conn, build_market_snapshot(conn, "agentic", web=False))

        guide = build_guide(conn, family_key="solutions_fde")
        assert guide["market_age_days"] is not None and guide["market_age_days"] > 90
        assert guide["market_stale"] is True

    def test_windowed_only_snapshot_is_used(self, db):
        # A family whose only snapshot was captured with --since-days N must
        # still render a market section, not "No market snapshot yet"
        # (Codex P2 #r3410545622).
        conn, _ = db
        persist_snapshot(
            conn, build_market_snapshot(conn, "solutions_fde", web=False, since_days=30)
        )
        guide = build_guide(conn, family_key="solutions_fde")
        assert guide["market_snapshot"] is not None
        assert guide["market_snapshot"]["since_days"] == 30


# ── CLI wiring ───────────────────────────────────────────────────────


class TestGuideCLI:
    def test_guide_json(self, db):
        conn, db_path = db
        add_win(conn, "Win one", category="delivery")
        result = _invoke(db_path, "career", "guide", "--json")
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["win_count"] == 1
        assert "recommendations" in payload
        assert "markdown" in payload

    def test_guide_markdown_to_stdout(self, db):
        conn, db_path = db
        result = _invoke(db_path, "career", "guide")
        assert result.exit_code == 0
        assert "# FDE Success Guide" in result.stdout

    def test_bad_archetype_exits_1(self, db):
        conn, db_path = db
        result = _invoke(db_path, "career", "guide", "--archetype", "nonsense", "--json")
        assert result.exit_code == 1
        assert json.loads(result.stdout)["code"] == 1

    def test_refresh_syncs_gaps(self, db):
        conn, db_path = db
        add_target(conn, title="FDE", horizon="2y", required_skills=["Ray"])
        result = _invoke(db_path, "career", "guide", "--refresh", "--json")
        assert result.exit_code == 0
        # The synced gap should now live in skill_gaps.
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM skill_gaps WHERE LOWER(skill_name) = 'ray'"
        ).fetchone()
        assert row["n"] == 1


def _wins(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM wins ORDER BY id").fetchall()]
