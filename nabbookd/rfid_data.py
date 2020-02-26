"""
Serialize & unserialize RFID application data
"""
import re


def serialize(voice, isbn):
    isbn.replace("-", "")
    if not re.match(r"^[0-9]{10}(?:[0-9]{3})?$", isbn):
        return b""
    if voice == "" or "/" in voice or voice.startswith("."):
        return b""
    formatted = voice + "/" + isbn
    return formatted.encode()


def unserialize(data):
    splitted = data.decode().split("/")
    if len(splitted) != 2:
        return None
    voice, isbn = splitted
    if voice == "" or "/" in voice or voice.startswith("."):
        return None
    if not re.match(r"^[0-9]{10}(?:[0-9]{3})?$", isbn):
        return None
    return voice, isbn
