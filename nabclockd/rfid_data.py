"""
Serialize & unserialize RFID application data
"""
from enum import Enum, unique


@unique
class TypeEnum(Enum):
    SLEEP = 0
    WAKEUP = 1


TYPE_NAMES = {
    TypeEnum.SLEEP: "sleep",
    TypeEnum.WAKEUP: "wakeup",
}


def serialize(type_name: str) -> bytes:
    encoded_type = TypeEnum.SLEEP
    for type, name in TYPE_NAMES.items():
        if name == type_name:
            encoded_type = type
    return bytes([encoded_type.value])


def unserialize(data: bytes) -> str:
    type = TypeEnum.SLEEP
    if len(data) >= 1:
        try:
            type = TypeEnum(data[0])
        except ValueError:
            pass
    type_name = TYPE_NAMES[type]
    return type_name
