"""Tests for beacon.targets — aspirational role track (#43, WS3).

Covers the role_targets/role_fit_snapshots schema, fit computation +
time-series snapshots, horizon-weighted target gap analysis (and its sync
into skill_gaps), trajectory rendering, FDE dispatches, seeds, and the
`beacon target gaps --json` envelope.
"""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from beacon.cli import TARGET_GAPS_SCHEMA_VERSION, app
from beacon.db.connection import get_connection, init_db
from beacon.targets import (
    add_dispatch,
    add_target,
    analyze_target_gaps,
    compute_target_fit,
    dispatch_attribute_counts,
    extract_target_skills,
    get_target,
    get_trajectory,
    jd_vs_field,
    latest_snapshot_age_days,
    list_dispatches,
    list_targets,
    render_trajectory_markdown,
    seed_targets,
    snapshot_fit,
    sync_target_gaps,
    targets_needing_fit,
    update_target,
    wins_closing_gaps,
)

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


def _add_basic_target(conn, **overrides):
    defaults = {
        "title": "Forward Deployed Engineer",
        "horizon": "2y",
        "required_skills": ["Python", "Kubernetes", "LLMs"],
        "why": "tier jump",
    }
    defaults.update(overrides)
    return add_target(conn, **defaults)


def _add_skill(conn, name, proficiency="advanced"):
    conn.execute(
        "INSERT INTO skills (name, category, proficiency) VALUES (?, 'tool', ?)",
        (name, proficiency),
    )
    conn.commit()


def _add_win(conn, title, technologies):
    conn.execute(
        "INSERT INTO wins (title, technologies) VALUES (?, ?)",
        (title, json.dumps(technologies)),
    )
    conn.commit()


# ── schema / CRUD ───────────────────────────────────────────────────


class TestAddTarget:
    def test_returns_id(self, db):
        conn, _ = db
        assert _add_basic_target(conn) > 0

    def test_invalid_horizon_raises(self, db):
        conn, _ = db
        with pytest.raises(ValueError, match="Unknown horizon"):
            _add_basic_target(conn, horizon="5y")

    def test_extracts_skills_from_description(self, db):
        conn, _ = db
        tid = add_target(
            conn,
            title="FDE",
            description_snapshot="You will deploy Kubernetes and Python systems with RAG pipelines.",
        )
        target = get_target(conn, tid)
        skills = json.loads(target["required_skills"])
        assert "Kubernetes" in skills
        assert "Python" in skills

    def test_explicit_skills_canonicalized(self, db):
        # `--skill k8s` must store the canonical name so fit/gap comparisons
        # match a profile that has `Kubernetes` (Codex review, PR #51).
        conn, _ = db
        tid = add_target(conn, title="FDE", required_skills=["k8s", "Kubernetes", "py"])
        assert json.loads(get_target(conn, tid)["required_skills"]) == ["Kubernetes", "Python"]

    def test_alias_skill_matches_canonical_profile(self, db):
        conn, _ = db
        _add_skill(conn, "Kubernetes")
        tid = add_target(conn, title="FDE", required_skills=["k8s"])
        fit = compute_target_fit(conn, get_target(conn, tid))
        assert fit["matched"] == ["Kubernetes"]
        assert fit["missing"] == []

    def test_legacy_alias_rows_canonicalized_on_read(self, db):
        # Rows written before storage-side normalization still compare right.
        conn, _ = db
        tid = _add_basic_target(conn)
        conn.execute(
            "UPDATE role_targets SET required_skills = ? WHERE id = ?",
            (json.dumps(["k8s"]), tid),
        )
        conn.commit()
        from beacon.targets import required_skills_for

        assert required_skills_for(get_target(conn, tid)) == ["Kubernetes"]

    def test_explicit_skills_win_over_extraction(self, db):
        conn, _ = db
        tid = add_target(
            conn,
            title="FDE",
            description_snapshot="Python everywhere.",
            required_skills=["Rust"],
        )
        assert json.loads(get_target(conn, tid)["required_skills"]) == ["Rust"]


class TestListTargets:
    def test_filters_by_status(self, db):
        conn, _ = db
        _add_basic_target(conn)
        dropped = _add_basic_target(conn, title="Old target")
        update_target(conn, dropped, status="dropped")
        active = list_targets(conn, status="active")
        assert [t["title"] for t in active] == ["Forward Deployed Engineer"]
        assert len(list_targets(conn, status=None)) == 2

    def test_orders_by_horizon(self, db):
        conn, _ = db
        _add_basic_target(conn, title="Far", horizon="4y")
        _add_basic_target(conn, title="Near", horizon="1y")
        assert [t["title"] for t in list_targets(conn)] == ["Near", "Far"]

    def test_includes_latest_fit(self, db):
        conn, _ = db
        tid = _add_basic_target(conn)
        assert list_targets(conn)[0]["latest_fit"] is None
        snapshot_fit(conn, get_target(conn, tid))
        assert list_targets(conn)[0]["latest_fit"] is not None


class TestUpdateTarget:
    def test_invalid_status_raises(self, db):
        conn, _ = db
        tid = _add_basic_target(conn)
        with pytest.raises(ValueError, match="Unknown status"):
            update_target(conn, tid, status="paused")

    def test_not_found(self, db):
        conn, _ = db
        assert update_target(conn, 999, status="achieved") is False


# ── fit + snapshots ─────────────────────────────────────────────────


class TestComputeFit:
    def test_full_overlap_scores_high(self, db):
        conn, _ = db
        for s in ("Python", "Kubernetes", "LLMs"):
            _add_skill(conn, s)
        tid = _add_basic_target(conn)
        fit = compute_target_fit(conn, get_target(conn, tid))
        assert fit["sub_scores"]["skill_overlap"] == 10.0
        assert fit["missing"] == []
        assert fit["sub_scores"]["gap_momentum"] == 10.0

    def test_no_overlap_scores_low(self, db):
        conn, _ = db
        tid = _add_basic_target(conn)
        fit = compute_target_fit(conn, get_target(conn, tid))
        assert fit["sub_scores"]["skill_overlap"] == 0.0
        assert sorted(fit["missing"]) == ["Kubernetes", "LLMs", "Python"]

    def test_skill_aliases_match(self, db):
        conn, _ = db
        _add_skill(conn, "typescript")
        tid = _add_basic_target(conn, required_skills=["JavaScript"])
        fit = compute_target_fit(conn, get_target(conn, tid))
        assert fit["matched"] == ["JavaScript"]

    def test_win_evidence_feeds_evidence_depth(self, db):
        conn, _ = db
        tid = _add_basic_target(conn)
        before = compute_target_fit(conn, get_target(conn, tid))
        _add_win(conn, "Shipped k8s deploy", ["Kubernetes"])
        after = compute_target_fit(conn, get_target(conn, tid))
        assert after["sub_scores"]["evidence_depth"] > before["sub_scores"]["evidence_depth"]
        assert "Kubernetes" in after["evidence"]["win_evidence"]

    def test_gap_momentum_counts_learning(self, db):
        conn, _ = db
        conn.execute(
            "INSERT INTO skill_gaps (skill_name, status) VALUES ('Kubernetes', 'learning')"
        )
        conn.commit()
        tid = _add_basic_target(conn)
        fit = compute_target_fit(conn, get_target(conn, tid))
        assert fit["sub_scores"]["gap_momentum"] > 0
        assert "Kubernetes" in fit["evidence"]["gaps_in_motion"]


class TestSnapshots:
    def test_writes_row(self, db):
        conn, _ = db
        tid = _add_basic_target(conn)
        snapshot_fit(conn, get_target(conn, tid))
        rows = conn.execute("SELECT * FROM role_fit_snapshots").fetchall()
        assert len(rows) == 1
        assert json.loads(rows[0]["gaps_json"]) == ["Python", "Kubernetes", "LLMs"]

    def test_reports_delta_and_closed_gaps(self, db):
        conn, _ = db
        tid = _add_basic_target(conn)
        target = get_target(conn, tid)
        first = snapshot_fit(conn, target)
        assert "fit_delta" not in first
        _add_skill(conn, "Python")
        second = snapshot_fit(conn, target)
        assert second["fit_delta"] > 0
        assert second["gaps_closed_since_last"] == ["python"]

    def test_latest_snapshot_age(self, db):
        conn, _ = db
        assert latest_snapshot_age_days(conn) is None
        tid = _add_basic_target(conn)
        snapshot_fit(conn, get_target(conn, tid))
        assert latest_snapshot_age_days(conn) == 0

    def test_needing_fit_checks_per_target(self, db):
        # A fresh snapshot on one target must not mask a newly added target
        # that has never been baselined (Codex review, PR #51).
        conn, _ = db
        baselined = _add_basic_target(conn, title="Baselined")
        snapshot_fit(conn, get_target(conn, baselined))
        _add_basic_target(conn, title="New target")
        needing = targets_needing_fit(conn)
        assert [t["title"] for t in needing] == ["New target"]
        assert needing[0]["snapshot_age_days"] is None

    def test_needing_fit_ignores_inactive(self, db):
        conn, _ = db
        tid = _add_basic_target(conn, title="Dropped")
        update_target(conn, tid, status="dropped")
        assert targets_needing_fit(conn) == []


# ── target gaps ─────────────────────────────────────────────────────


class TestTargetGaps:
    def test_horizon_weighting(self, db):
        conn, _ = db
        _add_basic_target(conn, title="Near", horizon="1y", required_skills=["Kafka"])
        _add_basic_target(conn, title="Far", horizon="4y", required_skills=["Spark", "Kafka"])
        analysis = analyze_target_gaps(conn)
        by_name = {g["skill_name"]: g for g in analysis["gaps"]}
        assert by_name["Kafka"]["priority"] == 5  # 4 (1y) + 1 (4y)
        assert by_name["Spark"]["priority"] == 1
        assert analysis["gaps"][0]["skill_name"] == "Kafka"

    def test_profile_skills_excluded(self, db):
        conn, _ = db
        _add_skill(conn, "Python")
        _add_basic_target(conn)
        names = {g["skill_name"] for g in analyze_target_gaps(conn)["gaps"]}
        assert "Python" not in names
        assert "Kubernetes" in names

    def test_win_evidence_annotated(self, db):
        conn, _ = db
        _add_basic_target(conn)
        _add_win(conn, "Built k8s pipeline", ["Kubernetes"])
        by_name = {g["skill_name"]: g for g in analyze_target_gaps(conn)["gaps"]}
        assert by_name["Kubernetes"]["win_evidence_count"] == 1
        assert by_name["Kubernetes"]["example_wins"][0]["title"] == "Built k8s pipeline"

    def test_field_observed_from_dispatches(self, db):
        conn, _ = db
        _add_basic_target(conn)
        add_dispatch(conn, "Field report", attributes=["Kubernetes", "Customer Obsession"])
        by_name = {g["skill_name"]: g for g in analyze_target_gaps(conn)["gaps"]}
        assert by_name["Kubernetes"]["field_observed"] == 1

    def test_sync_upserts_skill_gaps(self, db):
        conn, _ = db
        _add_basic_target(conn)
        analysis = analyze_target_gaps(conn)
        result = sync_target_gaps(conn, analysis["gaps"])
        assert result["inserted"] == 3
        row = conn.execute("SELECT * FROM skill_gaps WHERE skill_name = 'Kubernetes'").fetchone()
        assert row["status"] == "open"
        examples = json.loads(row["example_jobs"])
        assert examples[0]["title"] == "Forward Deployed Engineer"

    def test_sync_preserves_status(self, db):
        conn, _ = db
        conn.execute("INSERT INTO skill_gaps (skill_name, status) VALUES ('Kubernetes', 'learning')")
        conn.commit()
        _add_basic_target(conn)
        sync_target_gaps(conn, analyze_target_gaps(conn)["gaps"])
        row = conn.execute("SELECT status FROM skill_gaps WHERE skill_name = 'Kubernetes'").fetchone()
        assert row["status"] == "learning"


class TestJdVsField:
    def test_diff(self, db):
        conn, _ = db
        _add_basic_target(conn, required_skills=["Python", "Kubernetes"])
        add_dispatch(conn, "Field report", attributes=["Kubernetes", "Customer Obsession"])
        diff = jd_vs_field(conn)
        assert diff["both"] == ["Kubernetes"]
        assert diff["jd_only"] == ["Python"]
        assert diff["field_only"] == ["Customer Obsession"]
        assert diff["dispatch_count"] == 1


# ── wins ↔ gaps ─────────────────────────────────────────────────────


class TestWinsClosingGaps:
    def test_links_wins_to_target_gaps(self, db):
        conn, _ = db
        _add_basic_target(conn)
        _add_win(conn, "Shipped LLM eval harness", ["LLMs", "Evals"])
        _add_win(conn, "Unrelated win", ["Excel"])
        hits = wins_closing_gaps(conn)
        assert len(hits) == 1
        assert hits[0]["gap_skills"] == ["LLMs"]

    def test_empty_without_targets(self, db):
        conn, _ = db
        _add_win(conn, "A win", ["Python"])
        assert wins_closing_gaps(conn) == []


# ── trajectory ──────────────────────────────────────────────────────


class TestTrajectory:
    def test_not_found(self, db):
        conn, _ = db
        assert get_trajectory(conn, 999) is None

    def test_deltas_track_gap_closure(self, db):
        conn, _ = db
        tid = _add_basic_target(conn)
        target = get_target(conn, tid)
        snapshot_fit(conn, target)
        _add_skill(conn, "Python")
        snapshot_fit(conn, target)
        traj = get_trajectory(conn, tid)
        assert len(traj["snapshots"]) == 2
        assert traj["deltas"][0]["gaps_closed"] == ["python"]
        assert traj["deltas"][0]["fit_delta"] > 0

    def test_markdown_render(self, db):
        conn, _ = db
        tid = _add_basic_target(
            conn, target_comp_min=200_000, target_comp_max=240_000, why="tier jump"
        )
        target = get_target(conn, tid)
        snapshot_fit(conn, target)
        _add_win(conn, "K8s rollout", ["Kubernetes"])
        snapshot_fit(conn, target)
        md = render_trajectory_markdown(get_trajectory(conn, tid))
        assert "# Target Trajectory — Forward Deployed Engineer" in md
        assert "$200,000–$240,000" in md
        assert "## Fit over time" in md
        assert "## What moved the number" in md
        assert "Win-backed skills (resume-ready)" in md

    def test_markdown_empty_state(self, db):
        conn, _ = db
        tid = _add_basic_target(conn)
        md = render_trajectory_markdown(get_trajectory(conn, tid))
        assert "No fit snapshots yet" in md


# ── dispatches ──────────────────────────────────────────────────────


class TestDispatches:
    def test_add_and_list(self, db):
        conn, _ = db
        did = add_dispatch(
            conn, "Reflections", url="https://example.com", author="A. Writer",
            author_role="FDE @ Palantir", attributes=["Ownership"],
        )
        assert did > 0
        dispatches = list_dispatches(conn)
        assert dispatches[0]["title"] == "Reflections"
        assert dispatches[0]["attributes"] == ["Ownership"]

    def test_filter_by_target(self, db):
        conn, _ = db
        tid = _add_basic_target(conn)
        add_dispatch(conn, "Linked", role_target_id=tid)
        add_dispatch(conn, "Unlinked")
        assert [d["title"] for d in list_dispatches(conn, role_target_id=tid)] == ["Linked"]

    def test_attribute_counts_dedupe_within_dispatch(self, db):
        conn, _ = db
        add_dispatch(conn, "One", attributes=["Ownership", "ownership"])
        add_dispatch(conn, "Two", attributes=["Ownership"])
        assert dispatch_attribute_counts(conn)["ownership"] == 2


# ── seeds ───────────────────────────────────────────────────────────


class TestSeeds:
    def test_seeds_targets_and_dispatch(self, db):
        conn, _ = db
        result = seed_targets(conn)
        assert len(result["inserted"]) == 4
        assert result["dispatches_inserted"] == 1
        titles = {t["title"] for t in result["inserted"]}
        assert any("Palantir" in t for t in titles)
        assert any("Anthropic" in t for t in titles)
        assert any("OpenAI" in t for t in titles)

    def test_idempotent(self, db):
        conn, _ = db
        seed_targets(conn)
        again = seed_targets(conn)
        assert again["inserted"] == []
        assert again["dispatches_inserted"] == 0
        assert len(again["skipped"]) == 4

    def test_links_company_when_present(self, db):
        conn, _ = db
        conn.execute("INSERT INTO companies (name, tier) VALUES ('Anthropic', 1)")
        conn.commit()
        seed_targets(conn)
        row = conn.execute(
            "SELECT t.company_id FROM role_targets t JOIN companies c ON t.company_id = c.id "
            "WHERE c.name = 'Anthropic'"
        ).fetchone()
        assert row is not None

    def test_horizons_span_tiers(self, db):
        conn, _ = db
        seed_targets(conn)
        horizons = {t["horizon"] for t in list_targets(conn)}
        assert "2y" in horizons  # Palantir tier
        assert "4y" in horizons  # frontier labs


# ── extraction ──────────────────────────────────────────────────────


class TestExtractSkills:
    def test_canonical_and_deduped(self):
        skills = extract_target_skills("Build with python and Python; deploy on kubernetes.")
        assert skills.count("Python") == 1
        assert "Kubernetes" in skills

    def test_empty_description(self):
        assert extract_target_skills("") == []


# ── CLI ─────────────────────────────────────────────────────────────


class TestCli:
    def test_seed_then_list(self, db):
        _, path = db
        result = _invoke(path, "target", "seed", "--json")
        assert result.exit_code == 0
        assert len(json.loads(result.stdout)["inserted"]) == 4

        result = _invoke(path, "target", "list", "--json")
        payload = json.loads(result.stdout)
        assert len(payload["targets"]) == 4
        assert payload["latest_snapshot_age_days"] is None

    def test_add_requires_title(self, db):
        _, path = db
        result = _invoke(path, "target", "add", "--json")
        assert result.exit_code == 1
        assert "title" in json.loads(result.stdout)["error"].lower()

    def test_add_from_job(self, db):
        conn, path = db
        conn.execute("INSERT INTO companies (name, tier) VALUES ('Acme', 1)")
        conn.execute(
            "INSERT INTO job_listings (company_id, title, description_text, archetype) "
            "VALUES (1, 'Staff FDE', 'Python and Kubernetes work.', 'solutions_fde')"
        )
        conn.commit()
        result = _invoke(path, "target", "add", "--from-job", "1", "--horizon", "2y", "--json")
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["title"] == "Staff FDE"
        assert "Python" in payload["required_skills"]

        conn2 = get_connection(path)
        row = conn2.execute("SELECT * FROM role_targets").fetchone()
        assert row["source_job_id"] == 1
        assert row["archetype"] == "solutions_fde"
        conn2.close()

    def test_fit_requires_id_or_all(self, db):
        _, path = db
        result = _invoke(path, "target", "fit", "--json")
        assert result.exit_code == 1

    def test_fit_all_writes_snapshots(self, db):
        conn, path = db
        seed_targets(conn)
        result = _invoke(path, "target", "fit", "--all", "--json")
        assert result.exit_code == 0
        snaps = json.loads(result.stdout)["snapshots"]
        assert len(snaps) == 4
        conn2 = get_connection(path)
        assert conn2.execute("SELECT COUNT(*) FROM role_fit_snapshots").fetchone()[0] == 4
        conn2.close()

    def test_gaps_envelope(self, db):
        conn, path = db
        seed_targets(conn)
        result = _invoke(path, "target", "gaps", "--json")
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["schema_version"] == TARGET_GAPS_SCHEMA_VERSION
        assert isinstance(payload["gaps"], list)
        assert payload["targets_analyzed"] == 4
        assert {"both", "jd_only", "field_only", "dispatch_count"} <= set(payload["jd_vs_field"].keys())
        gap = payload["gaps"][0]
        for key in ("skill_name", "category", "demand_count", "priority",
                    "example_targets", "field_observed", "win_evidence_count",
                    "example_wins", "status"):
            assert key in gap
        assert "synced" in payload

    def test_gaps_sync_feeds_gaps_list(self, db):
        conn, path = db
        seed_targets(conn)
        _invoke(path, "target", "gaps", "--json")
        result = _invoke(path, "gaps", "list", "--json")
        payload = json.loads(result.stdout)
        assert payload["schema_version"] == 1
        assert len(payload["gaps"]) > 0

    def test_gaps_no_sync(self, db):
        conn, path = db
        seed_targets(conn)
        result = _invoke(path, "target", "gaps", "--no-sync", "--json")
        assert "synced" not in json.loads(result.stdout)
        conn2 = get_connection(path)
        assert conn2.execute("SELECT COUNT(*) FROM skill_gaps").fetchone()[0] == 0
        conn2.close()

    def test_show_and_update(self, db):
        conn, path = db
        tid = _add_basic_target(conn)
        result = _invoke(path, "target", "show", str(tid), "--json")
        assert json.loads(result.stdout)["required_skills"] == ["Python", "Kubernetes", "LLMs"]

        result = _invoke(path, "target", "update", str(tid), "--status", "achieved", "--json")
        assert json.loads(result.stdout)["status"] == "achieved"

    def test_show_not_found(self, db):
        _, path = db
        result = _invoke(path, "target", "show", "999", "--json")
        assert result.exit_code == 2

    def test_trajectory_json(self, db):
        conn, path = db
        tid = _add_basic_target(conn)
        snapshot_fit(conn, get_target(conn, tid))
        result = _invoke(path, "target", "trajectory", str(tid), "--json")
        payload = json.loads(result.stdout)
        assert payload["title"] == "Forward Deployed Engineer"
        assert len(payload["snapshots"]) == 1
        assert "# Target Trajectory" in payload["markdown"]

    def test_dispatch_add_and_list(self, db):
        _, path = db
        result = _invoke(
            path, "target", "dispatch", "add", "Field notes",
            "--author", "Jane", "--attribute", "Ownership", "--json",
        )
        assert result.exit_code == 0
        result = _invoke(path, "target", "dispatch", "list", "--json")
        dispatches = json.loads(result.stdout)
        assert dispatches[0]["title"] == "Field notes"
        assert dispatches[0]["attributes"] == ["Ownership"]


# ── surfacing: dashboard + career review ────────────────────────────


class TestSurfacing:
    def test_dashboard_nudges_when_unseeded(self, db):
        conn, _ = db
        from beacon.dashboard import gather_dashboard_data

        data = gather_dashboard_data(conn)
        assert any("beacon target seed" in item for item in data.action_items)

    def test_dashboard_nudges_missing_baseline(self, db):
        conn, _ = db
        from beacon.dashboard import gather_dashboard_data

        _add_basic_target(conn)
        data = gather_dashboard_data(conn)
        assert any("beacon target fit --all" in item for item in data.action_items)
        assert any("Next target gap" in item for item in data.action_items)

    def test_dashboard_nudges_unbaselined_target_despite_fresh_snapshot(self, db):
        # Per-target freshness: one fresh snapshot must not suppress the
        # baseline nudge for a target added afterwards (Codex review, PR #51).
        conn, _ = db
        from beacon.dashboard import gather_dashboard_data

        baselined = _add_basic_target(conn, title="Baselined")
        snapshot_fit(conn, get_target(conn, baselined))
        _add_basic_target(conn, title="New target")
        data = gather_dashboard_data(conn)
        assert any("no fit baseline" in item and "New target" in item for item in data.action_items)

    def test_dashboard_lists_targets(self, db):
        conn, _ = db
        from beacon.dashboard import gather_dashboard_data

        _add_basic_target(conn)
        data = gather_dashboard_data(conn)
        assert data.targets[0]["title"] == "Forward Deployed Engineer"

    def test_review_includes_target_section(self, db):
        conn, _ = db
        from beacon.career import list_wins, render_review_markdown, target_progress

        _add_basic_target(conn)
        _add_win(conn, "Shipped LLM evals", ["LLMs"])
        progress = target_progress(conn, since="90d")
        md = render_review_markdown(list_wins(conn), "window", targets=progress)
        assert "## Aspirational Targets — wins vs gaps" in md
        assert "Shipped LLM evals" in md
        assert "Next gaps to prioritize" in md
        assert "beacon target fit --all" in md  # no snapshot yet → stale nudge

    def test_review_renders_target_section_with_zero_wins(self, db):
        # A zero-win window is exactly when the target nudges matter most —
        # the no-wins branch must not short-circuit them (Codex review, PR #51).
        conn, _ = db
        from beacon.career import render_review_markdown, target_progress

        _add_basic_target(conn)
        progress = target_progress(conn, since="90d")
        md = render_review_markdown([], "window", targets=progress)
        assert "No wins logged" in md
        assert "## Aspirational Targets — wins vs gaps" in md
        assert "Next gaps to prioritize" in md
        assert "beacon target fit --all" in md

    def test_review_skips_section_without_targets(self, db):
        conn, _ = db
        from beacon.career import list_wins, render_review_markdown, target_progress

        progress = target_progress(conn, since="90d")
        md = render_review_markdown(list_wins(conn), "window", targets=progress)
        assert "Aspirational Targets" not in md
