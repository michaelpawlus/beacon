"""Desktop notifier using OS-native tools via subprocess."""

import logging
import platform
import subprocess

from beacon.config import BeaconConfig
from beacon.notifications.base import BaseNotifier

logger = logging.getLogger("beacon.notifications.desktop")


class DesktopNotifier(BaseNotifier):
    """Send desktop notifications using OS-native tools.

    Linux: notify-send
    macOS: osascript
    No required dependencies.
    """

    def __init__(self, config: BeaconConfig):
        self.config = config
        self._system = platform.system()

    def is_configured(self) -> bool:
        return self.config.desktop_notifications

    def send(self, subject: str, body: str, urgency: str = "normal") -> bool:
        if not self.is_configured():
            return False

        try:
            if self._system == "Linux":
                return self._send_linux(subject, body, urgency)
            elif self._system == "Darwin":
                return self._send_macos(subject, body)
            else:
                logger.warning("Desktop notifications not supported on %s", self._system)
                return False
        except Exception as e:
            logger.error("Desktop notification failed: %s", e)
            return False

    def _send_linux(self, subject: str, body: str, urgency: str) -> bool:
        urgency_map = {"low": "low", "normal": "normal", "high": "critical"}
        notify_urgency = urgency_map.get(urgency, "normal")
        result = subprocess.run(
            ["notify-send", "--urgency", notify_urgency, f"Beacon: {subject}", body],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0

    def _send_macos(self, subject: str, body: str) -> bool:
        script = f'display notification "{body}" with title "Beacon: {subject}"'
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
