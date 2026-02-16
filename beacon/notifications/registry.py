"""Notification registry — discovers and dispatches to configured notifiers."""

import logging

from beacon.config import BeaconConfig
from beacon.notifications.base import BaseNotifier
from beacon.notifications.desktop import DesktopNotifier
from beacon.notifications.email import EmailNotifier

logger = logging.getLogger("beacon.notifications.registry")


def get_notifiers(config: BeaconConfig) -> list[BaseNotifier]:
    """Get all configured notifiers."""
    notifiers: list[BaseNotifier] = []

    email = EmailNotifier(config)
    if email.is_configured():
        notifiers.append(email)

    desktop = DesktopNotifier(config)
    if desktop.is_configured():
        notifiers.append(desktop)

    return notifiers


def notify_all(
    config: BeaconConfig,
    subject: str,
    body: str,
    urgency: str = "normal",
) -> list[bool]:
    """Send notification through all configured notifiers. Returns list of success booleans."""
    notifiers = get_notifiers(config)
    if not notifiers:
        logger.warning("No notifiers configured")
        return []

    results = []
    for notifier in notifiers:
        try:
            result = notifier.send(subject, body, urgency)
            results.append(result)
        except Exception as e:
            logger.error("Notifier %s failed: %s", type(notifier).__name__, e)
            results.append(False)

    return results
