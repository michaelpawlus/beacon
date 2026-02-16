"""Tests for onboarding and polish (Phase 5, Step 8)."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from beacon.db.connection import get_connection, init_db

runner = CliRunner()


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn, db_path
    conn.close()


class TestGuideCommand:
    def test_guide_displays(self):
        from beacon.cli import app
        result = runner.invoke(app, ["guide"])
        assert result.exit_code == 0
        assert "Getting Started" in result.output
        assert "beacon init" in result.output
        assert "beacon scan" in result.output

    def test_guide_has_all_sections(self):
        from beacon.cli import app
        result = runner.invoke(app, ["guide"])
        assert "Build Your Profile" in result.output
        assert "Configure Preferences" in result.output
        assert "Scan for Jobs" in result.output
        assert "Set Up Automation" in result.output


class TestDashboardWelcome:
    def test_dashboard_runs_on_empty_db(self, db):
        from beacon.cli import app
        conn, _ = db
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["dashboard"])
            assert result.exit_code == 0


class TestConfigShow:
    def test_config_show_displays(self):
        from beacon.cli import app
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "notification_email" in result.output
        assert "log_level" in result.output


class TestEndToEndCLI:
    def test_all_help_commands(self):
        from beacon.cli import app
        # Test that all major sub-apps respond to --help
        for cmd in ["--help", "config --help", "automation --help", "application --help"]:
            result = runner.invoke(app, cmd.split())
            assert result.exit_code == 0, f"Failed for: {cmd}"
