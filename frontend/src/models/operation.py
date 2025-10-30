from enum import Enum


class OperationMode(Enum):
    NORMAL = "normal"
    EXTENDED = "extended"

    def __init__(self, typename: str):
        self._typename = typename

    @property
    def typename(self) -> str:
        return self._typename
    
    def __str__(self) -> str:
        return self._typename
    
    @classmethod
    def from_str(cls, name: str):
        name = name.strip().lower()
        for mode in cls:
            if mode.typename == name:
                return mode
            
        raise ValueError(f"Unknown OperationMode: {name!r}")
