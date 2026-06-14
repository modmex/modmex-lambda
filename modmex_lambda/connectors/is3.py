from abc import ABC, abstractmethod
from typing import Any, Dict

class IS3Connector(ABC):
    bucket_name: str

    @property
    def client(self) -> Any:
        """Returns the S3 client"""
        raise NotImplementedError("client property must be implemented")

    @abstractmethod
    def put_object(self, input_params: Dict[str, Any]) -> Dict[str, Any]:
        """Uploads an object to the bucket"""
        raise NotImplementedError("put_object method must be implemented")

    @abstractmethod
    def get_object(self, input_params: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieves an object from the bucket"""
        raise NotImplementedError("get_object method must be implemented")

    @abstractmethod
    def list_objects(self, input_params: Dict[str, Any]) -> Dict[str, Any]:
        """Lists objects in the bucket"""
        raise NotImplementedError("list_objects method must be implemented")

    @abstractmethod
    def delete_object(self, input_params: Dict[str, Any]) -> Dict[str, Any]:
        """Deletes an object from the bucket"""
        raise NotImplementedError("delete_object method must be implemented")
