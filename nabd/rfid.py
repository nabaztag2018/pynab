import abc
from enum import IntEnum, IntFlag
from typing import Callable, Optional

import nabairqualityd
import nabbookd
import nabclockd
import nabiftttd
import nabradio
import nabsurprised
import nabtaichid
import nabweatherd
import nabwebhook


class TagFlags(IntFlag):
    CLEAR = 1
    FORMATTED = 2
    READONLY = 4
    FOREIGN_DATA = 8
    UNKNOWN_PICC = 16
    REMOVED = 128


class TagTechnology(IntEnum):
    ISO14443A = 1
    ISO14443A_T2T = 2
    ISO14443A_MIFARE_CLASSIC = 3
    ISO14443A_NFCDEP = 4
    ISO14443A_T4T = 6
    ISO14443A_T4T_NFCDEP = 7
    ISO14443A_T1T = 8
    ISO14443B = 16
    ST25TB = 17


TAG_APPLICATION_NONE = 255
TAG_APPLICATIONS = {
    TAG_APPLICATION_NONE: "none",
    1: "nab8balld",
    2: "nabairqualityd",
    3: "nabblockly",
    nabbookd.NABAZTAG_RFID_APPLICATION_ID: "nabbookd",  # 4
    nabclockd.NABAZTAG_RFID_APPLICATION_ID: "nabclockd",  # 5
    6: "nabmastodond",
    nabsurprised.NABAZTAG_RFID_APPLICATION_ID: "nabsurprised",  # 7
    nabtaichid.NABAZTAG_RFID_APPLICATION_ID: "nabtaichid",  # 8
    nabweatherd.NABAZTAG_RFID_APPLICATION_ID: "nabweatherd",  # 9
    nabiftttd.NABAZTAG_RFID_APPLICATION_ID: "nabiftttd",  # 10
    nabairqualityd.NABAZTAG_RFID_APPLICATION_ID: "nabairqualityd",  # 11
    nabradio.NABAZTAG_RFID_APPLICATION_ID: "nabradio",  # 12
    nabwebhook.NABAZTAG_RFID_APPLICATION_ID: "nabwebhook",  # 13
}

DEFAULT_RFID_TIMEOUT = 20.0


class Rfid(object, metaclass=abc.ABCMeta):
    """Interface for rfid reader"""

    @abc.abstractmethod
    def on_detect(
        self,
        loop,
        callback: Callable[
            [TagTechnology, bytes, int, int, bytes, TagFlags, dict], None
        ],
    ) -> None:
        """
        Define the callback for rfid events.
        callback is cb(tech, uid, picture, app, data, support, tag_info) with
        uid being the RFID's UID, picture, app and data being the encoded tag's
        picture, app and data unless the tag is not encoded (in which case the
        callback gets None).
        flags describes support for this tag, inferred from the UID and
        reading few blocks.
        tag_info contains additional info that applications may use.
        The callback is called on the provided event loop, with
        loop.call_soon_threadsafe.
        Calling this method enables the reader.
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    async def write(
        self,
        tech: TagTechnology,
        uid: bytes,
        picture: int,
        app: int,
        data: Optional[bytes],
    ):
        """
        Write the tag with the given uid with the specified picture, app and
        bytes. picture and app should be within 0-255, data should be 32 bytes
        maximum.
        Cancelleable (would rethrow a CancelledError)
        Returns True if write succeeded (written data matches what is read)
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    def enable_polling(self):
        """
        Enable detection of tags.
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    def disable_polling(self):
        """
        Disable detection of tags.
        """
        raise NotImplementedError("Should have implemented")
