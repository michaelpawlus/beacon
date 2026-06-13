"""Tests for beacon.market — role-market radar (#44, WS4).

Covers the role-family title taxonomy (titles that mean "roughly the same job"),
the deterministic internal sweep (headcount, salary, skill + seniority mix), the
recurring-role basket, the quarter-over-quarter diff (skills rising/falling/
added/removed + comp/headcount deltas), snapshot persistence + re-hydration, the
graceful web-radar degradation, and the `beacon career market` CLI surface.
"""

import json
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from beacon.cli import app
from beacon.db.connection import get_connection, init_db
from beacon.market import (
    build_basket,
    build_market_snapshot,
    diff_snapshots,
    external_radar,
    family_for_title,
    get_family,
    latest_snapshot,
    list_families,
    listing_in_family,
    listing_skills,
    market_snapshot_age_days,
    persist_snapshot,
    render_market_markdown,
    salary_stats,
    sample_listings,
    seniority_mix,
    skill_frequencies,
)
from beacon.targets import add_target

runner = CliRunner()

TODAY = date(2026, 6, 13)


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


def _add_company(conn, name):
    cur = conn.execute("INSERT INTO companies (name, tier) VALUES (?, 4)", (name,))
    conn.commit()
    return cur.lastrowid


def _add_listing(conn, company_id, title, *, description="", archetype=None,
                 salary=None, days_ago=1, status="active"):
    highlights = {}
    if salary:
        highlights = {"salary_min": salary[0], "salary_max": salary[1],
                      "salary_raw": f"${salary[0]}-${salary[1]}"}
    seen = (TODAY - timedelta(days=days_ago)).isoformat()
    cur = conn.execute(
        """INSERT INTO job_listings
           (company_id, title, description_text, archetype, highlights,
            status, date_first_seen, date_posted)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (company_id, title, description, archetype,
         json.dumps(highlights) if highlights else None, status, seen, seen),
    )
    conn.commit()
    return cur.lastrowid


# ── Title taxonomy ──────────────────────────────────────────────────


class TestFamilyForTitle:
    def test_users_actual_title_maps_to_fde(self):
        # The whole point of requirement #4: the user's own title aggregates.
        assert family_for_title("Forward Deployed AI Solutions Lead") == "solutions_fde"

    @pytest.mark.parametrize("title", [
        "Forward Deployed Engineer",
        "Forward-Deployed Software Engineer",
        "Solutions Architect",
        "Solutions Engineer",
        "Applied AI Engineer",
        "Deployment Strategist",
        "Customer Engineer",
    ])
    def test_equivalent_titles_collapse(self, title):
        assert family_for_title(title) == "solutions_fde"

    def test_unrelated_title_returns_none(self):
        assert family_for_title("Senior Accountant") is None

    def test_empty(self):
        assert family_for_title(None) is None
        assert family_for_title("") is None

    def test_get_family_default_is_fde(self):
        assert get_family(None).key == "solutions_fde"

    def test_get_family_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown role family"):
            get_family("bogus")

    def test_list_families(self):
        keys = {f["key"] for f in list_families()}
        assert "solutions_fde" in keys


class TestListingInFamily:
    def test_by_archetype(self, db):
        conn, _ = db
        cid = _add_company(conn, "Acme")
        lid = _add_listing(conn, cid, "Mystery Role", archetype="solutions_fde")
        row = conn.execute("SELECT * FROM job_listings WHERE id = ?", (lid,)).fetchone()
        assert listing_in_family(row, get_family("solutions_fde"))

    def test_by_title_when_no_archetype(self, db):
        conn, _ = db
        cid = _add_company(conn, "Acme")
        lid = _add_listing(conn, cid, "Forward Deployed Engineer", archetype=None)
        row = conn.execute("SELECT * FROM job_listings WHERE id = ?", (lid,)).fetchone()
        assert listing_in_family(row, get_family("solutions_fde"))

    def test_stored_archetype_is_authoritative(self, db):
        # "Applied AI Engineer" is an alias of BOTH agentic and solutions_fde.
        # A listing already classified `agentic` must NOT leak into solutions_fde
        # via the title fallback (that would double-count it across families).
        conn, _ = db
        cid = _add_company(conn, "Acme")
        lid = _add_listing(conn, cid, "Applied AI Engineer", archetype="agentic")
        row = conn.execute("SELECT * FROM job_listings WHERE id = ?", (lid,)).fetchone()
        assert listing_in_family(row, get_family("agentic"))
        assert not listing_in_family(row, get_family("solutions_fde"))

    def test_classified_listing_not_double_counted_in_sweep(self, db):
        conn, _ = db
        cid = _add_company(conn, "Acme")
        _add_listing(conn, cid, "Applied AI Engineer", archetype="agentic")
        assert sample_listings(conn, get_family("solutions_fde")) == []
        assert len(sample_listings(conn, get_family("agentic"))) == 1


# ── Internal sweep ──────────────────────────────────────────────────


class TestSampleListings:
    def test_filters_to_family_and_active(self, db):
        conn, _ = db
        cid = _add_company(conn, "Acme")
        _add_listing(conn, cid, "Forward Deployed Engineer")
        _add_listing(conn, cid, "Solutions Architect")
        _add_listing(conn, cid, "Data Scientist")  # different family
        _add_listing(conn, cid, "FDE (closed)", status="closed")  # excluded: not active
        got = sample_listings(conn, get_family("solutions_fde"))
        titles = {row["title"] for row in got}
        assert titles == {"Forward Deployed Engineer", "Solutions Architect"}

    def test_since_days_window(self, db):
        conn, _ = db
        cid = _add_company(conn, "Acme")
        _add_listing(conn, cid, "Forward Deployed Engineer", days_ago=5)
        _add_listing(conn, cid, "Solutions Engineer", days_ago=200)
        recent = sample_listings(conn, get_family("solutions_fde"),
                                 since_days=30, today=TODAY)
        assert len(recent) == 1
        assert recent[0]["title"] == "Forward Deployed Engineer"


class TestSkillFrequencies:
    def test_counts_per_listing_once_and_normalizes(self, db):
        conn, _ = db
        cid = _add_company(conn, "Acme")
        _add_listing(conn, cid, "FDE",
                     description="We use Python, Kubernetes (k8s) and LLMs heavily.")
        _add_listing(conn, cid, "Solutions Engineer",
                     description="Python and RAG pipelines and LLM systems.")
        listings = sample_listings(conn, get_family("solutions_fde"))
        freqs = {s["skill"]: s["count"] for s in skill_frequencies(listings)}
        assert freqs["Python"] == 2
        # k8s normalizes to Kubernetes, LLM/LLMs collapse to one per listing
        assert freqs["Kubernetes"] == 1
        assert freqs["LLMs"] == 2

    def test_listing_skills_dedupes_within_listing(self):
        skills = listing_skills({
            "title": "FDE",
            "description_text": "LLM and LLMs and large language model everywhere",
            "highlights": json.dumps({"ai_tools": ["LLMs"], "key_requirements": []}),
        })
        # all collapse to a single canonical LLMs
        assert "LLMs" in skills


class TestSeniorityAndSalary:
    def test_seniority_mix(self, db):
        conn, _ = db
        cid = _add_company(conn, "Acme")
        _add_listing(conn, cid, "Senior Forward Deployed Engineer")
        _add_listing(conn, cid, "Staff Solutions Architect")
        _add_listing(conn, cid, "Forward Deployed Engineer")  # unspecified
        listings = sample_listings(conn, get_family("solutions_fde"))
        mix = seniority_mix(listings)
        assert mix.get("senior") == 1
        assert mix.get("staff") == 1
        assert mix.get("unspecified") == 1

    def test_salary_stats_averages_disclosed(self, db):
        conn, _ = db
        cid = _add_company(conn, "Acme")
        _add_listing(conn, cid, "FDE", salary=(180000, 220000))
        _add_listing(conn, cid, "Solutions Engineer", salary=(200000, 260000))
        _add_listing(conn, cid, "Solutions Architect")  # no salary
        listings = sample_listings(conn, get_family("solutions_fde"))
        stats = salary_stats(listings)
        assert stats["with_salary"] == 2
        assert stats["avg_comp_min"] == 190000
        assert stats["avg_comp_max"] == 240000


# ── Basket ──────────────────────────────────────────────────────────


class TestBasket:
    def test_basket_from_active_targets_in_family(self, db):
        conn, _ = db
        pal = _add_company(conn, "Palantir")
        add_target(conn, title="Forward Deployed Engineer", company_id=pal,
                   archetype="solutions_fde", horizon="2y",
                   target_comp_min=190000, target_comp_max=240000,
                   required_skills=["Python"])
        add_target(conn, title="Data Scientist", archetype="ml_ds", horizon="2y",
                   target_comp_min=150000, target_comp_max=180000,
                   required_skills=["Python"])
        basket = build_basket(conn, get_family("solutions_fde"))
        assert basket["count"] == 1
        assert basket["avg_comp_min"] == 190000
        assert basket["entries"][0]["company"] == "Palantir"

    def test_basket_honors_target_archetype_over_title(self, db):
        # An `agentic` target titled "Applied AI Engineer" (an alias of both
        # agentic and solutions_fde) must land only in the agentic basket.
        conn, _ = db
        add_target(conn, title="Applied AI Engineer", archetype="agentic",
                   horizon="2y", target_comp_min=200000, target_comp_max=250000,
                   required_skills=["Python"])
        assert build_basket(conn, get_family("solutions_fde"))["count"] == 0
        assert build_basket(conn, get_family("agentic"))["count"] == 1

    def test_basket_enriches_with_live_listing_salary(self, db):
        conn, _ = db
        pal = _add_company(conn, "Palantir")
        add_target(conn, title="Forward Deployed Engineer", company_id=pal,
                   archetype="solutions_fde", horizon="2y",
                   target_comp_min=190000, target_comp_max=240000,
                   required_skills=["Python"])
        _add_listing(conn, pal, "Forward Deployed Engineer", salary=(210000, 250000))
        basket = build_basket(conn, get_family("solutions_fde"))
        entry = basket["entries"][0]
        assert entry["live_listings"] == 1
        assert entry["live_salary"]["avg_comp_min"] == 210000


# ── Diff ────────────────────────────────────────────────────────────


def _payload(top_skills, sampled=0, avg_min=None, avg_max=None,
             basket_min=None, basket_max=None):
    return {
        "listings": {"sampled": sampled, "avg_comp_min": avg_min,
                     "avg_comp_max": avg_max, "top_skills": top_skills},
        "basket": {"avg_comp_min": basket_min, "avg_comp_max": basket_max},
        "captured_at": "2026-03-01T00:00:00Z",
    }


class TestDiff:
    def test_none_on_first_run(self):
        assert diff_snapshots(_payload([]), None) is None

    def test_rising_falling_added_removed(self):
        prev = _payload([{"skill": "Python", "count": 5},
                         {"skill": "SQL", "count": 4},
                         {"skill": "Spark", "count": 2}])
        cur = _payload([{"skill": "Python", "count": 8},   # rising
                        {"skill": "SQL", "count": 1},       # falling
                        {"skill": "RAG", "count": 3}])       # added; Spark removed
        diff = diff_snapshots(cur, prev)
        assert [s["skill"] for s in diff["skills_rising"]] == ["Python"]
        assert diff["skills_rising"][0]["delta"] == 3
        assert [s["skill"] for s in diff["skills_falling"]] == ["SQL"]
        assert diff["skills_added"] == ["RAG"]
        assert diff["skills_removed"] == ["Spark"]

    def test_headcount_and_comp_deltas(self):
        prev = _payload([], sampled=10, avg_min=180000, avg_max=220000,
                        basket_min=200000, basket_max=240000)
        cur = _payload([], sampled=14, avg_min=190000, avg_max=235000,
                       basket_min=210000, basket_max=250000)
        diff = diff_snapshots(cur, prev)
        assert diff["listings_delta"] == 4
        assert diff["avg_comp_min_delta"] == 10000
        assert diff["avg_comp_max_delta"] == 15000
        assert diff["basket_avg_comp_max_delta"] == 10000


# ── External radar (graceful) ───────────────────────────────────────


class TestExternalRadar:
    def test_injected_search_fn_parsed(self):
        def fake(family):
            return {
                "direction": "growing",
                "direction_rationale": "more postings",
                "trends": [{"term": "Agent evals", "summary": "hot", "movement": "rising"}],
                "comp_signals": [{"source": "Levels", "range": "$200k-$240k", "url": "u"}],
            }
        out = external_radar(get_family("solutions_fde"), search_fn=fake)
        assert out["direction"] == "growing"
        assert out["trends"][0]["term"] == "Agent evals"
        assert out["comp_signals"][0]["range"] == "$200k-$240k"

    def test_bad_direction_nulled(self):
        out = external_radar(get_family("solutions_fde"),
                             search_fn=lambda f: {"direction": "exploding"})
        assert out["direction"] is None

    def test_build_degrades_when_web_raises(self, db):
        conn, _ = db
        def boom(family):
            raise RuntimeError("ANTHROPIC_API_KEY unset")
        payload = build_market_snapshot(conn, "solutions_fde", web=True, search_fn=boom)
        assert any("web radar skipped" in w for w in payload["warnings"])
        assert payload["trends"] == []

    def test_build_no_web(self, db):
        conn, _ = db
        payload = build_market_snapshot(conn, "solutions_fde", web=False)
        assert payload["web_enabled"] is False
        assert payload["warnings"] == []


# ── Snapshot persistence + diff over time ───────────────────────────


class TestPersistence:
    def test_persist_and_rehydrate(self, db):
        conn, _ = db
        cid = _add_company(conn, "Acme")
        _add_listing(conn, cid, "FDE", description="Python and LLMs", salary=(180000, 220000))
        payload = build_market_snapshot(conn, "solutions_fde", web=False)
        sid = persist_snapshot(conn, payload)
        assert sid > 0
        latest = latest_snapshot(conn, "solutions_fde")
        assert latest["listings"]["sampled"] == 1
        assert latest["listings"]["avg_comp_min"] == 180000

    def test_second_snapshot_diffs_against_first(self, db):
        conn, _ = db
        cid = _add_company(conn, "Acme")
        _add_listing(conn, cid, "FDE", description="Python")
        first = build_market_snapshot(conn, "solutions_fde", web=False)
        persist_snapshot(conn, first)
        assert first["diff_vs_previous"] is None
        assert first["category_direction"] == "unknown"

        # A new listing appears with a new skill.
        _add_listing(conn, cid, "Solutions Engineer", description="Python and RAG")
        second = build_market_snapshot(conn, "solutions_fde", web=False)
        diff = second["diff_vs_previous"]
        assert diff is not None
        assert diff["listings_delta"] == 1
        assert "RAG" in diff["skills_added"]
        assert second["category_direction"] == "growing"

    def test_snapshot_age(self, db):
        conn, _ = db
        assert market_snapshot_age_days(conn) is None
        payload = build_market_snapshot(conn, "solutions_fde", web=False)
        persist_snapshot(conn, payload)
        assert market_snapshot_age_days(conn) == 0


class TestDashboardNudge:
    def test_market_baseline_nudge_surfaces_with_no_targets(self, db):
        # Fresh user, no role_targets and no market snapshot: the market
        # baseline reminder must still appear (it is independent of targets).
        conn, _ = db
        from beacon.dashboard import _generate_action_items

        items = _generate_action_items(conn)
        assert any("beacon career market" in it for it in items)

    def test_market_nudge_clears_after_snapshot(self, db):
        conn, _ = db
        from beacon.dashboard import _generate_action_items

        persist_snapshot(conn, build_market_snapshot(conn, "solutions_fde", web=False))
        items = _generate_action_items(conn)
        assert not any("role-market snapshot" in it.lower() for it in items)


# ── Rendering ───────────────────────────────────────────────────────


class TestRender:
    def test_markdown_has_sections(self, db):
        conn, _ = db
        cid = _add_company(conn, "Acme")
        _add_listing(conn, cid, "FDE", description="Python and LLMs", salary=(180000, 220000))
        payload = build_market_snapshot(conn, "solutions_fde", web=False)
        md = render_market_markdown(payload)
        assert "# Role-Market Radar" in md
        assert "## Category pulse" in md
        assert "## Compensation" in md
        assert "## The basket" in md
        assert "## Skill mix" in md


# ── CLI ─────────────────────────────────────────────────────────────


class TestCLI:
    def test_market_json(self, db):
        conn, db_path = db
        cid = _add_company(conn, "Acme")
        _add_listing(conn, cid, "Forward Deployed Engineer",
                     description="Python and LLMs", salary=(180000, 220000))
        conn.close()
        result = _invoke(db_path, "career", "market", "--no-web", "--json")
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["family"] == "solutions_fde"
        assert payload["listings"]["sampled"] == 1
        assert payload["snapshot_id"] is not None

    def test_market_dry_run_does_not_persist(self, db):
        conn, db_path = db
        _add_company(conn, "Acme")
        conn.close()
        result = _invoke(db_path, "career", "market", "--no-web", "--dry-run", "--json")
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["snapshot_id"] is None
        conn2 = get_connection(db_path)
        count = conn2.execute("SELECT COUNT(*) AS c FROM role_market_snapshots").fetchone()["c"]
        conn2.close()
        assert count == 0

    def test_market_list_families(self, db):
        _, db_path = db
        result = _invoke(db_path, "career", "market", "--list", "--json")
        assert result.exit_code == 0
        keys = {f["key"] for f in json.loads(result.stdout)}
        assert "solutions_fde" in keys

    def test_market_unknown_family(self, db):
        _, db_path = db
        result = _invoke(db_path, "career", "market", "--archetype", "bogus", "--json")
        assert result.exit_code == 1
        assert json.loads(result.stdout)["code"] == 1
