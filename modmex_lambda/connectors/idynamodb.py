from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable

class IDynamodbConnector(ABC):
    table_name: str
    retry_config: Dict[str, Any]

    @property
    def client(self) -> Any:
        """Returns the DynamoDB resource"""
        raise NotImplementedError("client property must be implemented")

    @abstractmethod
    def get(self, input_params: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieves an item from the table"""
        raise NotImplementedError("get method must be implemented")

    @abstractmethod
    def update(self, input_params: Dict[str, Any]) -> Dict[str, Any]:
        """Updates an item in the table"""
        raise NotImplementedError("update method must be implemented")

    @abstractmethod
    def put(self, input_params: Dict[str, Any]) -> Dict[str, Any]:
        """Puts an item into the table"""
        raise NotImplementedError("put method must be implemented")

    @abstractmethod
    def query(self, input_params: Dict[str, Any]) -> Dict[str, Any]:
        """Queries items from the table"""
        raise NotImplementedError("query method must be implemented")

    @abstractmethod
    def query_all(self, input_params: Dict[str, Any]) -> list[Dict[str, Any]]:
        """Queries all items, handling pagination"""
        raise NotImplementedError("query_all method must be implemented")

    @abstractmethod
    def query_page(self, input_params: Dict[str, Any]) -> Dict[str, Any]:
        """Queries one page of items"""
        raise NotImplementedError("query_page method must be implemented")

    @abstractmethod
    def scan(self, input_params: Dict[str, Any]) -> Dict[str, Any]:
        """Scans one page of items"""
        raise NotImplementedError("scan method must be implemented")

    @abstractmethod
    def batch_get(self, input_params: Dict[str, Any]) -> Dict[str, Any]:
        """Performs a batch get operation"""
        raise NotImplementedError("batch_get method must be implemented")

    @abstractmethod
    def bulk_insert(self, items: Iterable[Dict[str, Any]]) -> None:
        """Inserts multiple items using batch writer"""
        raise NotImplementedError("bulk_insert method must be implemented")

    @abstractmethod
    def bulk_delete(self, items: Iterable[Dict[str, Any]]) -> None:
        """Deletes multiple items using batch writer"""
        raise NotImplementedError("bulk_delete method must be implemented")


class DynamoDbResource(ABC):

    @abstractmethod
    def Table(self, name: str):
        raise NotImplementedError()
