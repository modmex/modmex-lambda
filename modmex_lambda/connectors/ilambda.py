from abc import ABC, abstractmethod
from typing import Any, Dict


class ILambdaConnector(ABC):
    @property
    def client(self) -> Any:
        """Returns the Lambda client"""
        raise NotImplementedError("client property must be implemented")

    @abstractmethod
    def invoke(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Invokes a Lambda function"""
        raise NotImplementedError("invoke method must be implemented")
