"""Tests for Beacon scheduling and automation (Phase 5, Step 5)."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from beacon.automation.cron_helper import CRON_MARKER, generate_crontab_entry, show_crontab_status
from beacon.automation.runner import run_automation_cycle, run_digest, run_scan_only
from beacon.config import BeaconConfig
from beacon.db.connection import get_connection, init_db
from beacon.scanner import ScanResult

runner = CliRunner()


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_beacon.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn, db_path
    conn.close()


def _insert_company(conn, name="TestCo"):
    cursor = conn.execute(
        "INSERT INTO companies (name, careers_platform, domain) VALUES (?, 'greenhouse', 'testco.com')",
        (name,),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_job(conn, company_id, title="Data Engineer", score=8.0):
    cursor = conn.execute(
        "INSERT INTO job_listings (company_id, title, relevance_score, status) VALUES (?, ?, ?, 'active')",
        (company_id, title, score),
    )
    conn.commit()
    return cursor.lastrowid


# --- Automation Runner ---

class TestRunScanOnly:
    @patch("beacon.scanner.scan_all")
    def test_scan_only_success(self, mock_scan, db):
        conn, _ = db
        mock_scan.return_value = [
            ScanResult("TestCo", "greenhouse", jobs_found=5, new_jobs=2),
        ]
        config = BeaconConfig()
        result = run_scan_only(conn, config)

        assert result["jobs_found"] == 5
        assert result["new_relevant_jobs"] == 2
        assert result["errors"] is None

        # Check automation_log
        log = conn.execute("SELECT * FROM automation_log WHERE run_type = 'scan'").fetchone()
        assert log is not None
        assert log["jobs_found"] == 5

    @patch("beacon.scanner.scan_all")
    def test_scan_with_errors(self, mock_scan, db):
        conn, _ = db
        mock_scan.return_value = [
            ScanResult("TestCo", "greenhouse", error="Connection failed"),
        ]
        config = BeaconConfig()
        result = run_scan_only(conn, config)

        assert result["errors"] is not None
        assert "Connection failed" in result["errors"]

    @patch("beacon.scanner.scan_all")
    def test_scan_exception(self, mock_scan, db):
        conn, _ = db
        mock_scan.side_effect = Exception("Import error")
        config = BeaconConfig()
        result = run_scan_only(conn, config)
        assert result["errors"] is not None


class TestRunDigest:
    def test_digest_empty_db(self, db):
        conn, _ = db
        config = BeaconConfig(desktop_notifications=False)
        result = run_digest(conn, config)
        assert result["notifications_sent"] == 0

        log = conn.execute("SELECT * FROM automation_log WHERE run_type = 'digest'").fetchone()
        assert log is not None

    @patch("beacon.notifications.registry.notify_all", return_value=[True])
    def test_digest_with_notification(self, mock_notify, db):
        conn, _ = db
        cid = _insert_company(conn)
        _insert_job(conn, cid)
        config = BeaconConfig()
        result = run_digest(conn, config)
        assert result["notifications_sent"] == 1


class TestRunFullCycle:
    @patch("beacon.scanner.scan_all")
    def test_full_cycle_no_new_jobs(self, mock_scan, db):
        conn, _ = db
        mock_scan.return_value = [
            ScanResult("TestCo", "greenhouse", jobs_found=3, new_jobs=0),
        ]
        config = BeaconConfig()
        result = run_automation_cycle(conn, config)

        assert result["jobs_found"] == 3
        assert result["new_relevant_jobs"] == 0
        assert result["notifications_sent"] == 0

        log = conn.execute("SELECT * FROM automation_log WHERE run_type = 'full'").fetchone()
        assert log is not None

    @patch("beacon.notifications.registry.notify_all", return_value=[True])
    @patch("beacon.scanner.scan_all")
    def test_full_cycle_with_notifications(self, mock_scan, mock_notify, db):
        conn, _ = db
        cid = _insert_company(conn)

        mock_scan.return_value = [
            ScanResult("TestCo", "greenhouse", jobs_found=5, new_jobs=3),
        ]

        # Insert some recent jobs to trigger notification
        conn.execute(
            "INSERT INTO job_listings (company_id, title, relevance_score, status, date_first_seen) VALUES (?, 'ML Engineer', 9.0, 'active', datetime('now'))",
            (cid,),
        )
        conn.commit()

        config = BeaconConfig(min_relevance_alert=7.0)
        result = run_automation_cycle(conn, config)

        assert result["jobs_found"] == 5
        assert result["new_relevant_jobs"] == 3

    @patch("beacon.scanner.scan_all")
    def test_full_cycle_scan_error_continues(self, mock_scan, db):
        conn, _ = db
        mock_scan.side_effect = Exception("Scan failed")
        config = BeaconConfig()
        result = run_automation_cycle(conn, config)
        assert result["errors"] is not None
        assert "scan" in result["errors"].lower()


class TestAutomationLog:
    @patch("beacon.scanner.scan_all")
    def test_log_recorded(self, mock_scan, db):
        conn, _ = db
        mock_scan.return_value = []
        config = BeaconConfig()
        run_scan_only(conn, config)

        logs = conn.execute("SELECT * FROM automation_log").fetchall()
        assert len(logs) == 1
        assert logs[0]["run_type"] == "scan"
        assert logs[0]["duration_seconds"] is not None
        assert logs[0]["completed_at"] is not None

    @patch("beacon.scanner.scan_all")
    def test_multiple_logs(self, mock_scan, db):
        conn, _ = db
        mock_scan.return_value = []
        config = BeaconConfig()
        run_scan_only(conn, config)
        run_scan_only(conn, config)

        logs = conn.execute("SELECT * FROM automation_log").fetchall()
        assert len(logs) == 2


# --- Cron Helper ---

class TestCronHelper:
    def test_generate_entry(self):
        entry = generate_crontab_entry(6)
        assert "*/6" in entry
        assert CRON_MARKER in entry
        assert "automation run" in entry

    def test_generate_entry_custom_hours(self):
        entry = generate_crontab_entry(12)
        assert "*/12" in entry

    @patch("beacon.automation.cron_helper.subprocess.run")
    @patch("beacon.automation.cron_helper.shutil.which", return_value="/usr/bin/crontab")
    def test_show_status_no_entry(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="0 * * * * some_other_job\n")
        status = show_crontab_status()
        assert "No beacon cron" in status

    @patch("beacon.automation.cron_helper.subprocess.run")
    @patch("beacon.automation.cron_helper.shutil.which", return_value="/usr/bin/crontab")
    def test_show_status_with_entry(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=f"0 */6 * * * /usr/bin/python3 -m beacon.cli automation run {CRON_MARKER}\n",
        )
        status = show_crontab_status()
        assert "Beacon cron active" in status

    @patch("beacon.automation.cron_helper.shutil.which", return_value=None)
    def test_show_status_no_crontab(self, mock_which):
        status = show_crontab_status()
        assert "not available" in status


# --- CLI Commands ---

class TestAutomationCLI:
    @patch("beacon.scanner.scan_all")
    @patch("beacon.config.load_config")
    def test_automation_run(self, mock_config, mock_scan, db):
        from beacon.cli import app
        conn, _ = db
        mock_config.return_value = BeaconConfig()
        mock_scan.return_value = []
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["automation", "run"])
            assert result.exit_code == 0

    @patch("beacon.scanner.scan_all")
    @patch("beacon.config.load_config")
    def test_automation_scan_only(self, mock_config, mock_scan, db):
        from beacon.cli import app
        conn, _ = db
        mock_config.return_value = BeaconConfig()
        mock_scan.return_value = []
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["automation", "run", "--scan-only"])
            assert result.exit_code == 0

    def test_automation_log_empty(self, db):
        from beacon.cli import app
        conn, _ = db
        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["automation", "log"])
            assert result.exit_code == 0
            assert "No automation" in result.output

    @patch("beacon.scanner.scan_all")
    @patch("beacon.config.load_config")
    def test_automation_log_with_data(self, mock_config, mock_scan, db):
        from beacon.cli import app
        conn, _ = db
        mock_config.return_value = BeaconConfig()
        mock_scan.return_value = []
        run_scan_only(conn, BeaconConfig())

        with patch("beacon.cli.get_connection", return_value=conn):
            result = runner.invoke(app, ["automation", "log"])
            assert result.exit_code == 0
