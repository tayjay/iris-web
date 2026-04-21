from typing import Dict

import requests
from azure.identity import ClientSecretCredential

from app.business.emailing.config import EmailProviderConfig
from app.business.emailing.config import ExchangeGraphEmailConfig
from app.business.emailing.providers.base import EmailProvider
from app.business.emailing.types import EmailProviderType
from app.business.emailing.types import EmailSendRequest
from app.business.emailing.types import EmailSendResult
from app.models.errors import BusinessProcessingError


class ExchangeGraphEmailProvider(EmailProvider):

    def __init__(self, provider_config: EmailProviderConfig, graph_config: ExchangeGraphEmailConfig):
        self._provider_config = provider_config
        self._graph_config = graph_config

    def send(self, request: EmailSendRequest) -> EmailSendResult:
        self._validate_configuration()

        token = self._get_access_token()
        endpoint = f"https://graph.microsoft.com/v1.0/users/{self._graph_config.sender_mailbox}/sendMail"

        response = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=self._build_payload(request),
            timeout=self._provider_config.send_timeout_seconds,
        )

        if response.status_code != 202:
            raise BusinessProcessingError(
                "Exchange Graph sendMail failed",
                f"status={response.status_code}, body={response.text}",
            )

        return EmailSendResult(
            provider=EmailProviderType.EXCHANGE_GRAPH,
            accepted_recipients=[recipient.email for recipient in request.recipients],
            provider_message_id=response.headers.get("request-id"),
        )

    def _validate_configuration(self):
        required = {
            "EMAIL_GRAPH_TENANT_ID": self._graph_config.tenant_id,
            "EMAIL_GRAPH_CLIENT_ID": self._graph_config.client_id,
            "EMAIL_GRAPH_CLIENT_SECRET": self._graph_config.client_secret,
            "EMAIL_GRAPH_SENDER_MAILBOX": self._graph_config.sender_mailbox,
        }

        missing = [key for key, value in required.items() if not value]
        if missing:
            raise BusinessProcessingError("Missing Exchange Graph configuration", ", ".join(missing))

    def _get_access_token(self) -> str:
        credential = ClientSecretCredential(
            tenant_id=self._graph_config.tenant_id,
            client_id=self._graph_config.client_id,
            client_secret=self._graph_config.client_secret,
        )

        token = credential.get_token(self._graph_config.scope)
        return token.token

    def _build_payload(self, request: EmailSendRequest) -> Dict:
        body = {
            "contentType": "HTML" if request.message.html_body else "Text",
            "content": request.message.html_body or request.message.text_body,
        }

        message_payload = {
            "subject": request.message.subject,
            "body": body,
            "toRecipients": [{"emailAddress": {"address": recipient.email}} for recipient in request.recipients],
        }

        reply_to = request.message.reply_to or self._provider_config.default_reply_to
        if reply_to:
            message_payload["replyTo"] = [{"emailAddress": {"address": reply_to}}]

        return {
            "message": message_payload,
            "saveToSentItems": True,
        }
