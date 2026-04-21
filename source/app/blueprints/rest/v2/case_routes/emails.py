from flask import Blueprint
from flask import request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.access_controls import ac_fast_check_current_user_has_case_access
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_error
from app.business.emailing import EmailMessageInput
from app.business.emailing import EmailService
from app.business.emailing import render_email_template
from app.business.tasks import tasks_get
from app.models.authorization import CaseAccessLevel
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


case_emails_blueprint = Blueprint(
    "case_emails",
    __name__,
    url_prefix="/<int:case_identifier>/emails",
)

case_task_emails_blueprint = Blueprint(
    "case_task_emails",
    __name__,
    url_prefix="/<int:case_identifier>/tasks/<int:task_identifier>/emails",
)


def _build_message_input_from_payload(request_data):
    subject = str(request_data.get("subject") or "").strip()
    if not subject:
        raise BusinessProcessingError("subject is required")

    text_body = str(request_data.get("text_body") or "").strip()
    html_body = str(request_data.get("html_body") or "").strip() or None
    template_reference = str(request_data.get("template_reference") or "").strip()

    if template_reference:
        template_context = request_data.get("template_context") or {}
        if not isinstance(template_context, dict):
            raise BusinessProcessingError("template_context should be an object")

        rendered_message = render_email_template(
            template_reference=template_reference,
            context=template_context,
            subject=subject,
        )
        if not text_body:
            text_body = rendered_message.text_body
        if not html_body:
            html_body = rendered_message.html_body

    if not text_body and not html_body:
        raise BusinessProcessingError("Either text_body, html_body, or template_reference must be provided")

    return EmailMessageInput(
        subject=subject,
        text_body=text_body or " ",
        html_body=html_body,
        reply_to=str(request_data.get("reply_to") or "").strip() or None,
    )


def _parse_contact_identifiers(request_data):
    contact_identifiers = request_data.get("contact_ids") or []
    if not isinstance(contact_identifiers, list):
        raise BusinessProcessingError("contact_ids should be an array")

    parsed_contact_identifiers = []
    for identifier in contact_identifiers:
        parsed_contact_identifiers.append(int(identifier))

    return parsed_contact_identifiers


@case_emails_blueprint.post("/send")
@ac_api_requires()
def send_case_email(case_identifier):
    if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=case_identifier)

    if not request.is_json:
        return response_api_error("Invalid request")

    try:
        request_data = request.get_json()
        message = _build_message_input_from_payload(request_data)
        contact_identifiers = _parse_contact_identifiers(request_data)

        result = EmailService().send_case_email(
            case_identifier=case_identifier,
            message=message,
            contact_identifiers=contact_identifiers,
        )

        return response_api_created(
            {
                "provider": result.provider.value,
                "accepted_recipients": result.accepted_recipients,
                "rejected_recipients": result.rejected_recipients,
                "provider_message_id": result.provider_message_id,
            }
        )
    except ObjectNotFoundError:
        return response_api_error("Case not found")
    except ValueError:
        return response_api_error("Invalid contact_ids values")
    except BusinessProcessingError as error:
        return response_api_error(error.get_message(), data=error.get_data())


@case_task_emails_blueprint.post("/send")
@ac_api_requires()
def send_task_email(case_identifier, task_identifier):
    if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=case_identifier)

    if not request.is_json:
        return response_api_error("Invalid request")

    try:
        task = tasks_get(task_identifier)
        if task.task_case_id != case_identifier:
            raise ObjectNotFoundError()

        request_data = request.get_json()
        message = _build_message_input_from_payload(request_data)
        contact_identifiers = _parse_contact_identifiers(request_data)

        result = EmailService().send_task_email(
            case_identifier=case_identifier,
            task_identifier=task_identifier,
            message=message,
            contact_identifiers=contact_identifiers,
        )

        return response_api_created(
            {
                "provider": result.provider.value,
                "accepted_recipients": result.accepted_recipients,
                "rejected_recipients": result.rejected_recipients,
                "provider_message_id": result.provider_message_id,
            }
        )
    except ObjectNotFoundError:
        return response_api_error("Task not found")
    except ValueError:
        return response_api_error("Invalid contact_ids values")
    except BusinessProcessingError as error:
        return response_api_error(error.get_message(), data=error.get_data())
