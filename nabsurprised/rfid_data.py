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


@unique
class TypeEnum(Enum):
    SURPRISE = 0
    CARROT = 1
    BIRTHDAY = 2
    AUTOPROMO = 3
    VALENTINE = 4


TYPE_NAMES = {
    TypeEnum.SURPRISE: "surprise",
    TypeEnum.CARROT: "carrot",
    TypeEnum.BIRTHDAY: "birthday",
    TypeEnum.AUTOPROMO: "autopromo",
    TypeEnum.VALENTINE: "02-14",
}


def serialize(lang_code, type_name):
    encoded_lang = LangEnum.DEFAULT
    for lang, code in LANG_CODES.items():
        if code == lang_code:
            encoded_lang = lang
    encoded_type = TypeEnum.SURPRISE
    for type, name in TYPE_NAMES.items():
        if name == type_name:
            encoded_type = type
    return bytes([encoded_lang.value, encoded_type.value])


def unserialize(data):
    type = TypeEnum.SURPRISE
    lang = LangEnum.DEFAULT
    if len(data) >= 2:
        try:
            lang = LangEnum(data[0])
        except ValueError:
            pass
        try:
            type = TypeEnum(data[1])
        except ValueError:
            pass
    type_name = TYPE_NAMES[type]
    lang_code = LANG_CODES[lang]
    return lang_code, type_name
