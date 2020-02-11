"""
Serialize & unserialize RFID application data
"""


def serialize(type):
    if type == "tomorrow":
        return b"\x02"
    else:
        return b"\x01"


def unserialize(data):
    if len(data) > 0 and data[0] == 2:
        return "tomorrow"
    return "today"
