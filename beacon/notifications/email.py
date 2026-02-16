"""Email notifier using stdlib smtplib."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from beacon.config import BeaconConfig
from beacon.notifications.base import BaseNotifier

logger = logging.getLogger("beacon.notifications.email")


class EmailNotifier(BaseNotifier):
    """Send notifications via SMTP email."""

    def __init__(self, config: BeaconConfig):
        self.config = config

    def is_configured(self) -> bool:
        return bool(self.config.notification_email and self.config.smtp_host)

    def send(self, subject: str, body: str, urgency: str = "normal") -> bool:
        if not self.is_configured():
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[Beacon] {subject}"
        msg["From"] = self.config.smtp_user or self.config.notification_email
        msg["To"] = self.config.notification_email

        if urgency == "high":
            msg["X-Priority"] = "1"

        msg.attach(MIMEText(body, "plain"))

        try:
            if self.config.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port)
            else:
                server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port)
                server.starttls()

            if self.config.smtp_user and self.config.smtp_password:
                server.login(self.config.smtp_user, self.config.smtp_password)

            server.send_message(msg)
            server.quit()
            logger.info("Email sent to %s: %s", self.config.notification_email, subject)
            return True
        except Exception as e:
            logger.error("Failed to send email: %s", e)
            return False
