from datetime import datetime
from typing import Dict
from typing import Optional

from app.business.alerts import alerts_create
from app.business.cases import cases_get_by_identifier
from app.business.emailing.ingestion import classify_inbound_message
from app.business.emailing.types import InboundEmail
from app.business.emailing.types import IngestionActionType
from app.business.notes import notes_create
from app.datamgmt.alerts.alerts_db import get_alert_status_by_name
from app.datamgmt.manage.manage_common import search_severity_by_name
from app.models.alerts import Alert
from app.models.alerts import AlertStatus
from app.models.alerts import Severity
from app.models.models import Notes
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


def process_inbound_email(message: InboundEmail) -> Dict:
    action = classify_inbound_message(message)

    if action.action_type == IngestionActionType.UPDATE_CASE:
        if action.case_id is None:
            raise BusinessProcessingError("Inbound message was marked as case update without a case identifier")

        case = cases_get_by_identifier(action.case_id)
        note = _create_note_from_message(message, case.case_id)
        return {
            "action_type": action.action_type.value,
            "case_id": case.case_id,
            "created_note_id": note.note_id,
            "created_note_uuid": str(note.note_uuid),
        }

    if action.action_type == IngestionActionType.CREATE_ALERT:
        customer_identifier = _extract_customer_identifier(action.payload)
        if customer_identifier is None:
            raise BusinessProcessingError("Unable to create alert from inbound email without customer marker")

        alert = _create_alert_from_message(message, customer_identifier)
        return {
            "action_type": action.action_type.value,
            "created_alert_id": alert.alert_id,
            "customer_id": alert.alert_customer_id,
        }

    return {
        "action_type": action.action_type.value,
        "reason": action.reason,
    }


def _create_note_from_message(message: InboundEmail, case_identifier: int) -> Notes:
    note = Notes()
    note.note_title = f"Inbound email: {message.subject[:120]}"
    note.note_content = _format_note_body(message)

    return notes_create(note, case_identifier)


def _format_note_body(message: InboundEmail) -> str:
    text_content = message.text_body or message.html_body or "(No body)"
    return "\n".join(
        [
            f"From: {message.from_address}",
            f"To: {', '.join(message.to_addresses)}",
            f"CC: {', '.join(message.cc_addresses)}" if message.cc_addresses else "CC:",
            "",
            text_content,
        ]
    )


def _extract_customer_identifier(payload: dict) -> Optional[int]:
    customer_identifier = payload.get("customer_id")
    if customer_identifier is None:
        return None

    try:
        return int(customer_identifier)
    except (TypeError, ValueError):
        return None


def _create_alert_from_message(message: InboundEmail, customer_identifier: int) -> Alert:
    severity_identifier = _resolve_default_severity_identifier()
    status_identifier = _resolve_default_status_identifier()

    alert = Alert(
        alert_title=message.subject,
        alert_description=message.text_body or message.html_body or "Inbound email without body",
        alert_source="email_ingestion",
        alert_source_ref=message.message_id,
        alert_source_content={
            "from": message.from_address,
            "to": message.to_addresses,
            "cc": message.cc_addresses,
            "headers": message.raw_headers,
        },
        alert_severity_id=severity_identifier,
        alert_status_id=status_identifier,
        alert_source_event_time=message.received_at or datetime.utcnow(),
        alert_customer_id=customer_identifier,
    )

    return alerts_create(alert=alert, iocs=[], assets=[])


def _resolve_default_severity_identifier() -> int:
    for severity_name in ["Medium", "High", "Low"]:
        severities = search_severity_by_name(severity_name, exact_match=True)
        if severities:
            return severities[0].severity_id

    severity = Severity.query.order_by(Severity.severity_id.asc()).first()
    if not severity:
        raise BusinessProcessingError("No severity is configured")

    return severity.severity_id


def _resolve_default_status_identifier() -> int:
    for status_name in ["Open", "New"]:
        status = get_alert_status_by_name(status_name)
        if status:
            return status.status_id

    status = AlertStatus.query.order_by(AlertStatus.status_id.asc()).first()
    if not status:
        raise BusinessProcessingError("No alert status is configured")

    return status.status_id
