import asyncio
import functools
import logging
import os
from typing import Optional

import ndef  # type: ignore
import nfcdev

from .rfid import Rfid, TagFlags, TagTechnology


class TagData:
    def __init__(self, picture, app, app_data: Optional[bytes]):
        self.app = app
        self.picture = picture
        self.app_data = app_data

    def encode(self):
        first_block = RfidNFCDevSupport.NABAZTAG_SIGNATURE + bytes(
            [self.picture, self.app]
        )
        first_block = bytearray(first_block)
        first_block.reverse()
        data = self.app_data
        if data:
            # Add terminator.
            if len(data) < 32:
                data = bytearray(data) + b"\xFF"
            # Pad to 32 bits boundaries.
            while len(data) % 4 > 0:
                data = bytearray(data) + b"\xFF"
        else:
            data = b"\xFF\xFF\xFF\xFF"
        return first_block + data

    @classmethod
    def decode(cls, data):
        app = data[0]
        picture = data[1]
        app_data = data[4:36]
        return TagData(picture, app, app_data)


class RfidNFCDevSupport:
    NABAZTAG_SIGNATURE = b"Nb"

    @staticmethod
    def exported_tag_info(tag_info):
        result = dict()
        for attr in ["ats", "sak", "application_data", "protocol_info"]:
            if hasattr(tag_info, attr):
                value = getattr(tag_info, attr)
                if type(value) is int:
                    result[attr] = value
                else:
                    result[attr] = " ".join(
                        "{:02x}".format(c) for c in bytearray(value)
                    )
        return result


class RfidNFCDevST25TBSupport:
    @staticmethod
    def get_model(uid_le: bytes) -> Optional[str]:
        """
        Determine model based on UID.
        We currently support:
        - STMicroelectronics SRI512 (Violet ztamps)
        - STMicroelectronics SRT512 (Lemet' contactless transport tickets)
        - STMicroelectronics SRIX4K, SRI4K, SRI2K
        """
        if uid_le[-1] != 0xD0:
            return None
        if uid_le[-2] != 0x02:
            # STMicroelectronics
            return None
        if uid_le[-3] & 0xFC == 0b00011000:
            return "SRI512"
        if uid_le[-3] & 0xFC == 0b00110000:
            return "SRT512"
        if uid_le[-3] & 0xFC == 0b00011100:
            return "SRI4K"
        if uid_le[-3] & 0xFC == 0b00001100:
            return "SRIX4K"
        if uid_le[-3] & 0xFC == 0b00111100:
            return "SRIX2K"
        return None

    @staticmethod
    def is_compatible(uid_le: bytes) -> bool:
        """
        Determine if tag is compatible based on UID.
        We currently support:
        - STMicroelectronics SRI512 (Violet ztamps)
        - STMicroelectronics SRT512 (Lemet' contactless transport tickets)
        - STMicroelectronics SRIX4K, SRI4K, SRI2K
        """
        return RfidNFCDevST25TBSupport.get_model(uid_le) in (
            "SRI512",
            "SRT512",
            "SRI4K",
            "SRIX4K",
            "SRIX2K",
        )

    @staticmethod
    def exported_tag_info(tag_info):
        # ST25TB tags have no tag info beyond the UID.
        model = RfidNFCDevST25TBSupport.get_model(tag_info.uid)
        if model is not None:
            return dict(model=model)
        return None

    @staticmethod
    def decode_data(data):
        """
        Decode data for ST25TB including system block (7-15,255)
        """
        first_block_le = data[0:4]
        first_block = bytearray(first_block_le)
        first_block.reverse()
        flags = 0
        tag_data = None
        if RfidNFCDevST25TBSupport.is_locked(data[36:40]):
            flags |= TagFlags.READONLY
        if first_block[0:2] == RfidNFCDevSupport.NABAZTAG_SIGNATURE:
            tag_data = TagData.decode(data[0:36])
            flags |= TagFlags.FORMATTED
        else:
            user_data = data[0:36]
            foreign_data = False
            for c in user_data:
                if c != 255:
                    foreign_data = True
                    break
            if foreign_data:
                flags |= TagFlags.FOREIGN_DATA
            else:
                flags |= TagFlags.CLEAR
        return tag_data, flags

    @staticmethod
    def is_locked(system_block_le):
        """
        Determine if user data is locked, based on STMicroelectronics
        datasheets (we currently only support STMicroelectronics tags)
        """
        system_block_int = int.from_bytes(system_block_le, byteorder="little")
        return system_block_int & 0xFF800000 != 0xFF800000


class RfidNFCDevT2TSupport:
    NABAZTAG_TYPE = b"tagtagtag.fr:z"

    @staticmethod
    def exported_tag_info(tag_info, ndef_messages):
        taginfo_dict = RfidNFCDevSupport.exported_tag_info(tag_info)
        ndef = []
        if ndef_messages:
            for ndef_message in ndef_messages:
                if not ndef_message or not ndef_message.records:
                    continue
                for record in ndef_message.records:
                    exported_record = dict(
                        tnf=record.tnf,
                        type=record.type.hex(),
                    )
                    if record.id:
                        exported_record["id"] = record.id.hex()
                    if record.payload:
                        exported_record["payload"] = record.payload.hex()
                    ndef.append(exported_record)
        if len(ndef) > 0:
            taginfo_dict["ndef"] = ndef
        return taginfo_dict

    @staticmethod
    def decode_messages(ndef_messages, locked):
        """
        Decode data for T2T
        """
        flags = 0
        tag_data = None
        if ndef_messages == [] or ndef_messages == [None]:
            flags |= TagFlags.CLEAR
        else:
            # Do we have a tagtagtag.fr ext type?
            foreign_data = False
            for message in ndef_messages:
                for record in message.records:
                    if (
                        record.tnf == ndef.TNF_EXTERNAL
                        and record.type == RfidNFCDevT2TSupport.NABAZTAG_TYPE
                    ):
                        tag_data = TagData.decode(record.payload)
                        flags |= TagFlags.FORMATTED
                        foreign_data = False
                        break
                    else:
                        foreign_data = True
            if foreign_data:
                flags |= TagFlags.FOREIGN_DATA
        if locked:
            flags |= TagFlags.READONLY
        return tag_data, flags

    @staticmethod
    def encode_message(data):
        nabaztag_record = (
            ndef.TNF_EXTERNAL,
            RfidNFCDevT2TSupport.NABAZTAG_TYPE,
            b"",
            data,
        )
        nabaztag_message = ndef.new_message(nabaztag_record)
        return nabaztag_message


class RfidNFCDevDetectTagRemoval(nfcdev.NFCDevStateDetectRemoval):
    def __init__(self, rfid_dev, fsm, tag_type, tag_info):
        super().__init__(fsm, tag_type, tag_info, 0)
        self.__rfid_dev = rfid_dev

    def process_removed_tag(self, tag_type, tag_id):
        self.__rfid_dev._invoke_callback(
            tag_type, tag_id, None, TagFlags.REMOVED, None
        )
        self.fsm.write_message(nfcdev.NFCIdleModeRequestMessage())
        return RfidNFCDevDiscoverTags(self.__rfid_dev, self.fsm)


class RfidNFCDevDiscoverTags(nfcdev.NFCDevStateDiscover):
    def __init__(self, rfid_dev, fsm):
        self.__rfid_dev = rfid_dev
        super().__init__(
            fsm,
            nfcdev.NFCTagProtocol.ALL,
            0,
            0,
            0,
            nfcdev.NFCDiscoverFlags.SELECT,
        )

    def process_selected_tag(self, tag_type, tag_info):
        if tag_type == nfcdev.NFCTagType.ST25TB:
            return self._process_st25tb_tag(tag_type, tag_info)
        elif tag_type == nfcdev.NFCTagType.ISO14443A_T2T:
            return self._process_t2t_tag(tag_type, tag_info)
        else:
            return self._process_unsupported_tag(tag_type, tag_info)

    # ST25TB support
    def _process_st25tb_tag(self, tag_type, tag_info):
        if RfidNFCDevST25TBSupport.is_compatible(tag_info.uid):
            return RfidNFCReadST25TB(
                self.__rfid_dev, self.fsm, tag_type, tag_info
            )
        # Transition to polling repeat
        exported_tag_info = RfidNFCDevST25TBSupport.exported_tag_info(tag_info)
        self.__rfid_dev._invoke_callback(
            tag_type,
            tag_info.tag_id(),
            None,
            TagFlags.UNKNOWN_PICC,
            exported_tag_info,
        )
        self.fsm.write_message(nfcdev.NFCIdleModeRequestMessage())
        return RfidNFCDevDetectTagRemoval(
            self.__rfid_dev, self.fsm, tag_type, tag_info
        )

    # T2T support
    def _process_t2t_tag(self, tag_type, tag_info):
        return RfidNFCReadT2T(self.__rfid_dev, self.fsm, tag_type, tag_info)

    def _process_unsupported_tag(self, tag_type, tag_info):
        # Transition to polling repeat
        logging.info(f"Unsupported tag {tag_type}")
        exported_tag_info = RfidNFCDevSupport.exported_tag_info(tag_info)
        self.__rfid_dev._invoke_callback(
            tag_type,
            tag_info.tag_id(),
            None,
            TagFlags.UNKNOWN_PICC,
            exported_tag_info,
        )
        self.fsm.write_message(nfcdev.NFCIdleModeRequestMessage())
        return RfidNFCDevDetectTagRemoval(
            self.__rfid_dev, self.fsm, tag_type, tag_info
        )


class RfidNFCReadT2T(nfcdev.NFCDevStateT2TReadNDEF):
    def __init__(self, rfid_dev, fsm, tag_type, tag_info):
        super().__init__(fsm)
        self.__rfid_dev = rfid_dev
        self.__tag_type = tag_type
        self.__tag_info = tag_info

    def failure(self, ex: BaseException):
        # We got some I/O problem with the tag
        # Maybe it was removed, but we'll wait for the timeout to kick in
        exported_tag_info = RfidNFCDevT2TSupport.exported_tag_info(
            self.__tag_info, None
        )
        logging.info("Failed to read NDEF from tag (not a formatted T2T?)")
        self.__rfid_dev._invoke_callback(
            self.__tag_type,
            self.__tag_info.tag_id(),
            None,
            TagFlags.UNKNOWN_PICC,
            exported_tag_info,
        )
        self.fsm.write_message(nfcdev.NFCIdleModeRequestMessage())
        return RfidNFCDevDetectTagRemoval(
            self.__rfid_dev, self.fsm, self.__tag_type, self.__tag_info
        )

    def success(self, messages, locked):
        self.fsm.write_message(nfcdev.NFCIdleModeRequestMessage())
        tag_data, flags = RfidNFCDevT2TSupport.decode_messages(
            messages, locked
        )
        exported_tag_info = RfidNFCDevT2TSupport.exported_tag_info(
            self.__tag_info, messages
        )
        self.__rfid_dev._invoke_callback(
            self.__tag_type,
            self.__tag_info.tag_id(),
            tag_data,
            flags,
            exported_tag_info,
        )
        return RfidNFCDevDetectTagRemoval(
            self.__rfid_dev, self.fsm, self.__tag_type, self.__tag_info
        )


class RfidNFCDevWriteT2T(nfcdev.NFCDevStateT2TWriteNDEF):
    def __init__(self, rfid_dev, fsm, tag_type, tag_info, data, future):
        ndef_message = RfidNFCDevT2TSupport.encode_message(data)
        super().__init__(fsm, [ndef_message])
        self.__rfid_dev = rfid_dev
        self.__tag_type = tag_type
        self.__tag_info = tag_info
        self.__future = future

    def failure(self, ex: BaseException):
        self.__future.set_result(False)
        self.fsm.write_message(nfcdev.NFCIdleModeRequestMessage())
        return RfidNFCDevDetectTagRemoval(
            self.__rfid_dev, self.fsm, self.__tag_type, self.__tag_info
        )

    def success(self):
        self.__future.set_result(True)
        self.fsm.write_message(nfcdev.NFCIdleModeRequestMessage())
        return RfidNFCDevDetectTagRemoval(
            self.__rfid_dev, self.fsm, self.__tag_type, self.__tag_info
        )


class RfidNFCReadST25TB(nfcdev.NFCDevStateST25TBReadBlocks):
    def __init__(self, rfid_dev, fsm, tag_type, tag_info):
        super().__init__(fsm, [*range(7, 16), 255])
        self.__rfid_dev = rfid_dev
        self.__tag_type = tag_type
        self.__tag_info = tag_info

    def failure(self):
        # We got some I/O problem with the tag
        # Maybe it was removed, but we'll wait for the timeout to kick in
        exported_tag_info = RfidNFCDevST25TBSupport.exported_tag_info(
            self.__tag_info
        )
        self.__rfid_dev._invoke_callback(
            self.__tag_type,
            self.__tag_info.tag_id(),
            None,
            TagFlags.UNKNOWN_PICC,
            exported_tag_info,
        )
        self.fsm.write_message(nfcdev.NFCIdleModeRequestMessage())
        return RfidNFCDevDetectTagRemoval(
            self.__rfid_dev, self.fsm, self.__tag_type, self.__tag_info
        )

    def success(self, data):
        self.fsm.write_message(nfcdev.NFCIdleModeRequestMessage())
        tag_data, flags = RfidNFCDevST25TBSupport.decode_data(data)
        exported_tag_info = RfidNFCDevST25TBSupport.exported_tag_info(
            self.__tag_info
        )
        self.__rfid_dev._invoke_callback(
            self.__tag_type,
            self.__tag_info.tag_id(),
            tag_data,
            flags,
            exported_tag_info,
        )
        return RfidNFCDevDetectTagRemoval(
            self.__rfid_dev, self.fsm, self.__tag_type, self.__tag_info
        )


class RfidNFCDevWriteST25TB(nfcdev.NFCDevStateST25TBWriteBlocks):
    def __init__(self, rfid_dev, fsm, tag_type, tag_info, data, future):
        blocks_count = len(data) // 4
        # User blocks start at 7
        blocks = range(7, blocks_count + 7)
        super().__init__(fsm, blocks, data)
        self.__rfid_dev = rfid_dev
        self.__tag_type = tag_type
        self.__tag_info = tag_info
        self.__future = future

    def failure(self):
        self.__future.set_result(False)
        self.fsm.write_message(nfcdev.NFCIdleModeRequestMessage())
        return RfidNFCDevDetectTagRemoval(
            self.__rfid_dev, self.fsm, self.__tag_type, self.__tag_info
        )

    def success(self):
        self.__future.set_result(True)
        self.fsm.write_message(nfcdev.NFCIdleModeRequestMessage())
        return RfidNFCDevDetectTagRemoval(
            self.__rfid_dev, self.fsm, self.__tag_type, self.__tag_info
        )


class RfidNFCDevSelectTagForWriting(nfcdev.NFCDevStateSelect):
    def __init__(self, rfid_dev, fsm, tag_type, tag_id, data, future):
        super().__init__(fsm, tag_type, tag_id)
        self.__rfid_dev = rfid_dev
        self.__data = data
        self.__future = future

    def process_selected_tag(self, tag_type, tag_info):
        if tag_type == nfcdev.NFCTagType.ST25TB:
            return RfidNFCDevWriteST25TB(
                self.__rfid_dev,
                self.fsm,
                tag_type,
                tag_info,
                self.__data,
                self.__future,
            )
        if tag_type == nfcdev.NFCTagType.ISO14443A_T2T:
            return RfidNFCDevWriteT2T(
                self.__rfid_dev,
                self.fsm,
                tag_type,
                tag_info,
                self.__data,
                self.__future,
            )
        logging.error(f"Unexpected tag type when writing ({tag_type})")
        self.__future.set_result(False)


class RfidNFCDev(Rfid):  # pragma: no cover
    """
    Implementation for rfid reader based on /dev/nfc0
    Relying on st25r391x driver and pynfcdev statemachine API
    """

    DEVICE_PATH = "/dev/nfc0"
    REMOVED_TIMEOUT = 1.5

    def __init__(self):
        self.__callback = None
        if os.path.exists(RfidNFCDev.DEVICE_PATH):
            loop = asyncio.get_event_loop()
            self.__fsm = nfcdev.NFCDevStateMachine(
                loop, RfidNFCDev.DEVICE_PATH
            )
            self.__fsm.open()
        else:
            self.__fsm = None

    def format_uid(self, tag_type, tag_id):
        if tag_type == nfcdev.NFCTagType.ST25TB:
            tag_uid = bytearray(tag_id)
            tag_uid.reverse()
        else:
            tag_uid = tag_id
        return tag_uid

    def unformat_uid(self, tech, uid):
        if tech == TagTechnology.ST25TB:
            tag_id = bytearray(uid)
            tag_id.reverse()
        else:
            tag_id = uid
        return tag_id

    def format_tech(self, tag_type):
        return TagTechnology(tag_type.value)

    def unformat_tech(self, tech):
        return nfcdev.NFCTagType(tech.value)

    def _invoke_callback(self, tag_type, tag_id, tag_data, flags, tag_info):
        if self.__callback is not None:
            uid = self.format_uid(tag_type, tag_id)
            tech = self.format_tech(tag_type)
            (loop, callback) = self.__callback
            partial = functools.partial(
                callback,
                tech,
                uid,
                tag_data and tag_data.picture,
                tag_data and tag_data.app,
                tag_data and tag_data.app_data,
                flags,
                tag_info,
            )
            loop.call_soon_threadsafe(partial)

    @staticmethod
    def is_available():
        return os.path.exists(RfidNFCDev.DEVICE_PATH)

    def on_detect(self, loop, callback):
        self.__callback = (loop, callback)
        if self.__fsm is not None:
            if self.__fsm.get_device_state() == nfcdev.NFCDeviceState.IDLE:
                self.__fsm.set_state(RfidNFCDevDiscoverTags(self, self.__fsm))

    def disable_polling(self):
        if self.__fsm is not None:
            if self.__fsm.get_device_state() != nfcdev.NFCDeviceState.IDLE:
                self.__fsm.write_message(nfcdev.NFCIdleModeRequestMessage())
                self.__fsm.set_state(nfcdev.NFCDevStateDisabled(self.__fsm))

    def enable_polling(self):
        if self.__fsm is not None:
            if self.__fsm.get_device_state() == nfcdev.NFCDeviceState.IDLE:
                self.__fsm.set_state(RfidNFCDevDiscoverTags(self, self.__fsm))

    async def write(
        self,
        tech: TagTechnology,
        uid: bytes,
        picture: int,
        app: int,
        data: Optional[bytes],
    ):
        """
        Write a tag.
        This function is synchronous, so we use an async condition to wait
        for completion.
        """
        if self.__fsm is None:
            return False
        tag_data = TagData(picture, app, data)
        write_data = tag_data.encode()
        tag_id = self.unformat_uid(tech, uid)
        tag_type = self.unformat_tech(tech)
        future = self.__fsm.loop.create_future()
        try:
            self.__fsm.set_state(
                RfidNFCDevSelectTagForWriting(
                    self, self.__fsm, tag_type, tag_id, write_data, future
                )
            )
            return await future
        finally:
            # If the task is cancelled, reset the fsm to discover mode.
            self.__fsm.write_message(nfcdev.NFCIdleModeRequestMessage())
            self.__fsm.set_state(RfidNFCDevDiscoverTags(self, self.__fsm))
