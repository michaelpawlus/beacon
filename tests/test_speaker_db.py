"""Tests for beacon.db.speaker — presentations and speaker profile operations."""

import json

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.db.speaker import (
    add_presentation,
    delete_presentation,
    get_presentation_by_id,
    get_presentations,
    get_speaker_profile,
    get_upcoming_presentations,
    set_bio,
    set_headshot,
    update_presentation,
    upsert_speaker_profile,
)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


def _insert_presentation(conn, **overrides):
    defaults = dict(
        title="AI in Higher Ed",
        abstract="How AI transforms advancement.",
        key_points=["Point A", "Point B"],
        event_name="DRIVE 2025",
        venue="Convention Center",
        date="2025-09-15",
        duration_minutes=45,
        audience="Advancement professionals",
        status="accepted",
        tags=["AI", "higher-ed"],
    )
    defaults.update(overrides)
    return add_presentation(conn, **defaults)


class TestAddPresentation:
    def test_returns_id(self, db):
        pres_id = add_presentation(db, "Test Talk")
        assert pres_id is not None
        assert pres_id > 0

    def test_stores_all_fields(self, db):
        pres_id = _insert_presentation(db)
        row = get_presentation_by_id(db, pres_id)
        assert row["title"] == "AI in Higher Ed"
        assert row["abstract"] == "How AI transforms advancement."
        assert row["event_name"] == "DRIVE 2025"
        assert row["venue"] == "Convention Center"
        assert row["date"] == "2025-09-15"
        assert row["duration_minutes"] == 45
        assert row["audience"] == "Advancement professionals"
        assert row["status"] == "accepted"

    def test_json_fields(self, db):
        pres_id = _insert_presentation(db)
        row = get_presentation_by_id(db, pres_id)
        kp = json.loads(row["key_points"])
        assert kp == ["Point A", "Point B"]
        tags = json.loads(row["tags"])
        assert "AI" in tags

    def test_default_status(self, db):
        pres_id = add_presentation(db, "Talk")
        row = get_presentation_by_id(db, pres_id)
        assert row["status"] == "planned"

    def test_co_presenters(self, db):
        pres_id = add_presentation(db, "Joint Talk", co_presenters=["Alice", "Bob"])
        row = get_presentation_by_id(db, pres_id)
        co = json.loads(row["co_presenters"])
        assert co == ["Alice", "Bob"]


class TestGetPresentations:
    def test_empty(self, db):
        result = get_presentations(db)
        assert result == []

    def test_returns_all(self, db):
        _insert_presentation(db, title="Talk 1")
        _insert_presentation(db, title="Talk 2")
        result = get_presentations(db)
        assert len(result) == 2

    def test_filter_by_status(self, db):
        _insert_presentation(db, title="Planned", status="planned")
        _insert_presentation(db, title="Delivered", status="delivered")
        _insert_presentation(db, title="Accepted", status="accepted")
        planned = get_presentations(db, status="planned")
        assert len(planned) == 1
        assert planned[0]["title"] == "Planned"

    def test_order_by_date_desc(self, db):
        _insert_presentation(db, title="Earlier", date="2025-01-01")
        _insert_presentation(db, title="Later", date="2025-12-01")
        result = get_presentations(db)
        assert result[0]["title"] == "Later"


class TestGetPresentationById:
    def test_found(self, db):
        pres_id = _insert_presentation(db)
        row = get_presentation_by_id(db, pres_id)
        assert row is not None
        assert row["id"] == pres_id

    def test_not_found(self, db):
        assert get_presentation_by_id(db, 999) is None


class TestGetUpcomingPresentations:
    def test_includes_future_accepted(self, db):
        _insert_presentation(db, title="Future Talk", date="2099-01-01", status="accepted")
        result = get_upcoming_presentations(db)
        assert len(result) == 1
        assert result[0]["title"] == "Future Talk"

    def test_includes_future_planned(self, db):
        _insert_presentation(db, title="Planned Talk", date="2099-01-01", status="planned")
        result = get_upcoming_presentations(db)
        assert len(result) == 1

    def test_excludes_past(self, db):
        _insert_presentation(db, title="Past Talk", date="2020-01-01", status="accepted")
        result = get_upcoming_presentations(db)
        assert len(result) == 0

    def test_excludes_delivered(self, db):
        _insert_presentation(db, title="Done Talk", date="2099-01-01", status="delivered")
        result = get_upcoming_presentations(db)
        assert len(result) == 0

    def test_order_by_date_asc(self, db):
        _insert_presentation(db, title="Later", date="2099-12-01", status="planned")
        _insert_presentation(db, title="Sooner", date="2099-01-01", status="planned")
        result = get_upcoming_presentations(db)
        assert result[0]["title"] == "Sooner"


class TestUpdatePresentation:
    def test_update_title(self, db):
        pres_id = _insert_presentation(db)
        assert update_presentation(db, pres_id, title="New Title")
        row = get_presentation_by_id(db, pres_id)
        assert row["title"] == "New Title"

    def test_update_json_field(self, db):
        pres_id = _insert_presentation(db)
        assert update_presentation(db, pres_id, tags=["new-tag"])
        row = get_presentation_by_id(db, pres_id)
        assert json.loads(row["tags"]) == ["new-tag"]

    def test_update_nonexistent(self, db):
        assert not update_presentation(db, 999, title="X")

    def test_empty_kwargs(self, db):
        pres_id = _insert_presentation(db)
        assert not update_presentation(db, pres_id)


class TestDeletePresentation:
    def test_delete_existing(self, db):
        pres_id = _insert_presentation(db)
        assert delete_presentation(db, pres_id)
        assert get_presentation_by_id(db, pres_id) is None

    def test_delete_nonexistent(self, db):
        assert not delete_presentation(db, 999)


class TestSpeakerProfile:
    def test_empty_profile(self, db):
        assert get_speaker_profile(db) is None

    def test_upsert_creates(self, db):
        upsert_speaker_profile(db, headshot_path="/img/me.jpg")
        row = get_speaker_profile(db)
        assert row is not None
        assert row["headshot_path"] == "/img/me.jpg"

    def test_upsert_updates(self, db):
        upsert_speaker_profile(db, headshot_path="/img/old.jpg")
        upsert_speaker_profile(db, headshot_path="/img/new.jpg")
        row = get_speaker_profile(db)
        assert row["headshot_path"] == "/img/new.jpg"

    def test_upsert_merges(self, db):
        upsert_speaker_profile(db, headshot_path="/img/me.jpg")
        upsert_speaker_profile(db, short_bio="A speaker.")
        row = get_speaker_profile(db)
        assert row["headshot_path"] == "/img/me.jpg"
        assert row["short_bio"] == "A speaker."

    def test_set_headshot(self, db):
        set_headshot(db, "/img/headshot.png")
        row = get_speaker_profile(db)
        assert row["headshot_path"] == "/img/headshot.png"

    def test_set_bio_short(self, db):
        set_bio(db, "Short bio here.")
        row = get_speaker_profile(db)
        assert row["short_bio"] == "Short bio here."
        assert row["bio_generated_at"] is not None

    def test_set_bio_with_long(self, db):
        set_bio(db, "Short.", long_bio="Long bio paragraph here.")
        row = get_speaker_profile(db)
        assert row["short_bio"] == "Short."
        assert row["long_bio"] == "Long bio paragraph here."
        assert row["bio_generated_at"] is not None

    def test_set_bio_on_existing_profile(self, db):
        set_headshot(db, "/img/me.jpg")
        set_bio(db, "Updated bio.")
        row = get_speaker_profile(db)
        assert row["headshot_path"] == "/img/me.jpg"
        assert row["short_bio"] == "Updated bio."


class TestStatusConstraint:
    def test_valid_statuses(self, db):
        for status in ("planned", "accepted", "delivered", "cancelled"):
            pres_id = add_presentation(db, f"Talk {status}", status=status)
            assert pres_id > 0

    def test_invalid_status(self, db):
        with pytest.raises(Exception):
            add_presentation(db, "Bad Talk", status="invalid_status")
