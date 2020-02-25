import abc
from enum import IntFlag
from typing import Callable
import nabbookd
import nabsurprised
import nabtaichid
import nabweatherd


class TagFlags(IntFlag):
    CLEAR = 1
    FORMATTED = 2
    READONLY = 4
    FOREIGN_DATA = 8
    UNKNOWN_PICC = 16
    REMOVED = 128


TAG_APPLICATION_NONE = 255
TAG_APPLICATIONS = {
    TAG_APPLICATION_NONE: "none",
    1: "nab8balld",
    2: "nabairqualityd",
    3: "nabblockly",
    nabbookd.NABAZTAG_RFID_APPLICATION_ID: "nabbookd",  # 4
    5: "nabclockd",
    6: "nabmastodond",
    nabsurprised.NABAZTAG_RFID_APPLICATION_ID: "nabsurprised",  # 7
    nabtaichid.NABAZTAG_RFID_APPLICATION_ID: "nabtaichid",  # 8
    nabweatherd.NABAZTAG_RFID_APPLICATION_ID: "nabweatherd",  # 9
}

DEFAULT_RFID_TIMEOUT = 20.0


class Rfid(object, metaclass=abc.ABCMeta):
    """ Interface for rfid reader """

    @abc.abstractmethod
    def on_detect(
        self,
        loop,
        callback: Callable[[bytes, int, int, bytes, TagFlags], None],
    ) -> None:
        """
        Define the callback for rfid events.
        callback is cb(uid, picture, app, data, support) with uid being the
        RFID's UID, picture, app and data being the encoded tag's picture, app
        and data unless the tag is not encoded (in which case the callback gets
        None).
        flags describes support for this tag, inferred from the UID and
        reading few blocks.
        The callback is called on the provided event loop, with
        loop.call_soon_threadsafe.
        Calling this method enables the reader.
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    async def write(self, uid: bytes, picture: int, app: int, data: bytes):
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
