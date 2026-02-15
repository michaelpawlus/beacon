"""Tests for beacon.db.content — content CRUD operations."""

import json

import pytest

from beacon.db.connection import get_connection, init_db
from beacon.db.content import (
    add_accomplishment,
    add_calendar_entry,
    add_content_draft,
    delete_accomplishment,
    delete_calendar_entry,
    delete_content_draft,
    get_accomplishment_by_id,
    get_accomplishments,
    get_calendar_entries,
    get_calendar_entry_by_id,
    get_content_draft_by_id,
    get_content_drafts,
    publish_content_draft,
    update_accomplishment,
    update_calendar_entry,
    update_content_draft,
)
from beacon.db.profile import add_work_experience


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


# --- Content Drafts ---

class TestContentDrafts:
    def test_add_draft(self, db):
        draft_id = add_content_draft(db, "readme", "github", "My README", "# Hello")
        assert draft_id > 0

    def test_get_draft_by_id(self, db):
        draft_id = add_content_draft(db, "readme", "github", "My README", "# Hello")
        draft = get_content_draft_by_id(db, draft_id)
        assert draft is not None
        assert draft["title"] == "My README"
        assert draft["body"] == "# Hello"
        assert draft["platform"] == "github"
        assert draft["status"] == "draft"

    def test_get_draft_not_found(self, db):
        assert get_content_draft_by_id(db, 999) is None

    def test_list_drafts(self, db):
        add_content_draft(db, "readme", "github", "README", "body")
        add_content_draft(db, "post", "linkedin", "Post", "body")
        drafts = get_content_drafts(db)
        assert len(drafts) == 2

    def test_filter_by_platform(self, db):
        add_content_draft(db, "readme", "github", "README", "body")
        add_content_draft(db, "post", "linkedin", "Post", "body")
        drafts = get_content_drafts(db, platform="github")
        assert len(drafts) == 1
        assert drafts[0]["platform"] == "github"

    def test_filter_by_status(self, db):
        add_content_draft(db, "readme", "github", "README", "body", status="draft")
        add_content_draft(db, "post", "linkedin", "Post", "body", status="published")
        drafts = get_content_drafts(db, status="published")
        assert len(drafts) == 1
        assert drafts[0]["status"] == "published"

    def test_filter_by_content_type(self, db):
        add_content_draft(db, "readme", "github", "README", "body")
        add_content_draft(db, "post", "blog", "Blog Post", "body")
        drafts = get_content_drafts(db, content_type="readme")
        assert len(drafts) == 1

    def test_update_draft(self, db):
        draft_id = add_content_draft(db, "readme", "github", "Old Title", "body")
        success = update_content_draft(db, draft_id, title="New Title")
        assert success
        draft = get_content_draft_by_id(db, draft_id)
        assert draft["title"] == "New Title"

    def test_update_draft_empty_kwargs(self, db):
        draft_id = add_content_draft(db, "readme", "github", "Title", "body")
        assert not update_content_draft(db, draft_id)

    def test_update_draft_not_found(self, db):
        assert not update_content_draft(db, 999, title="New")

    def test_delete_draft(self, db):
        draft_id = add_content_draft(db, "readme", "github", "README", "body")
        assert delete_content_draft(db, draft_id)
        assert get_content_draft_by_id(db, draft_id) is None

    def test_delete_draft_not_found(self, db):
        assert not delete_content_draft(db, 999)

    def test_publish_draft(self, db):
        draft_id = add_content_draft(db, "post", "linkedin", "Post", "body")
        success = publish_content_draft(db, draft_id, url="https://linkedin.com/post/123")
        assert success
        draft = get_content_draft_by_id(db, draft_id)
        assert draft["status"] == "published"
        assert draft["published_url"] == "https://linkedin.com/post/123"
        assert draft["published_at"] is not None

    def test_publish_draft_without_url(self, db):
        draft_id = add_content_draft(db, "post", "blog", "Post", "body")
        success = publish_content_draft(db, draft_id)
        assert success
        draft = get_content_draft_by_id(db, draft_id)
        assert draft["status"] == "published"
        assert draft["published_url"] is None

    def test_publish_draft_not_found(self, db):
        assert not publish_content_draft(db, 999)

    def test_metadata_stored_as_json(self, db):
        draft_id = add_content_draft(db, "post", "blog", "Post", "body",
                                      metadata={"topic": "AI", "tags": ["python"]})
        draft = get_content_draft_by_id(db, draft_id)
        metadata = json.loads(draft["metadata"])
        assert metadata["topic"] == "AI"
        assert metadata["tags"] == ["python"]

    def test_update_metadata(self, db):
        draft_id = add_content_draft(db, "post", "blog", "Post", "body")
        update_content_draft(db, draft_id, metadata={"key": "value"})
        draft = get_content_draft_by_id(db, draft_id)
        metadata = json.loads(draft["metadata"])
        assert metadata["key"] == "value"


# --- Content Calendar ---

class TestContentCalendar:
    def test_add_entry(self, db):
        entry_id = add_calendar_entry(db, "AI Post", "linkedin", "post")
        assert entry_id > 0

    def test_get_entry_by_id(self, db):
        entry_id = add_calendar_entry(db, "AI Post", "linkedin", "post",
                                       topic="AI adoption", target_date="2025-06-01")
        entry = get_calendar_entry_by_id(db, entry_id)
        assert entry["title"] == "AI Post"
        assert entry["platform"] == "linkedin"
        assert entry["status"] == "idea"

    def test_get_entry_not_found(self, db):
        assert get_calendar_entry_by_id(db, 999) is None

    def test_list_entries(self, db):
        add_calendar_entry(db, "Post 1", "linkedin", "post")
        add_calendar_entry(db, "Post 2", "blog", "article")
        entries = get_calendar_entries(db)
        assert len(entries) == 2

    def test_filter_by_platform(self, db):
        add_calendar_entry(db, "Post 1", "linkedin", "post")
        add_calendar_entry(db, "Post 2", "blog", "article")
        entries = get_calendar_entries(db, platform="linkedin")
        assert len(entries) == 1

    def test_filter_by_status(self, db):
        add_calendar_entry(db, "Post 1", "linkedin", "post", status="idea")
        add_calendar_entry(db, "Post 2", "blog", "article", status="drafted")
        entries = get_calendar_entries(db, status="drafted")
        assert len(entries) == 1

    def test_update_entry(self, db):
        entry_id = add_calendar_entry(db, "Old Title", "blog", "post")
        assert update_calendar_entry(db, entry_id, title="New Title", status="outlined")
        entry = get_calendar_entry_by_id(db, entry_id)
        assert entry["title"] == "New Title"
        assert entry["status"] == "outlined"

    def test_update_entry_empty_kwargs(self, db):
        entry_id = add_calendar_entry(db, "Title", "blog", "post")
        assert not update_calendar_entry(db, entry_id)

    def test_delete_entry(self, db):
        entry_id = add_calendar_entry(db, "Post", "blog", "post")
        assert delete_calendar_entry(db, entry_id)
        assert get_calendar_entry_by_id(db, entry_id) is None

    def test_delete_entry_not_found(self, db):
        assert not delete_calendar_entry(db, 999)

    def test_draft_id_reference(self, db):
        draft_id = add_content_draft(db, "post", "blog", "Post", "body")
        entry_id = add_calendar_entry(db, "Post", "blog", "post", draft_id=draft_id)
        entry = get_calendar_entry_by_id(db, entry_id)
        assert entry["draft_id"] == draft_id

    def test_draft_id_set_null_on_delete(self, db):
        draft_id = add_content_draft(db, "post", "blog", "Post", "body")
        entry_id = add_calendar_entry(db, "Post", "blog", "post", draft_id=draft_id)
        delete_content_draft(db, draft_id)
        entry = get_calendar_entry_by_id(db, entry_id)
        assert entry["draft_id"] is None


# --- Accomplishments ---

class TestAccomplishments:
    def test_add_accomplishment(self, db):
        acc_id = add_accomplishment(db, "Led Copilot rollout to 50K users")
        assert acc_id > 0

    def test_get_accomplishment_by_id(self, db):
        acc_id = add_accomplishment(db, "Led Copilot rollout", context="Large university",
                                     action="Built governance framework", result="Adopted by all departments")
        acc = get_accomplishment_by_id(db, acc_id)
        assert acc["raw_statement"] == "Led Copilot rollout"
        assert acc["context"] == "Large university"
        assert acc["action"] == "Built governance framework"

    def test_get_accomplishment_not_found(self, db):
        assert get_accomplishment_by_id(db, 999) is None

    def test_list_accomplishments(self, db):
        add_accomplishment(db, "Accomplishment 1")
        add_accomplishment(db, "Accomplishment 2")
        accs = get_accomplishments(db)
        assert len(accs) == 2

    def test_filter_by_work_experience(self, db):
        work_id = add_work_experience(db, "Acme", "Analyst", "2023-01")
        add_accomplishment(db, "Acc 1", work_experience_id=work_id)
        add_accomplishment(db, "Acc 2")
        accs = get_accomplishments(db, work_experience_id=work_id)
        assert len(accs) == 1

    def test_update_accomplishment(self, db):
        acc_id = add_accomplishment(db, "Raw statement")
        assert update_accomplishment(db, acc_id, context="New context", metrics="10x improvement")
        acc = get_accomplishment_by_id(db, acc_id)
        assert acc["context"] == "New context"
        assert acc["metrics"] == "10x improvement"

    def test_update_accomplishment_empty(self, db):
        acc_id = add_accomplishment(db, "Raw statement")
        assert not update_accomplishment(db, acc_id)

    def test_delete_accomplishment(self, db):
        acc_id = add_accomplishment(db, "To delete")
        assert delete_accomplishment(db, acc_id)
        assert get_accomplishment_by_id(db, acc_id) is None

    def test_delete_accomplishment_not_found(self, db):
        assert not delete_accomplishment(db, 999)

    def test_work_experience_fk(self, db):
        work_id = add_work_experience(db, "Acme", "Dev", "2023-01")
        acc_id = add_accomplishment(db, "Built feature", work_experience_id=work_id)
        acc = get_accomplishment_by_id(db, acc_id)
        assert acc["work_experience_id"] == work_id
