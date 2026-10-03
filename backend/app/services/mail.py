"""Outbound email.

The existing Step 1 module only resolved SMTP settings; this adds delivery.
Two properties matter more than features here:

* **The SMTP password is a** ``SecretStr`` **and is never logged.** Connection
  failures are reported by exception *type* only, because driver messages can
  echo the username and host.
* **Delivery failures never propagate to the API response.** A forgotten-password
  request must answer identically whether or not the mail was sent, otherwise
  the response becomes an account-enumeration oracle.
"""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """The message could not be handed to the SMTP server."""


@dataclass(frozen=True, slots=True)
class SmtpSettings:
    """Resolved SMTP connection details."""

    host: str
    port: int = 587
    username: str | None = None
    password: str | None = None
    from_email: str = ""
    use_tls: bool = True

    @property
    def is_complete(self) -> bool:
        return bool(self.host and self.from_email)


def get_smtp_settings(settings: Settings | None = None) -> SmtpSettings:
    """Build :class:`SmtpSettings` from the environment.

    ``SecretStr`` values are unwrapped here and only here, at the point of use.
    """
    settings = settings or get_settings()
    password = settings.smtp_password
    return SmtpSettings(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=password.get_secret_value() if password is not None else None,
        from_email=settings.smtp_from_email,
        use_tls=settings.smtp_port == 587,
    )


def is_email_configured(settings: Settings | None = None) -> bool:
    return get_smtp_settings(settings).is_complete


def _client_name(from_email: str) -> str:
    """The display name configured in ``SMTP_FROM_EMAIL`` ("Name <addr>")."""
    name, address = parseaddr(from_email)
    return name or address


class EmailService:
    """Sends plain-text transactional email over SMTP."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def is_configured(self) -> bool:
        return is_email_configured(self._settings)

    def build_password_reset_message(
        self,
        *,
        to_email: str,
        admin_name: str,
        reset_url: str,
        expires_in_minutes: int,
    ) -> EmailMessage:
        """Compose the password-reset email.

        The message tells the recipient what to do, how long they have, and
        that they did not ask for it. It contains no credential material -
        only the single-use link.
        """
        smtp = get_smtp_settings(self._settings)
        subject = f"Password reset for {self._settings.app_name} admin"

        greeting = admin_name.strip() or "there"
        body = "\n".join(
            [
                f"Hello {greeting},",
                "",
                f"A password reset was requested for your {self._settings.app_name} "
                "administrator account.",
                "",
                "Open this link to choose a new password:",
                reset_url,
                "",
                f"This link expires in {expires_in_minutes} minutes and can only be used once.",
                "",
                "If you did not request this, you can ignore this email. Your "
                "current password will keep working and no change will be made.",
                "",
                f"-- {self._settings.app_name} administration",
            ]
        )

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr((_client_name(smtp.from_email), smtp.from_email))
        message["To"] = to_email
        message["Reply-To"] = smtp.from_email
        message.set_content(body)
        return message

    def send(self, message: EmailMessage) -> None:
        """Deliver ``message``, raising :class:`EmailDeliveryError` on failure.

        Uses an explicit context manager rather than a shared connection so a
        queued message can never be sent to the wrong recipient.
        """
        smtp = get_smtp_settings(self._settings)
        if not smtp.is_complete:
            raise EmailDeliveryError("SMTP is not configured")

        try:
            with smtplib.SMTP(smtp.host, smtp.port, timeout=15) as client:
                if smtp.use_tls:
                    client.starttls()
                if smtp.username and smtp.password:
                    client.login(smtp.username, smtp.password)
                client.send_message(message)
        except (smtplib.SMTPException, OSError) as exc:
            # Never log the message body or the credentials.
            logger.error(
                "Email delivery failed (%s) to domain %s",
                type(exc).__name__,
                to_domain(message.get("To", "")),
            )
            raise EmailDeliveryError("The message could not be delivered") from exc

    def send_password_reset(
        self,
        *,
        to_email: str,
        admin_name: str,
        reset_url: str,
        expires_in_minutes: int,
    ) -> None:
        """Build and send the password-reset email."""
        self.send(
            self.build_password_reset_message(
                to_email=to_email,
                admin_name=admin_name,
                reset_url=reset_url,
                expires_in_minutes=expires_in_minutes,
            )
        )


def to_domain(address: str) -> str:
    """The domain part only - enough to debug routing, useless to an attacker."""
    _, domain = parseaddr(address or "")
    return domain or "unknown"
