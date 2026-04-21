import smtplib
import ssl
from email.message import EmailMessage
from typing import List

from app.business.emailing.config import EmailProviderConfig
from app.business.emailing.config import SmtpEmailConfig
from app.business.emailing.providers.base import EmailProvider
from app.business.emailing.types import EmailProviderType
from app.business.emailing.types import EmailSendRequest
from app.business.emailing.types import EmailSendResult
from app.models.errors import BusinessProcessingError


class SmtpEmailProvider(EmailProvider):

    def __init__(self, provider_config: EmailProviderConfig, smtp_config: SmtpEmailConfig):
        self._provider_config = provider_config
        self._smtp_config = smtp_config

    def send(self, request: EmailSendRequest) -> EmailSendResult:
        if not self._smtp_config.host:
            raise BusinessProcessingError("EMAIL_SMTP_HOST is not configured")

        sender = self._resolve_sender()
        recipients = [recipient.email for recipient in request.recipients]
        message = self._build_message(sender, recipients, request)

        try:
            if self._smtp_config.use_ssl:
                context = self._build_ssl_context()
                with smtplib.SMTP_SSL(
                    host=self._smtp_config.host,
                    port=self._smtp_config.port,
                    timeout=self._provider_config.send_timeout_seconds,
                    context=context,
                ) as smtp_client:
                    self._authenticate_if_needed(smtp_client)
                    smtp_client.send_message(message)
            else:
                with smtplib.SMTP(
                    host=self._smtp_config.host,
                    port=self._smtp_config.port,
                    timeout=self._provider_config.send_timeout_seconds,
                ) as smtp_client:
                    if self._smtp_config.starttls:
                        smtp_client.starttls(context=self._build_ssl_context())
                    self._authenticate_if_needed(smtp_client)
                    smtp_client.send_message(message)

            return EmailSendResult(
                provider=EmailProviderType.SMTP,
                accepted_recipients=recipients,
            )

        except Exception as error:
            raise BusinessProcessingError("Failed to send message over SMTP", str(error))

    def _resolve_sender(self) -> str:
        sender = self._smtp_config.from_address or self._provider_config.default_sender
        if not sender:
            raise BusinessProcessingError("No sender configured for SMTP")
        return sender

    def _authenticate_if_needed(self, smtp_client):
        if self._smtp_config.username:
            smtp_client.login(self._smtp_config.username, self._smtp_config.password or "")

    def _build_ssl_context(self):
        context = ssl.create_default_context()
        if self._smtp_config.allow_insecure_tls:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        return context

    def _build_message(self, sender: str, recipients: List[str], request: EmailSendRequest) -> EmailMessage:
        message = EmailMessage()
        message["From"] = sender
        message["To"] = ", ".join(recipients)
        message["Subject"] = request.message.subject

        reply_to = request.message.reply_to or self._provider_config.default_reply_to
        if reply_to:
            message["Reply-To"] = reply_to

        message.set_content(request.message.text_body)

        if request.message.html_body:
            message.add_alternative(request.message.html_body, subtype="html")

        return message
