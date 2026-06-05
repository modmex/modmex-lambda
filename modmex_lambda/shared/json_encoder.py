from json import JSONEncoder as BaseJSONEncoder
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum


class JSONEncoder(BaseJSONEncoder):
    
    def default(self, obj: object) -> object:
        
        if is_modmex(obj):
            return obj.model_dump_json()
        
        if is_dataclass(obj):
            return dataclass_to_dict(obj)
        
        if is_pydantic(obj):
            return obj.model_dump_json()
        
        if isinstance(obj, Enum):
            return obj.value
    
        if isinstance(obj, datetime):
            return obj.isoformat()
    
        if isinstance(obj, date):
            return obj.isoformat()
    
        if isinstance(obj, time):
            return obj.isoformat()
    
        if isinstance(obj, timedelta):
            return obj.total_seconds()
    
        if isinstance(obj, Decimal):
            return float(obj)
    
        return super().default(obj)
    

def is_dataclass(obj) -> bool:
    return hasattr(obj, "__dataclass_fields__")

def is_modmex(obj) -> bool:
    return hasattr(obj, "model_dump_json")

def is_pydantic(obj) -> bool:
    return hasattr(obj, "model_dump_json")

def dataclass_to_dict(obj) -> dict:
    import dataclasses

    return dataclasses.asdict(obj)