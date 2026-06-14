from abc import ABC, abstractmethod
from typing import Any, Dict


class ISQSConnector(ABC):
    queue_url: str

    @property
    def client(self) -> Any:
        """Returns the SQS client"""
        raise NotImplementedError("client property must be implemented")

    @abstractmethod
    def send_message(self, input_params: Dict[str, Any]) -> Dict[str, Any]:
        """Sends a message to SQS"""
        raise NotImplementedError("send_message method must be implemented")

    @abstractmethod
    def send_message_batch(self, input_params: Dict[str, Any]) -> Dict[str, Any]:
        """Sends a message batch to SQS"""
        raise NotImplementedError("send_message_batch method must be implemented")
