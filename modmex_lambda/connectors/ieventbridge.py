from abc import ABC, abstractmethod
from typing import Any, Dict

class IEventBridgeConnector(ABC):
    
    @property
    def client(self) -> Any:
        """Returns the EventBridge client"""
        raise NotImplementedError("client property must be implemented")

    @abstractmethod
    def put_events(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Puts events into EventBridge"""
        raise NotImplementedError("put_events method must be implemented")
