"""Dataclass Action - Inmutable."""
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Optional
from enum import Enum

class ActionType(str, Enum):
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    TYPE_TEXT = "type"
    KEY_PRESS = "key"
    KEY_COMBINATION = "key_combination"
    WAIT = "wait"
    VALIDATE = "validate"

@dataclass(frozen=True)
class Action:
    """Acción inmutable con metadatos completos."""
    type: ActionType
    timestamp: datetime
    wait_before: float = 0.0
    
    selector: Optional[Dict[str, str]] = None
    position: Optional[Dict[str, int]] = None
    
    text: Optional[str] = None
    key_code: Optional[str] = None
    combination: Optional[str] = None
    clipboard_content: Optional[str] = None
    validation_rule: Optional[str] = None
    
    app_context: Optional[Dict] = None
    modifiers: Optional[Dict[str, bool]] = None
    element_info: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['type'] = self.type.value
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Action":
        type_str = data['type']
        if type_str == "type_text":
            type_str = "type"
        data['type'] = ActionType(type_str)
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)
