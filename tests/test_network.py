"""Tests for beacon.network — networking events and contacts."""

import json
from unittest.mock import patch

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.network import (
    add_contact,
    add_event,
    get_contact,
    get_contact_events,
    get_event,
    get_event_contacts,
    link_contact_event,
    list_contacts,
    list_events,
    prep_event,
    update_contact,
    update_event,
    update_link,
)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _add_sample_event(conn, **overrides):
    defaults = {
        "name": "AI Tinkerers Columbus",
        "organizer": "AI Tinkerers",
        "event_type": "meetup",
        "url": "https://columbus.aitinkerers.org",
        "location": "Columbus, OH",
        "date": "2026-04-15",
        "status": "upcoming",
        "tags": ["ai", "networking"],
    }
    defaults.update(overrides)
    return add_event(conn, **defaults)


def _add_sample_contact(conn, **overrides):
    defaults = {
        "name": "Jane Smith",
        "title": "ML Engineer",
        "company": "Acme AI",
        "bio": "Works on LLM infra",
        "interests": ["agents", "mlops"],
        "priority": 3,
    }
    defaults.update(overrides)
    return add_contact(conn, **defaults)


def _insert_company(conn):
    conn.execute(
        "INSERT INTO companies (name, ai_first_score, tier) VALUES (?, ?, ?)",
        ("Acme AI", 8.5, 1),
    )
    conn.commit()
    return conn.execute("SELECT id FROM companies WHERE name = 'Acme AI'").fetchone()["id"]


# ── add_event ──────────────────────────────────────────────────────


class TestAddEvent:
    def test_returns_id(self, db):
        eid = add_event(db, name="Test Meetup")
        assert eid is not None
        assert eid > 0

    def test_stores_all_fields(self, db):
        eid = _add_sample_event(db)
        row = db.execute("SELECT * FROM network_events WHERE id = ?", (eid,)).fetchone()
        assert row["name"] == "AI Tinkerers Columbus"
        assert row["organizer"] == "AI Tinkerers"
        assert row["event_type"] == "meetup"
        assert row["location"] == "Columbus, OH"
        assert row["status"] == "upcoming"
        assert json.loads(row["tags"]) == ["ai", "networking"]

    def test_defaults(self, db):
        eid = add_event(db, name="Simple Event")
        row = db.execute("SELECT * FROM network_events WHERE id = ?", (eid,)).fetchone()
        assert row["event_type"] == "meetup"
        assert row["status"] == "upcoming"


# ── list_events ────────────────────────────────────────────────────


class TestListEvents:
    def test_returns_all(self, db):
        _add_sample_event(db, name="A")
        _add_sample_event(db, name="B")
        result = list_events(db)
        assert len(result) == 2

    def test_filter_status(self, db):
        _add_sample_event(db, name="Past", status="attended")
        _add_sample_event(db, name="Future", status="upcoming")
        result = list_events(db, status="upcoming")
        assert len(result) == 1
        assert result[0]["name"] == "Future"

    def test_filter_event_type(self, db):
        _add_sample_event(db, name="Meetup", event_type="meetup")
        _add_sample_event(db, name="Conf", event_type="conference")
        result = list_events(db, event_type="conference")
        assert len(result) == 1
        assert result[0]["name"] == "Conf"

    def test_filter_since(self, db):
        _add_sample_event(db, name="Old", date="2024-01-01")
        _add_sample_event(db, name="New", date="2026-06-01")
        result = list_events(db, since="2026-01-01")
        assert len(result) == 1
        assert result[0]["name"] == "New"

    def test_search(self, db):
        _add_sample_event(db, name="AI Tinkerers", organizer="AI Tinkerers")
        _add_sample_event(db, name="Python Meetup", organizer="PyColumbus")
        result = list_events(db, search="Tinkerers")
        assert len(result) == 1
        assert result[0]["name"] == "AI Tinkerers"

    def test_limit(self, db):
        for i in range(5):
            _add_sample_event(db, name=f"Event {i}")
        result = list_events(db, limit=3)
        assert len(result) == 3

    def test_composable_filters(self, db):
        _add_sample_event(db, name="Match", status="upcoming", event_type="meetup", date="2026-06-01")
        _add_sample_event(db, name="WrongStatus", status="attended", event_type="meetup", date="2026-06-01")
        _add_sample_event(db, name="WrongType", status="upcoming", event_type="conference", date="2026-06-01")
        result = list_events(db, status="upcoming", event_type="meetup", since="2026-01-01")
        assert len(result) == 1
        assert result[0]["name"] == "Match"


# ── get_event ──────────────────────────────────────────────────────


class TestGetEvent:
    def test_valid_id(self, db):
        eid = _add_sample_event(db)
        event = get_event(db, eid)
        assert event is not None
        assert event["name"] == "AI Tinkerers Columbus"

    def test_invalid_id(self, db):
        assert get_event(db, 9999) is None


# ── update_event ───────────────────────────────────────────────────


class TestUpdateEvent:
    def test_update_status(self, db):
        eid = _add_sample_event(db)
        ok = update_event(db, eid, status="attended")
        assert ok is True
        event = get_event(db, eid)
        assert event["status"] == "attended"

    def test_update_notes(self, db):
        eid = _add_sample_event(db)
        update_event(db, eid, notes="Great event!")
        event = get_event(db, eid)
        assert event["notes"] == "Great event!"

    def test_update_not_found(self, db):
        ok = update_event(db, 9999, status="attended")
        assert ok is False

    def test_update_no_fields(self, db):
        eid = _add_sample_event(db)
        ok = update_event(db, eid)
        assert ok is False


# ── add_contact ────────────────────────────────────────────────────


class TestAddContact:
    def test_returns_id(self, db):
        cid = add_contact(db, name="Bob")
        assert cid is not None
        assert cid > 0

    def test_stores_all_fields(self, db):
        cid = _add_sample_contact(db)
        row = db.execute("SELECT * FROM network_contacts WHERE id = ?", (cid,)).fetchone()
        assert row["name"] == "Jane Smith"
        assert row["title"] == "ML Engineer"
        assert row["company"] == "Acme AI"
        assert row["priority"] == 3
        assert json.loads(row["interests"]) == ["agents", "mlops"]

    def test_company_id_link(self, db):
        company_id = _insert_company(db)
        cid = add_contact(db, name="Alice", company="Acme AI", company_id=company_id)
        row = db.execute("SELECT * FROM network_contacts WHERE id = ?", (cid,)).fetchone()
        assert row["company_id"] == company_id


# ── list_contacts ──────────────────────────────────────────────────


class TestListContacts:
    def test_returns_all(self, db):
        _add_sample_contact(db, name="A")
        _add_sample_contact(db, name="B")
        result = list_contacts(db)
        assert len(result) == 2

    def test_filter_company(self, db):
        _add_sample_contact(db, name="At Acme", company="Acme AI")
        _add_sample_contact(db, name="At Other", company="Other Corp")
        result = list_contacts(db, company="Acme")
        assert len(result) == 1
        assert result[0]["name"] == "At Acme"

    def test_filter_event(self, db):
        eid = _add_sample_event(db)
        cid1 = _add_sample_contact(db, name="Linked")
        _add_sample_contact(db, name="Not Linked")
        link_contact_event(db, cid1, eid)
        result = list_contacts(db, event_id=eid)
        assert len(result) == 1
        assert result[0]["name"] == "Linked"

    def test_filter_min_priority(self, db):
        _add_sample_contact(db, name="Low", priority=1)
        _add_sample_contact(db, name="High", priority=5)
        result = list_contacts(db, min_priority=4)
        assert len(result) == 1
        assert result[0]["name"] == "High"

    def test_search(self, db):
        _add_sample_contact(db, name="Jane Smith", bio="ML infra")
        _add_sample_contact(db, name="Bob Jones", bio="Frontend dev")
        result = list_contacts(db, search="ML infra")
        assert len(result) == 1
        assert result[0]["name"] == "Jane Smith"

    def test_limit(self, db):
        for i in range(5):
            _add_sample_contact(db, name=f"Contact {i}")
        result = list_contacts(db, limit=3)
        assert len(result) == 3


# ── get_contact ────────────────────────────────────────────────────


class TestGetContact:
    def test_valid_id(self, db):
        cid = _add_sample_contact(db)
        contact = get_contact(db, cid)
        assert contact is not None
        assert contact["name"] == "Jane Smith"

    def test_invalid_id(self, db):
        assert get_contact(db, 9999) is None


# ── update_contact ─────────────────────────────────────────────────


class TestUpdateContact:
    def test_update_title(self, db):
        cid = _add_sample_contact(db)
        ok = update_contact(db, cid, title="Senior ML Engineer")
        assert ok is True
        contact = get_contact(db, cid)
        assert contact["title"] == "Senior ML Engineer"

    def test_update_priority(self, db):
        cid = _add_sample_contact(db, priority=1)
        update_contact(db, cid, priority=5)
        contact = get_contact(db, cid)
        assert contact["priority"] == 5

    def test_update_interests(self, db):
        cid = _add_sample_contact(db, interests=["old"])
        update_contact(db, cid, interests=["new", "updated"])
        contact = get_contact(db, cid)
        assert json.loads(contact["interests"]) == ["new", "updated"]

    def test_update_not_found(self, db):
        ok = update_contact(db, 9999, title="X")
        assert ok is False

    def test_update_no_fields(self, db):
        cid = _add_sample_contact(db)
        ok = update_contact(db, cid)
        assert ok is False


# ── link_contact_event ─────────────────────────────────────────────


class TestLinkContactEvent:
    def test_creates_link(self, db):
        eid = _add_sample_event(db)
        cid = _add_sample_contact(db)
        lid = link_contact_event(db, cid, eid)
        assert lid > 0

    def test_with_details(self, db):
        eid = _add_sample_event(db)
        cid = _add_sample_contact(db)
        link_contact_event(db, cid, eid, topics_discussed="LLM agents", follow_up="Send paper link")
        row = db.execute(
            "SELECT * FROM network_contact_events WHERE contact_id = ? AND event_id = ?",
            (cid, eid),
        ).fetchone()
        assert row["topics_discussed"] == "LLM agents"
        assert row["follow_up"] == "Send paper link"

    def test_upsert(self, db):
        eid = _add_sample_event(db)
        cid = _add_sample_contact(db)
        link_contact_event(db, cid, eid, topics_discussed="first")
        link_contact_event(db, cid, eid, topics_discussed="updated")
        rows = db.execute(
            "SELECT * FROM network_contact_events WHERE contact_id = ? AND event_id = ?",
            (cid, eid),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["topics_discussed"] == "updated"


# ── update_link ────────────────────────────────────────────────────


class TestUpdateLink:
    def test_mark_followed_up(self, db):
        eid = _add_sample_event(db)
        cid = _add_sample_contact(db)
        link_contact_event(db, cid, eid, follow_up="Send email")
        ok = update_link(db, cid, eid, followed_up=True)
        assert ok is True
        row = db.execute(
            "SELECT * FROM network_contact_events WHERE contact_id = ? AND event_id = ?",
            (cid, eid),
        ).fetchone()
        assert row["followed_up"] == 1

    def test_update_not_found(self, db):
        ok = update_link(db, 9999, 9999, followed_up=True)
        assert ok is False


# ── get_event_contacts ─────────────────────────────────────────────


class TestGetEventContacts:
    def test_returns_linked_contacts(self, db):
        eid = _add_sample_event(db)
        cid1 = _add_sample_contact(db, name="Alice")
        cid2 = _add_sample_contact(db, name="Bob")
        link_contact_event(db, cid1, eid, topics_discussed="AI")
        link_contact_event(db, cid2, eid)
        contacts = get_event_contacts(db, eid)
        assert len(contacts) == 2
        names = {c["name"] for c in contacts}
        assert names == {"Alice", "Bob"}

    def test_includes_link_fields(self, db):
        eid = _add_sample_event(db)
        cid = _add_sample_contact(db)
        link_contact_event(db, cid, eid, topics_discussed="Agents", follow_up="Coffee chat")
        contacts = get_event_contacts(db, eid)
        assert contacts[0]["topics_discussed"] == "Agents"
        assert contacts[0]["follow_up"] == "Coffee chat"

    def test_empty_event(self, db):
        eid = _add_sample_event(db)
        assert get_event_contacts(db, eid) == []


# ── get_contact_events ─────────────────────────────────────────────


class TestGetContactEvents:
    def test_returns_linked_events(self, db):
        eid1 = _add_sample_event(db, name="Event A", date="2026-04-01")
        eid2 = _add_sample_event(db, name="Event B", date="2026-05-01")
        cid = _add_sample_contact(db)
        link_contact_event(db, cid, eid1)
        link_contact_event(db, cid, eid2)
        events = get_contact_events(db, cid)
        assert len(events) == 2
        assert events[0]["name"] == "Event B"  # newer first

    def test_no_events(self, db):
        cid = _add_sample_contact(db)
        assert get_contact_events(db, cid) == []


# ── prep_event ─────────────────────────────────────────────────────


class TestPrepEvent:
    def test_basic_prep(self, db):
        eid = _add_sample_event(db)
        cid = _add_sample_contact(db, name="Alice")
        link_contact_event(db, cid, eid)
        result = prep_event(db, eid)
        assert result is not None
        assert result["event"]["name"] == "AI Tinkerers Columbus"
        assert result["total_contacts"] == 1
        assert result["beacon_matches"] == 0

    def test_beacon_cross_reference(self, db):
        company_id = _insert_company(db)
        eid = _add_sample_event(db)
        cid = _add_sample_contact(db, company="Acme AI", company_id=company_id)
        link_contact_event(db, cid, eid)
        result = prep_event(db, eid)
        assert result["beacon_matches"] == 1
        assert result["contacts"][0]["beacon_company"]["ai_first_score"] == 8.5

    def test_beacon_fuzzy_match(self, db):
        _insert_company(db)
        eid = _add_sample_event(db)
        cid = _add_sample_contact(db, company="Acme AI")  # no company_id, but name matches
        link_contact_event(db, cid, eid)
        result = prep_event(db, eid)
        assert result["beacon_matches"] == 1

    def test_not_found(self, db):
        assert prep_event(db, 9999) is None

    def test_sorting_beacon_first(self, db):
        company_id = _insert_company(db)
        eid = _add_sample_event(db)
        cid1 = _add_sample_contact(db, name="No Match", company="Unknown Corp", priority=5)
        cid2 = _add_sample_contact(db, name="Beacon Match", company="Acme AI", company_id=company_id, priority=1)
        link_contact_event(db, cid1, eid)
        link_contact_event(db, cid2, eid)
        result = prep_event(db, eid)
        assert result["contacts"][0]["name"] == "Beacon Match"


# ── CLI integration ────────────────────────────────────────────────


class TestNetworkCLI:
    def test_add_event_json(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, [
                "network", "add-event", "Test Meetup",
                "--organizer", "AI Group",
                "--type", "meetup",
                "--date", "2026-05-01",
                "--json",
            ])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["id"] > 0
            assert data["name"] == "Test Meetup"

    def test_events_json(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        _add_sample_event(db, name="Listed Event")

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, ["network", "events", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert len(data) >= 1

    def test_event_show_json(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        eid = _add_sample_event(db)
        cid = _add_sample_contact(db)
        link_contact_event(db, cid, eid)

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, ["network", "event", str(eid), "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["name"] == "AI Tinkerers Columbus"
            assert len(data["contacts"]) == 1

    def test_event_not_found(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, ["network", "event", "9999", "--json"])
            assert result.exit_code == 2

    def test_add_contact_json(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, [
                "network", "add-contact", "Alice Johnson",
                "--title", "Data Scientist",
                "--company", "SomeCompany",
                "--priority", "4",
                "--json",
            ])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["id"] > 0
            assert data["name"] == "Alice Johnson"

    def test_add_contact_auto_matches_beacon_company(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        _insert_company(db)

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, [
                "network", "add-contact", "Bob",
                "--company", "Acme AI",
                "--json",
            ])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert "beacon_company_id" in data

    def test_contacts_json(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        _add_sample_contact(db, name="Listed Contact")

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, ["network", "contacts", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert len(data) >= 1

    def test_contact_show_json(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        cid = _add_sample_contact(db)

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, ["network", "contact", str(cid), "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["name"] == "Jane Smith"

    def test_contact_not_found(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, ["network", "contact", "9999", "--json"])
            assert result.exit_code == 2

    def test_link_json(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        eid = _add_sample_event(db)
        cid = _add_sample_contact(db)

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, [
                "network", "link", str(cid), str(eid),
                "--topics", "AI agents",
                "--json",
            ])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["contact_id"] == cid
            assert data["event_id"] == eid

    def test_prep_json(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        eid = _add_sample_event(db)
        cid = _add_sample_contact(db)
        link_contact_event(db, cid, eid)

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, ["network", "prep", str(eid), "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["total_contacts"] == 1
            assert data["event"]["name"] == "AI Tinkerers Columbus"

    def test_prep_not_found(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, ["network", "prep", "9999", "--json"])
            assert result.exit_code == 2

    def test_add_contact_with_event(self, db):
        from typer.testing import CliRunner

        from beacon.cli import app

        eid = _add_sample_event(db)

        # CLI closes conn, so we need a fresh one for verification
        db_path = db.execute("PRAGMA database_list").fetchone()[2]

        with patch("beacon.cli.get_connection", return_value=db):
            runner = CliRunner()
            result = runner.invoke(app, [
                "network", "add-contact", "Alice",
                "--event", str(eid),
                "--json",
            ])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["linked_event_id"] == eid

        # Verify link was created using a fresh connection
        verify_conn = get_connection(db_path)
        contacts = get_event_contacts(verify_conn, eid)
        verify_conn.close()
        assert len(contacts) == 1
