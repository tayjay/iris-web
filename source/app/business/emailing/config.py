from dataclasses import dataclass
from typing import Optional

from app import app
from app.business.emailing.types import EmailProviderType
from app.business.emailing.types import IngestionProviderType


@dataclass
class EmailProviderConfig:
    provider: EmailProviderType
    default_sender: str
    default_reply_to: Optional[str]
    send_timeout_seconds: int
    max_recipients: int


@dataclass
class SmtpEmailConfig:
    host: str
    port: int
    username: Optional[str]
    password: Optional[str]
    starttls: bool
    use_ssl: bool
    from_address: Optional[str]
    allow_insecure_tls: bool


@dataclass
class ExchangeGraphEmailConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    sender_mailbox: str
    scope: str


@dataclass
class IngestionConfig:
    enabled: bool
    provider: IngestionProviderType
    imap_host: Optional[str]
    imap_port: int
    imap_use_ssl: bool
    imap_username: Optional[str]
    imap_password: Optional[str]
    imap_folder: str
    graph_subscription_id: Optional[str]
    graph_client_state: Optional[str]


TRUE_SET = {"1", "true", "yes", "on"}


def _as_bool(value) -> bool:
    return str(value).strip().lower() in TRUE_SET


def load_email_provider_config() -> EmailProviderConfig:
    provider_name = (app.config.get("EMAIL_PROVIDER") or EmailProviderType.SMTP.value).strip().lower()
    provider = EmailProviderType(provider_name)

    return EmailProviderConfig(
        provider=provider,
        default_sender=(app.config.get("EMAIL_DEFAULT_SENDER") or "").strip(),
        default_reply_to=(app.config.get("EMAIL_DEFAULT_REPLY_TO") or "").strip() or None,
        send_timeout_seconds=int(app.config.get("EMAIL_SEND_TIMEOUT_SECONDS") or 15),
        max_recipients=int(app.config.get("EMAIL_MAX_RECIPIENTS") or 100),
    )


def load_smtp_config() -> SmtpEmailConfig:
    return SmtpEmailConfig(
        host=(app.config.get("EMAIL_SMTP_HOST") or "").strip(),
        port=int(app.config.get("EMAIL_SMTP_PORT") or 587),
        username=(app.config.get("EMAIL_SMTP_USERNAME") or "").strip() or None,
        password=(app.config.get("EMAIL_SMTP_PASSWORD") or "").strip() or None,
        starttls=_as_bool(app.config.get("EMAIL_SMTP_STARTTLS")),
        use_ssl=_as_bool(app.config.get("EMAIL_SMTP_USE_SSL")),
        from_address=(app.config.get("EMAIL_SMTP_FROM") or "").strip() or None,
        allow_insecure_tls=_as_bool(app.config.get("EMAIL_ALLOW_INSECURE_TLS")),
    )


def load_exchange_graph_config() -> ExchangeGraphEmailConfig:
    return ExchangeGraphEmailConfig(
        tenant_id=(app.config.get("EMAIL_GRAPH_TENANT_ID") or "").strip(),
        client_id=(app.config.get("EMAIL_GRAPH_CLIENT_ID") or "").strip(),
        client_secret=(app.config.get("EMAIL_GRAPH_CLIENT_SECRET") or "").strip(),
        sender_mailbox=(app.config.get("EMAIL_GRAPH_SENDER_MAILBOX") or "").strip(),
        scope=(app.config.get("EMAIL_GRAPH_SCOPE") or "https://graph.microsoft.com/.default").strip(),
    )


def load_ingestion_config() -> IngestionConfig:
    provider_name = (app.config.get("EMAIL_INGESTION_PROVIDER") or IngestionProviderType.IMAP.value).strip().lower()
    provider = IngestionProviderType(provider_name)

    return IngestionConfig(
        enabled=_as_bool(app.config.get("EMAIL_INGESTION_ENABLED")),
        provider=provider,
        imap_host=(app.config.get("EMAIL_INGESTION_IMAP_HOST") or "").strip() or None,
        imap_port=int(app.config.get("EMAIL_INGESTION_IMAP_PORT") or 993),
        imap_use_ssl=_as_bool(app.config.get("EMAIL_INGESTION_IMAP_USE_SSL")),
        imap_username=(app.config.get("EMAIL_INGESTION_IMAP_USERNAME") or "").strip() or None,
        imap_password=(app.config.get("EMAIL_INGESTION_IMAP_PASSWORD") or "").strip() or None,
        imap_folder=(app.config.get("EMAIL_INGESTION_IMAP_FOLDER") or "INBOX").strip(),
        graph_subscription_id=(app.config.get("EMAIL_INGESTION_GRAPH_SUBSCRIPTION_ID") or "").strip() or None,
        graph_client_state=(app.config.get("EMAIL_INGESTION_GRAPH_CLIENT_STATE") or "").strip() or None,
    )
