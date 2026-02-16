"""Tests for Beacon configuration system and logging setup."""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from beacon.config import (
    BeaconConfig,
    _parse_toml_to_config,
    _serialize_config,
    get_config_value,
    load_config,
    save_config,
    set_config_value,
)
from beacon.logging_setup import setup_logging

runner = CliRunner()


# --- BeaconConfig defaults ---

class TestBeaconConfigDefaults:
    def test_default_values(self):
        config = BeaconConfig()
        assert config.notification_email == ""
        assert config.smtp_host == ""
        assert config.smtp_port == 587
        assert config.notification_cadence == "daily"
        assert config.scan_cadence == "daily"
        assert config.min_relevance_alert == 7.0
        assert config.desktop_notifications is True
        assert config.log_level == "INFO"
        assert config.log_file == "data/beacon.log"

    def test_custom_values(self):
        config = BeaconConfig(
            notification_email="test@example.com",
            smtp_host="smtp.example.com",
            smtp_port=465,
            min_relevance_alert=8.0,
        )
        assert config.notification_email == "test@example.com"
        assert config.smtp_host == "smtp.example.com"
        assert config.smtp_port == 465
        assert config.min_relevance_alert == 8.0


# --- Validation ---

class TestBeaconConfigValidation:
    def test_valid_config(self):
        config = BeaconConfig()
        assert config.validate() == []

    def test_invalid_cadence(self):
        config = BeaconConfig(notification_cadence="yearly")
        errors = config.validate()
        assert any("notification_cadence" in e for e in errors)

    def test_invalid_scan_cadence(self):
        config = BeaconConfig(scan_cadence="minutely")
        errors = config.validate()
        assert any("scan_cadence" in e for e in errors)

    def test_invalid_log_level(self):
        config = BeaconConfig(log_level="VERBOSE")
        errors = config.validate()
        assert any("log_level" in e for e in errors)

    def test_invalid_min_relevance(self):
        config = BeaconConfig(min_relevance_alert=15.0)
        errors = config.validate()
        assert any("min_relevance_alert" in e for e in errors)

    def test_invalid_smtp_port(self):
        config = BeaconConfig(smtp_port=0)
        errors = config.validate()
        assert any("smtp_port" in e for e in errors)

    def test_multiple_errors(self):
        config = BeaconConfig(notification_cadence="bad", log_level="bad")
        errors = config.validate()
        assert len(errors) >= 2


# --- TOML round-trip ---

class TestTomlRoundTrip:
    def test_serialize_deserialize(self):
        config = BeaconConfig(
            notification_email="user@example.com",
            smtp_host="smtp.gmail.com",
            smtp_port=465,
            min_relevance_alert=8.5,
            desktop_notifications=False,
            scan_cadence="weekly",
            log_level="DEBUG",
        )
        toml_str = _serialize_config(config)
        import tomllib
        data = tomllib.loads(toml_str)
        restored = _parse_toml_to_config(data)

        assert restored.notification_email == "user@example.com"
        assert restored.smtp_host == "smtp.gmail.com"
        assert restored.smtp_port == 465
        assert restored.min_relevance_alert == 8.5
        assert restored.desktop_notifications is False
        assert restored.scan_cadence == "weekly"
        assert restored.log_level == "DEBUG"

    def test_serialize_defaults_roundtrip(self):
        config = BeaconConfig()
        toml_str = _serialize_config(config)
        import tomllib
        data = tomllib.loads(toml_str)
        restored = _parse_toml_to_config(data)
        assert restored.notification_email == config.notification_email
        assert restored.smtp_port == config.smtp_port
        assert restored.log_level == config.log_level

    def test_parse_empty_toml(self):
        config = _parse_toml_to_config({})
        assert config.notification_email == ""
        assert config.smtp_port == 587

    def test_parse_partial_toml(self):
        data = {"notifications": {"email": "test@test.com"}}
        config = _parse_toml_to_config(data)
        assert config.notification_email == "test@test.com"
        assert config.smtp_port == 587  # default preserved


# --- File I/O ---

class TestFileIO:
    def test_load_config_missing_file(self, tmp_path):
        path = tmp_path / "nonexistent.toml"
        config = load_config(path)
        assert config.notification_email == ""  # defaults

    def test_save_and_load(self, tmp_path):
        path = tmp_path / "config.toml"
        config = BeaconConfig(notification_email="saved@test.com", smtp_port=465)
        save_config(config, path)
        assert path.exists()

        loaded = load_config(path)
        assert loaded.notification_email == "saved@test.com"
        assert loaded.smtp_port == 465

    def test_save_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "sub" / "dir" / "config.toml"
        save_config(BeaconConfig(), path)
        assert path.exists()


# --- Key-value access ---

class TestKeyValueAccess:
    def test_get_value(self):
        config = BeaconConfig(notification_email="test@test.com")
        assert get_config_value(config, "notification_email") == "test@test.com"

    def test_get_unknown_key(self):
        config = BeaconConfig()
        with pytest.raises(KeyError, match="Unknown config key"):
            get_config_value(config, "nonexistent_key")

    def test_set_string_value(self):
        config = BeaconConfig()
        set_config_value(config, "notification_email", "new@test.com")
        assert config.notification_email == "new@test.com"

    def test_set_int_value(self):
        config = BeaconConfig()
        set_config_value(config, "smtp_port", "465")
        assert config.smtp_port == 465

    def test_set_float_value(self):
        config = BeaconConfig()
        set_config_value(config, "min_relevance_alert", "8.5")
        assert config.min_relevance_alert == 8.5

    def test_set_bool_value(self):
        config = BeaconConfig()
        set_config_value(config, "desktop_notifications", "false")
        assert config.desktop_notifications is False

    def test_set_unknown_key(self):
        config = BeaconConfig()
        with pytest.raises(KeyError):
            set_config_value(config, "bad_key", "value")


# --- CLI commands ---

class TestConfigCLI:
    def test_config_show(self):
        from beacon.cli import app
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "notification_email" in result.output

    def test_config_init(self, tmp_path):
        from beacon.cli import app
        config_path = tmp_path / "beacon.toml"
        with patch("beacon.config.DEFAULT_CONFIG_PATH", config_path):
            result = runner.invoke(app, ["config", "init"])
            assert result.exit_code == 0

    def test_config_set(self, tmp_path):
        from beacon.cli import app
        config_path = tmp_path / "beacon.toml"
        save_config(BeaconConfig(), config_path)
        with patch("beacon.config.DEFAULT_CONFIG_PATH", config_path):
            result = runner.invoke(app, ["config", "set", "log_level", "DEBUG"])
            assert result.exit_code == 0


# --- Logging setup ---

class TestLoggingSetup:
    def test_setup_creates_logger(self, tmp_path):
        log_file = tmp_path / "test.log"
        # Clear any existing handlers
        logger = logging.getLogger("beacon")
        logger.handlers.clear()

        result = setup_logging(log_level="DEBUG", log_file=str(log_file))
        assert result.name == "beacon"
        assert result.level == logging.DEBUG
        assert len(result.handlers) == 2  # file + console

        # Cleanup
        for handler in result.handlers[:]:
            handler.close()
            result.removeHandler(handler)

    def test_setup_creates_log_directory(self, tmp_path):
        log_file = tmp_path / "sub" / "dir" / "test.log"
        logger = logging.getLogger("beacon")
        logger.handlers.clear()

        setup_logging(log_file=str(log_file))
        assert log_file.parent.exists()

        # Cleanup
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    def test_idempotent_setup(self, tmp_path):
        log_file = tmp_path / "test.log"
        logger = logging.getLogger("beacon")
        logger.handlers.clear()

        setup_logging(log_file=str(log_file))
        handler_count = len(logger.handlers)
        setup_logging(log_file=str(log_file))
        assert len(logger.handlers) == handler_count

        # Cleanup
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    def test_writes_to_file(self, tmp_path):
        log_file = tmp_path / "test.log"
        logger = logging.getLogger("beacon")
        logger.handlers.clear()

        setup_logging(log_level="DEBUG", log_file=str(log_file))
        logger.info("Test message")

        # Flush handlers
        for handler in logger.handlers:
            handler.flush()

        content = log_file.read_text()
        assert "Test message" in content

        # Cleanup
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)
