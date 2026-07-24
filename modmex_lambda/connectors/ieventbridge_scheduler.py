from abc import ABC, abstractmethod
from typing import Any, Dict


class IEventBridgeSchedulerConnector(ABC):
    """Schedules one-time EventBridge deliveries."""

    @property
    def client(self) -> Any:
        """Returns the EventBridge Scheduler client."""
        raise NotImplementedError("client property must be implemented")

    @abstractmethod
    def create_schedule(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a one-time schedule."""
        raise NotImplementedError("create_schedule method must be implemented")

    @abstractmethod
    def delete_schedule(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Deletes a previously created schedule."""
        raise NotImplementedError("delete_schedule method must be implemented")
