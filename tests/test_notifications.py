"""Tests for Beacon notification system (Phase 5, Step 4)."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from beacon.config import BeaconConfig
from beacon.notifications.base import BaseNotifier
from beacon.notifications.desktop import DesktopNotifier
from beacon.notifications.email import EmailNotifier
from beacon.notifications.formatters import format_action_items, format_digest, format_new_jobs_alert
from beacon.notifications.registry import get_notifiers, notify_all

runner = CliRunner()


# --- EmailNotifier ---

class TestEmailNotifier:
    def test_not_configured(self):
        config = BeaconConfig()
        notifier = EmailNotifier(config)
        assert notifier.is_configured() is False
        assert notifier.send("test", "body") is False

    def test_configured(self):
        config = BeaconConfig(
            notification_email="test@test.com",
            smtp_host="smtp.test.com",
        )
        notifier = EmailNotifier(config)
        assert notifier.is_configured() is True

    @patch("beacon.notifications.email.smtplib.SMTP")
    def test_send_tls(self, mock_smtp):
        config = BeaconConfig(
            notification_email="test@test.com",
            smtp_host="smtp.test.com",
            smtp_port=587,
            smtp_user="user",
            smtp_password="pass",
        )
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        notifier = EmailNotifier(config)
        result = notifier.send("Test Subject", "Test Body")

        assert result is True
        mock_smtp.assert_called_once_with("smtp.test.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user", "pass")
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()

    @patch("beacon.notifications.email.smtplib.SMTP_SSL")
    def test_send_ssl(self, mock_smtp_ssl):
        config = BeaconConfig(
            notification_email="test@test.com",
            smtp_host="smtp.test.com",
            smtp_port=465,
        )
        mock_server = MagicMock()
        mock_smtp_ssl.return_value = mock_server

        notifier = EmailNotifier(config)
        result = notifier.send("Test", "Body")

        assert result is True
        mock_smtp_ssl.assert_called_once_with("smtp.test.com", 465)

    @patch("beacon.notifications.email.smtplib.SMTP")
    def test_send_failure(self, mock_smtp):
        config = BeaconConfig(
            notification_email="test@test.com",
            smtp_host="smtp.test.com",
        )
        mock_smtp.side_effect = ConnectionError("Connection refused")

        notifier = EmailNotifier(config)
        result = notifier.send("Test", "Body")
        assert result is False

    @patch("beacon.notifications.email.smtplib.SMTP")
    def test_high_urgency_header(self, mock_smtp):
        config = BeaconConfig(
            notification_email="test@test.com",
            smtp_host="smtp.test.com",
            smtp_port=587,
        )
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        notifier = EmailNotifier(config)
        notifier.send("Urgent", "Body", urgency="high")

        # Verify the message was sent
        mock_server.send_message.assert_called_once()
        msg = mock_server.send_message.call_args[0][0]
        assert msg["X-Priority"] == "1"


# --- DesktopNotifier ---

class TestDesktopNotifier:
    def test_not_configured(self):
        config = BeaconConfig(desktop_notifications=False)
        notifier = DesktopNotifier(config)
        assert notifier.is_configured() is False
        assert notifier.send("test", "body") is False

    def test_configured(self):
        config = BeaconConfig(desktop_notifications=True)
        notifier = DesktopNotifier(config)
        assert notifier.is_configured() is True

    @patch("beacon.notifications.desktop.subprocess.run")
    @patch("beacon.notifications.desktop.platform.system", return_value="Linux")
    def test_send_linux(self, mock_system, mock_run):
        config = BeaconConfig(desktop_notifications=True)
        mock_run.return_value = MagicMock(returncode=0)

        notifier = DesktopNotifier(config)
        notifier._system = "Linux"
        result = notifier.send("Test", "Body")

        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "notify-send" in args

    @patch("beacon.notifications.desktop.subprocess.run")
    def test_send_macos(self, mock_run):
        config = BeaconConfig(desktop_notifications=True)
        mock_run.return_value = MagicMock(returncode=0)

        notifier = DesktopNotifier(config)
        notifier._system = "Darwin"
        result = notifier.send("Test", "Body")

        assert result is True
        args = mock_run.call_args[0][0]
        assert "osascript" in args

    def test_unsupported_platform(self):
        config = BeaconConfig(desktop_notifications=True)
        notifier = DesktopNotifier(config)
        notifier._system = "Windows"
        result = notifier.send("Test", "Body")
        assert result is False

    @patch("beacon.notifications.desktop.subprocess.run")
    def test_send_failure(self, mock_run):
        config = BeaconConfig(desktop_notifications=True)
        mock_run.return_value = MagicMock(returncode=1)

        notifier = DesktopNotifier(config)
        notifier._system = "Linux"
        result = notifier.send("Test", "Body")
        assert result is False


# --- Registry ---

class TestRegistry:
    def test_no_notifiers_configured(self):
        config = BeaconConfig(desktop_notifications=False)
        notifiers = get_notifiers(config)
        assert len(notifiers) == 0

    def test_desktop_only(self):
        config = BeaconConfig(desktop_notifications=True)
        notifiers = get_notifiers(config)
        assert len(notifiers) == 1
        assert isinstance(notifiers[0], DesktopNotifier)

    def test_email_and_desktop(self):
        config = BeaconConfig(
            notification_email="test@test.com",
            smtp_host="smtp.test.com",
            desktop_notifications=True,
        )
        notifiers = get_notifiers(config)
        assert len(notifiers) == 2

    def test_notify_all_no_config(self):
        config = BeaconConfig(desktop_notifications=False)
        results = notify_all(config, "Test", "Body")
        assert results == []

    @patch("beacon.notifications.desktop.subprocess.run")
    def test_notify_all_with_desktop(self, mock_run):
        config = BeaconConfig(desktop_notifications=True)
        mock_run.return_value = MagicMock(returncode=0)

        results = notify_all(config, "Test", "Body")
        # Desktop might fail on non-Linux/macOS, but shouldn't raise
        assert isinstance(results, list)


# --- Formatters ---

class TestFormatters:
    def test_format_new_jobs_empty(self):
        result = format_new_jobs_alert([])
        assert "No new relevant" in result

    def test_format_new_jobs(self):
        jobs = [
            {"company_name": "Anthropic", "title": "ML Engineer", "relevance_score": 9.4},
            {"company_name": "Cursor", "title": "Backend Dev", "relevance_score": 8.1},
        ]
        result = format_new_jobs_alert(jobs)
        assert "2 new relevant" in result
        assert "Anthropic" in result
        assert "Cursor" in result

    def test_format_digest(self):
        from beacon.dashboard import DashboardData
        data = DashboardData(
            date="Feb 15, 2026",
            company_count=38,
            active_job_count=127,
            application_count=12,
            top_jobs=[{"company_name": "Test", "title": "Engineer", "relevance_score": 8.0}],
            pipeline={"applied": 5, "draft": 2},
            action_items=["Check new jobs"],
        )
        result = format_digest(data)
        assert "Daily Digest" in result
        assert "38" in result
        assert "Test" in result

    def test_format_action_items_empty(self):
        result = format_action_items([])
        assert "No pending" in result

    def test_format_action_items(self):
        items = ["Check jobs", "Update profile"]
        result = format_action_items(items)
        assert "Check jobs" in result
        assert "Update profile" in result


# --- CLI ---

class TestNotificationCLI:
    @patch("beacon.notifications.registry.notify_all", return_value=[True])
    @patch("beacon.config.load_config")
    def test_test_notify_command(self, mock_config, mock_notify):
        from beacon.cli import app
        mock_config.return_value = BeaconConfig()
        result = runner.invoke(app, ["automation", "test-notify"])
        assert result.exit_code == 0
