from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
import re
from typing import List
from typing import Optional

from app.business.emailing.config import load_ingestion_config
from app.business.emailing.types import InboundEmail
from app.business.emailing.types import IngestionAction
from app.business.emailing.types import IngestionActionType
from app.business.emailing.types import IngestionProviderType
from app.models.errors import BusinessProcessingError


@dataclass
class IngestionBatch:
    provider: IngestionProviderType
    items: List[InboundEmail]


class InboundEmailProvider(ABC):

    @abstractmethod
    def fetch(self) -> IngestionBatch:
        raise NotImplementedError()


class ImapInboundEmailProvider(InboundEmailProvider):

    def fetch(self) -> IngestionBatch:
        # Placeholder for IMAP integration; wiring and credentials handling comes later.
        return IngestionBatch(provider=IngestionProviderType.IMAP, items=[])


class GraphInboundEmailProvider(InboundEmailProvider):

    def fetch(self) -> IngestionBatch:
        # Placeholder for Graph subscription/webhook polling implementation.
        return IngestionBatch(provider=IngestionProviderType.GRAPH_SUBSCRIPTION, items=[])


def build_inbound_provider() -> Optional[InboundEmailProvider]:
    configuration = load_ingestion_config()
    if not configuration.enabled:
        return None

    if configuration.provider == IngestionProviderType.IMAP:
        return ImapInboundEmailProvider()

    if configuration.provider == IngestionProviderType.GRAPH_SUBSCRIPTION:
        return GraphInboundEmailProvider()

    return None


def classify_inbound_message(message: InboundEmail) -> IngestionAction:
    # Keep this deterministic and explicit until case/alert wiring is in place.
    lowered_subject = (message.subject or "").lower()

    if "[case:" in lowered_subject:
        case_identifier = _extract_case_identifier(lowered_subject)
        return IngestionAction(
            action_type=IngestionActionType.UPDATE_CASE,
            case_id=case_identifier,
            reason="subject contains [case: marker]",
        )

    if "[new-alert]" in lowered_subject:
        customer_identifier = _extract_customer_identifier(lowered_subject)
        return IngestionAction(
            action_type=IngestionActionType.CREATE_ALERT,
            reason="subject contains [new-alert]",
            payload={
                "customer_id": customer_identifier,
            },
        )

    return IngestionAction(action_type=IngestionActionType.NOOP, reason="message did not match routing rules")


def inbound_email_from_payload(payload: dict) -> InboundEmail:
    if not isinstance(payload, dict):
        raise BusinessProcessingError("Inbound payload should be a JSON object")

    source_provider = payload.get("source_provider", IngestionProviderType.IMAP.value)
    provider = IngestionProviderType(str(source_provider).strip().lower())

    to_addresses = payload.get("to_addresses") or []
    cc_addresses = payload.get("cc_addresses") or []

    if not isinstance(to_addresses, list) or not isinstance(cc_addresses, list):
        raise BusinessProcessingError("to_addresses and cc_addresses must be arrays")

    subject = str(payload.get("subject") or "").strip()
    from_address = str(payload.get("from_address") or "").strip()
    if not subject or not from_address:
        raise BusinessProcessingError("subject and from_address are required for ingestion")

    return InboundEmail(
        source_provider=provider,
        message_id=str(payload.get("message_id") or "").strip() or None,
        subject=subject,
        from_address=from_address,
        to_addresses=[str(address).strip() for address in to_addresses if str(address).strip()],
        cc_addresses=[str(address).strip() for address in cc_addresses if str(address).strip()],
        text_body=str(payload.get("text_body") or "").strip() or None,
        html_body=str(payload.get("html_body") or "").strip() or None,
        raw_headers=payload.get("raw_headers") if isinstance(payload.get("raw_headers"), dict) else {},
    )


def _extract_case_identifier(lowered_subject: str) -> Optional[int]:
    match = re.search(r"\[case:(\d+)\]", lowered_subject)
    if not match:
        return None

    try:
        return int(match.group(1))
    except ValueError:
        return None


def _extract_customer_identifier(lowered_subject: str) -> Optional[int]:
    match = re.search(r"\[customer:(\d+)\]", lowered_subject)
    if not match:
        return None

    try:
        return int(match.group(1))
    except ValueError:
        return None
