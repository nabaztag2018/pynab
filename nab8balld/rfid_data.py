"""
Serialize & unserialize RFID application data
"""
from enum import Enum, unique


@unique
class LangEnum(Enum):
    DEFAULT = 0
    FR_FR = 1
    DE_DE = 2
    EN_US = 3
    EN_GB = 4
    IT_IT = 5
    ES_ES = 6
    JA_JP = 7
    PT_BR = 8


LANG_CODES = {
    LangEnum.DEFAULT: "default",
    LangEnum.FR_FR: "fr_FR",
    LangEnum.DE_DE: "de_DE",
    LangEnum.EN_US: "en_US",
    LangEnum.EN_GB: "en_GB",
    LangEnum.IT_IT: "it_IT",
    LangEnum.ES_ES: "es_ES",
    LangEnum.JA_JP: "ja_JP",
    LangEnum.PT_BR: "pt_BR",
}


def serialize(lang_code):
    encoded_lang = LangEnum.DEFAULT
    for lang, code in LANG_CODES.items():
        if code == lang_code:
            encoded_lang = lang
    return bytes([encoded_lang.value])


def unserialize(data):
    lang = LangEnum.DEFAULT
    if len(data) >= 1:
        try:
            lang = LangEnum(data[0])
        except ValueError:
            pass  # assume default
    lang_code = LANG_CODES[lang]
    return lang_code
