from flask import Blueprint
from flask import request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_success
from app.business.cases import cases_exists
from app.business.emailing.ingestion import classify_inbound_message
from app.business.emailing.ingestion import inbound_email_from_payload
from app.business.emailing.ingestion_actions import process_inbound_email
from app.models.authorization import Permissions
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


emails_blueprint = Blueprint("emails", __name__, url_prefix="/emails")


@emails_blueprint.post("/ingestion/classify")
@ac_api_requires(Permissions.server_administrator)
def classify_inbound_email():
    if not request.is_json:
        return response_api_error("Invalid request")

    try:
        inbound_email = inbound_email_from_payload(request.get_json())
        action = classify_inbound_message(inbound_email)

        case_exists = None
        if action.case_id is not None:
            case_exists = cases_exists(action.case_id)

        return response_api_success(
            {
                "action_type": action.action_type.value,
                "case_id": action.case_id,
                "reason": action.reason,
                "payload": action.payload,
                "case_exists": case_exists,
            }
        )
    except ValueError:
        return response_api_error("Invalid source_provider value")
    except BusinessProcessingError as error:
        return response_api_error(error.get_message(), data=error.get_data())


@emails_blueprint.post("/ingestion/process")
@ac_api_requires(Permissions.server_administrator)
def process_inbound_email_route():
    if not request.is_json:
        return response_api_error("Invalid request")

    try:
        inbound_email = inbound_email_from_payload(request.get_json())
        result = process_inbound_email(inbound_email)
        return response_api_created(result)
    except ValueError:
        return response_api_error("Invalid source_provider value")
    except ObjectNotFoundError:
        return response_api_error("Case not found")
    except BusinessProcessingError as error:
        return response_api_error(error.get_message(), data=error.get_data())
