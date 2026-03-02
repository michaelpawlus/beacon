"""Tests for speaker/presentation CLI commands."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from beacon.cli import app
from beacon.db.connection import get_connection, init_db
from beacon.db.speaker import add_presentation, set_bio, set_headshot
from beacon.llm.client import LLMResponse

runner = CliRunner()

MOCK_LLM = "beacon.llm.client.generate"


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn, db_path
    conn.close()


def _add_sample_presentation(conn):
    return add_presentation(
        conn, "AI in Higher Ed",
        abstract="How AI transforms advancement.",
        event_name="DRIVE 2025",
        date="2025-09-15",
        audience="Advancement professionals",
        status="accepted",
    )


class TestProfilePresentations:
    def test_list_empty(self, db):
        conn, db_path = db
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["profile", "presentations"])
            assert result.exit_code == 0
            assert "No presentations" in result.output

    def test_list_with_data(self, db):
        conn, db_path = db
        _add_sample_presentation(conn)
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["profile", "presentations"])
            assert result.exit_code == 0
            assert "AI in Higher Ed" in result.output

    def test_detail_view(self, db):
        conn, db_path = db
        pres_id = _add_sample_presentation(conn)
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["profile", "presentations", "--detail", str(pres_id)])
            assert result.exit_code == 0
            assert "AI in Higher Ed" in result.output
            assert "DRIVE 2025" in result.output

    def test_detail_not_found(self, db):
        conn, db_path = db
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["profile", "presentations", "--detail", "999"])
            assert result.exit_code == 0
            assert "No presentation found" in result.output


class TestProfileAddPresentation:
    def test_add_presentation(self, db):
        conn, db_path = db
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, [
                "profile", "add-presentation",
                "--title", "New Talk",
                "--event", "Conference 2025",
                "--date", "2025-10-01",
            ])
            assert result.exit_code == 0
            assert "added" in result.output

    def test_add_with_key_points_and_tags(self, db):
        conn, db_path = db
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, [
                "profile", "add-presentation",
                "--title", "Tagged Talk",
                "--key-points", "point1, point2",
                "--tags", "AI, data",
            ])
            assert result.exit_code == 0
            assert "added" in result.output


class TestProfileSpeaker:
    def test_no_profile(self, db):
        conn, db_path = db
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["profile", "speaker"])
            assert result.exit_code == 0
            assert "No speaker profile" in result.output

    def test_with_profile(self, db):
        conn, db_path = db
        set_headshot(conn, "/img/me.jpg")
        set_bio(conn, "Short bio here.", long_bio="Long bio paragraph.")
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["profile", "speaker"])
            assert result.exit_code == 0
            assert "/img/me.jpg" in result.output
            assert "Short bio here" in result.output


class TestProfileSetHeadshot:
    def test_set_headshot(self, db, tmp_path):
        conn, db_path = db
        img = tmp_path / "headshot.jpg"
        img.write_bytes(b"fake-image")
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["profile", "set-headshot", str(img)])
            assert result.exit_code == 0
            assert "Headshot set" in result.output

    def test_set_headshot_missing_file(self, db):
        conn, db_path = db
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["profile", "set-headshot", "/nonexistent/file.jpg"])
            assert result.exit_code == 1
            assert "not found" in result.output


class TestPresenceBio:
    @patch(MOCK_LLM)
    def test_generate_short_bio(self, mock_generate, db):
        conn, db_path = db
        mock_generate.return_value = LLMResponse(
            text="Jane Doe is a data scientist specializing in AI.",
            model="test", input_tokens=100, output_tokens=50,
        )
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "bio"])
            assert result.exit_code == 0
            assert "Jane Doe" in result.output

    @patch(MOCK_LLM)
    def test_generate_long_bio(self, mock_generate, db):
        conn, db_path = db
        mock_generate.return_value = LLMResponse(
            text="Jane Doe is a data scientist with a decade of experience...",
            model="test", input_tokens=100, output_tokens=100,
        )
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "bio", "--length", "long"])
            assert result.exit_code == 0
            assert "decade" in result.output

    @patch(MOCK_LLM)
    def test_bio_save(self, mock_generate, db):
        conn, db_path = db
        mock_generate.return_value = LLMResponse(
            text="Saved bio text.", model="test", input_tokens=100, output_tokens=50,
        )
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "bio", "--save"])
            assert result.exit_code == 0
            assert "saved to speaker profile" in result.output

    @patch(MOCK_LLM)
    def test_bio_output_file(self, mock_generate, db, tmp_path):
        conn, db_path = db
        mock_generate.return_value = LLMResponse(
            text="Bio for file.", model="test", input_tokens=100, output_tokens=50,
        )
        output_file = tmp_path / "bio.txt"
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["presence", "bio", "--output", str(output_file)])
            assert result.exit_code == 0
            assert output_file.exists()
            assert "Bio for file." in output_file.read_text()
