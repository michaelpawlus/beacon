"""Base notifier abstract class."""

from abc import ABC, abstractmethod


class BaseNotifier(ABC):
    """Abstract base class for notification backends."""

    @abstractmethod
    def send(self, subject: str, body: str, urgency: str = "normal") -> bool:
        """Send a notification. Returns True if successful."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if this notifier is properly configured."""
