from typing import Iterable
from typing import List
from typing import Optional

from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_tasks_db import get_task
from app.datamgmt.client.client_db import get_client_contacts
from app.business.emailing.types import EmailRecipient
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


def resolve_case_contact_recipients(case_identifier: int, contact_identifiers: Optional[Iterable[int]] = None) -> List[EmailRecipient]:
    case = get_case(case_identifier)
    if not case:
        raise ObjectNotFoundError()

    contacts = get_client_contacts(case.client_id)
    return _convert_contacts_to_recipients(contacts, contact_identifiers)


def resolve_task_contact_recipients(task_identifier: int, contact_identifiers: Optional[Iterable[int]] = None) -> List[EmailRecipient]:
    task = get_task(task_identifier)
    if not task:
        raise ObjectNotFoundError()

    return resolve_case_contact_recipients(task.task_case_id, contact_identifiers)


def _convert_contacts_to_recipients(contacts, contact_identifiers: Optional[Iterable[int]]) -> List[EmailRecipient]:
    selected_ids = set(contact_identifiers or [])
    recipients: List[EmailRecipient] = []

    for contact in contacts:
        if selected_ids and contact.id not in selected_ids:
            continue
        if not contact.contact_email:
            continue

        email_value = contact.contact_email.strip()
        if not email_value:
            continue

        recipients.append(
            EmailRecipient(
                email=email_value,
                contact_id=contact.id,
                display_name=contact.contact_name,
            )
        )

    if selected_ids and not recipients:
        raise BusinessProcessingError("No valid contact recipients found for the selected contacts")

    deduplicated = {}
    for recipient in recipients:
        deduplicated[recipient.email.lower()] = recipient

    return list(deduplicated.values())
