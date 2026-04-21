import os
from typing import Dict

from app import app
from app.business.emailing.types import RenderedEmailMessage
from app.iris_engine.utils.common import IrisJinjaEnv
from app.models.errors import BusinessProcessingError


def render_email_template(template_reference: str, context: Dict, subject: str = "") -> RenderedEmailMessage:
    template_root = (app.config.get("EMAIL_TEMPLATE_ROOT") or "email").strip().strip("/")
    template_path = os.path.join(app.config["TEMPLATES_PATH"], template_root, template_reference)

    if not os.path.isfile(template_path):
        raise BusinessProcessingError("Email template does not exist", template_path)

    try:
        env = IrisJinjaEnv()
        env.filters = app.jinja_env.filters

        with open(template_path, "r", encoding="utf-8") as template_file:
            template = env.from_string(template_file.read())

        rendered_content = template.render(context or {})
    except Exception as error:
        raise BusinessProcessingError("Failed to render email template", str(error))

    return RenderedEmailMessage(
        subject=subject,
        text_body=rendered_content,
        html_body=None,
    )
