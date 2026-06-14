from abc import ABC, abstractmethod
from typing import Any, Dict

class ISNSConnector(ABC):
    topic_arn: str

    @property
    def client(self) -> Any:
        """Returns the SNS client"""
        raise NotImplementedError("client property must be implemented")

    @abstractmethod
    def publish(self, input_params: Dict[str, Any]) -> Dict[str, Any]:
        """Publishes a message to the SNS topic"""
        raise NotImplementedError("publish method must be implemented")

    @abstractmethod
    def publish_batch(self, input_params: Dict[str, Any]) -> Dict[str, Any]:
        """Publishes a batch of messages to the SNS topic"""
        raise NotImplementedError("publish_batch method must be implemented")
