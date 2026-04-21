from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from typing import Dict
from typing import List
from typing import Optional


class EmailProviderType(str, Enum):
    SMTP = "smtp"
    EXCHANGE_GRAPH = "exchange_graph"


class EmailScopeType(str, Enum):
    CASE = "case"
    TASK = "task"


@dataclass
class EmailScope:
    scope_type: EmailScopeType
    case_id: int
    task_id: Optional[int] = None


@dataclass
class EmailRecipient:
    email: str
    contact_id: Optional[int] = None
    display_name: Optional[str] = None


@dataclass
class EmailMessageInput:
    subject: str
    text_body: str
    html_body: Optional[str] = None
    reply_to: Optional[str] = None


@dataclass
class EmailRenderInput:
    template_reference: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RenderedEmailMessage:
    subject: str
    text_body: str
    html_body: Optional[str] = None


@dataclass
class EmailSendRequest:
    scope: EmailScope
    recipients: List[EmailRecipient]
    message: EmailMessageInput
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmailSendResult:
    provider: EmailProviderType
    accepted_recipients: List[str] = field(default_factory=list)
    rejected_recipients: List[str] = field(default_factory=list)
    provider_message_id: Optional[str] = None


class IngestionProviderType(str, Enum):
    IMAP = "imap"
    GRAPH_SUBSCRIPTION = "graph_subscription"


@dataclass
class InboundEmail:
    source_provider: IngestionProviderType
    message_id: Optional[str]
    subject: str
    from_address: str
    to_addresses: List[str]
    cc_addresses: List[str] = field(default_factory=list)
    received_at: Optional[datetime] = None
    text_body: Optional[str] = None
    html_body: Optional[str] = None
    raw_headers: Dict[str, str] = field(default_factory=dict)


class IngestionActionType(str, Enum):
    UPDATE_CASE = "update_case"
    CREATE_ALERT = "create_alert"
    NOOP = "noop"


@dataclass
class IngestionAction:
    action_type: IngestionActionType
    case_id: Optional[int] = None
    reason: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
