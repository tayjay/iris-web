from abc import ABC
from abc import abstractmethod

from app.business.emailing.types import EmailSendRequest
from app.business.emailing.types import EmailSendResult


class EmailProvider(ABC):

    @abstractmethod
    def send(self, request: EmailSendRequest) -> EmailSendResult:
        raise NotImplementedError()
