from abc import ABC, abstractmethod
from typing import Any, Dict


class ICloudWatchConnector(ABC):
    @property
    def client(self) -> Any:
        """Returns the CloudWatch client"""
        raise NotImplementedError("client property must be implemented")

    @abstractmethod
    def put(self, input_params: Dict[str, Any]) -> Dict[str, Any]:
        """Puts metric data into CloudWatch"""
        raise NotImplementedError("put method must be implemented")
