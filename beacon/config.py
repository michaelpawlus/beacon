"""Beacon configuration management using TOML."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "data" / "beacon.toml"

VALID_CADENCES = ("hourly", "daily", "weekly")
VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


@dataclass
class BeaconConfig:
    """Beacon configuration with sensible defaults."""

    notification_email: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notification_cadence: str = "daily"
    scan_cadence: str = "daily"
    min_relevance_alert: float = 7.0
    desktop_notifications: bool = True
    log_level: str = "INFO"
    log_file: str = "data/beacon.log"

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty if valid)."""
        errors = []
        if self.notification_cadence not in VALID_CADENCES:
            errors.append(f"notification_cadence must be one of {VALID_CADENCES}")
        if self.scan_cadence not in VALID_CADENCES:
            errors.append(f"scan_cadence must be one of {VALID_CADENCES}")
        if self.log_level not in VALID_LOG_LEVELS:
            errors.append(f"log_level must be one of {VALID_LOG_LEVELS}")
        if not (0 <= self.min_relevance_alert <= 10):
            errors.append("min_relevance_alert must be between 0 and 10")
        if not (0 < self.smtp_port <= 65535):
            errors.append("smtp_port must be between 1 and 65535")
        return errors


def _serialize_config(config: BeaconConfig) -> str:
    """Serialize a BeaconConfig to TOML string."""
    lines = ["# Beacon configuration\n"]

    lines.append("[notifications]")
    lines.append(f'email = "{config.notification_email}"')
    lines.append(f'cadence = "{config.notification_cadence}"')
    lines.append(f"desktop = {str(config.desktop_notifications).lower()}")
    lines.append(f"min_relevance_alert = {config.min_relevance_alert}")
    lines.append("")

    lines.append("[smtp]")
    lines.append(f'host = "{config.smtp_host}"')
    lines.append(f"port = {config.smtp_port}")
    lines.append(f'user = "{config.smtp_user}"')
    lines.append(f'password = "{config.smtp_password}"')
    lines.append("")

    lines.append("[scanning]")
    lines.append(f'cadence = "{config.scan_cadence}"')
    lines.append("")

    lines.append("[logging]")
    lines.append(f'level = "{config.log_level}"')
    lines.append(f'file = "{config.log_file}"')
    lines.append("")

    return "\n".join(lines)


def _parse_toml_to_config(data: dict) -> BeaconConfig:
    """Parse a TOML dict into a BeaconConfig."""
    config = BeaconConfig()

    notif = data.get("notifications", {})
    config.notification_email = notif.get("email", config.notification_email)
    config.notification_cadence = notif.get("cadence", config.notification_cadence)
    config.desktop_notifications = notif.get("desktop", config.desktop_notifications)
    config.min_relevance_alert = notif.get("min_relevance_alert", config.min_relevance_alert)

    smtp = data.get("smtp", {})
    config.smtp_host = smtp.get("host", config.smtp_host)
    config.smtp_port = smtp.get("port", config.smtp_port)
    config.smtp_user = smtp.get("user", config.smtp_user)
    config.smtp_password = smtp.get("password", config.smtp_password)

    scanning = data.get("scanning", {})
    config.scan_cadence = scanning.get("cadence", config.scan_cadence)

    logging_cfg = data.get("logging", {})
    config.log_level = logging_cfg.get("level", config.log_level)
    config.log_file = logging_cfg.get("file", config.log_file)

    return config


def load_config(config_path: Path | str | None = None) -> BeaconConfig:
    """Load configuration from a TOML file. Returns defaults if file doesn't exist."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        return BeaconConfig()
    data = tomllib.loads(path.read_text())
    return _parse_toml_to_config(data)


def save_config(config: BeaconConfig, config_path: Path | str | None = None) -> Path:
    """Save configuration to a TOML file. Returns the path written."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_serialize_config(config))
    return path


# Mapping from flat CLI keys to config field names
_KEY_MAP = {
    "notification_email": "notification_email",
    "smtp_host": "smtp_host",
    "smtp_port": "smtp_port",
    "smtp_user": "smtp_user",
    "smtp_password": "smtp_password",
    "notification_cadence": "notification_cadence",
    "scan_cadence": "scan_cadence",
    "min_relevance_alert": "min_relevance_alert",
    "desktop_notifications": "desktop_notifications",
    "log_level": "log_level",
    "log_file": "log_file",
}


def get_config_value(config: BeaconConfig, key: str) -> str:
    """Get a config value by flat key name."""
    if key not in _KEY_MAP:
        raise KeyError(f"Unknown config key: {key}. Valid keys: {', '.join(sorted(_KEY_MAP))}")
    return str(getattr(config, _KEY_MAP[key]))


def set_config_value(config: BeaconConfig, key: str, value: str) -> BeaconConfig:
    """Set a config value by flat key name, with type coercion."""
    if key not in _KEY_MAP:
        raise KeyError(f"Unknown config key: {key}. Valid keys: {', '.join(sorted(_KEY_MAP))}")

    field_name = _KEY_MAP[key]
    # Get the current value to determine type
    current = getattr(config, field_name)

    # Coerce value to match current type
    if isinstance(current, bool):
        coerced = value.lower() in ("true", "1", "yes")
    elif isinstance(current, int):
        coerced = int(value)
    elif isinstance(current, float):
        coerced = float(value)
    else:
        coerced = value

    setattr(config, field_name, coerced)
    return config
