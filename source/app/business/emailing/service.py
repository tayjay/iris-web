from typing import Iterable
from typing import Optional

from app.business.emailing.config import load_email_provider_config
from app.business.emailing.config import load_exchange_graph_config
from app.business.emailing.config import load_smtp_config
from app.business.emailing.providers.exchange_graph_provider import ExchangeGraphEmailProvider
from app.business.emailing.providers.smtp_provider import SmtpEmailProvider
from app.business.emailing.recipients import resolve_case_contact_recipients
from app.business.emailing.recipients import resolve_task_contact_recipients
from app.business.emailing.types import EmailMessageInput
from app.business.emailing.types import EmailProviderType
from app.business.emailing.types import EmailScope
from app.business.emailing.types import EmailScopeType
from app.business.emailing.types import EmailSendRequest
from app.business.emailing.types import EmailSendResult
from app.models.errors import BusinessProcessingError


class EmailService:

    def __init__(self):
        self._provider_config = load_email_provider_config()

    def send_case_email(
        self,
        case_identifier: int,
        message: EmailMessageInput,
        contact_identifiers: Optional[Iterable[int]] = None,
    ) -> EmailSendResult:
        recipients = resolve_case_contact_recipients(case_identifier, contact_identifiers)
        return self._send(
            EmailSendRequest(
                scope=EmailScope(scope_type=EmailScopeType.CASE, case_id=case_identifier),
                recipients=recipients,
                message=message,
            )
        )

    def send_task_email(
        self,
        case_identifier: int,
        task_identifier: int,
        message: EmailMessageInput,
        contact_identifiers: Optional[Iterable[int]] = None,
    ) -> EmailSendResult:
        recipients = resolve_task_contact_recipients(task_identifier, contact_identifiers)
        return self._send(
            EmailSendRequest(
                scope=EmailScope(
                    scope_type=EmailScopeType.TASK,
                    case_id=case_identifier,
                    task_id=task_identifier,
                ),
                recipients=recipients,
                message=message,
            )
        )

    def _send(self, request: EmailSendRequest) -> EmailSendResult:
        if not request.recipients:
            raise BusinessProcessingError("No recipients resolved for email request")

        if len(request.recipients) > self._provider_config.max_recipients:
            raise BusinessProcessingError(
                "Too many recipients for a single email request",
                f"max={self._provider_config.max_recipients}",
            )

        provider = self._build_provider()
        return provider.send(request)

    def _build_provider(self):
        if self._provider_config.provider == EmailProviderType.EXCHANGE_GRAPH:
            return ExchangeGraphEmailProvider(
                provider_config=self._provider_config,
                graph_config=load_exchange_graph_config(),
            )

        if self._provider_config.provider == EmailProviderType.SMTP:
            return SmtpEmailProvider(
                provider_config=self._provider_config,
                smtp_config=load_smtp_config(),
            )

        raise BusinessProcessingError("Unsupported EMAIL_PROVIDER", self._provider_config.provider.value)
