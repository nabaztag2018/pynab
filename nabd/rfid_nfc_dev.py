import asyncio
import functools
import logging
import os
from enum import Enum
from threading import Timer

import nfcdev

from .rfid import Rfid, TagFlags, TagTechnology


class RfidNFCDevState(Enum):  # pragma: no cover
    DISABLED = "disabled"
    POLLING_AND_SELECT = "polling_and_select"
    POLLING_REPEAT = "polling_repeat"
    SELECTING = "selecting"
    RUNNING_OPERATION = "running_operation"


class RfidNFCOperationReadST25:  # pragma: no cover
    """
    Read several blocks from an ST25 tag
    """

    def __init__(self, dev, blocks, callback):
        self.__dev = dev
        self.__blocks = blocks
        self.__data = b""
        self.__callback = callback
        self.__dev.write_message(
            nfcdev.NFCTransceiveFrameRequestMessage(
                bytes([nfcdev.ST25TB_COMMAND_READ_BLOCK, self.__blocks[0]]),
            )
        )

    def process_frame(self, payload):
        if payload.flags & nfcdev.NFC_TRANSCEIVE_FLAGS_ERROR:
            self.__callback(False, None)
        elif payload.rx_count != 6:
            # Unexpected payload length.
            self.__callback(False, None)
        else:
            # Append data and read next block.
            self.__data += payload.data[0:4]
            self.__blocks = self.__blocks[1:]
            if len(self.__blocks) > 0:
                self.__dev.write_message(
                    nfcdev.NFCTransceiveFrameRequestMessage(
                        bytes(
                            [
                                nfcdev.ST25TB_COMMAND_READ_BLOCK,
                                self.__blocks[0],
                            ]
                        ),
                    )
                )
            else:
                self.__callback(True, self.__data)


class RfidNFCAsyncOperationWriteST25:  # pragma: no cover
    """
    Write several blocks from an ST25 tag.
    Because the tag does not reply to write commands, we will issue a read
    of system block afterwards to make sure the tag is still there.
    """

    def __init__(self, dev, blocks, data, loop=None):
        self.__dev = dev
        self.__blocks = blocks
        self.__data = data
        self.__loop = loop or asyncio.get_running_loop()
        self.future = self.__loop.create_future()
        self._send_command()

    def _send_command(self):
        if len(self.__blocks) > 0:
            block_data = self.__data[0:4]
            tx_data = (
                bytes([nfcdev.ST25TB_COMMAND_WRITE_BLOCK, self.__blocks[0]])
                + block_data
            )
            self.__dev.write_message(
                nfcdev.NFCTransceiveFrameRequestMessage(
                    tx_data,
                    nfcdev.NFC_TRANSCEIVE_FLAGS_TX_ONLY,
                )
            )
        else:
            # Read system block to make sure the tag is still here.
            self.__dev.write_message(
                nfcdev.NFCTransceiveFrameRequestMessage(
                    bytes([nfcdev.ST25TB_COMMAND_READ_BLOCK, 255])
                )
            )

    def process_frame(self, payload):
        if payload.flags & nfcdev.NFC_TRANSCEIVE_FLAGS_ERROR:
            self.future.set_result(False)
        elif payload.rx_count == 6 and len(self.__blocks) == 0:
            # All bytes were written, this is the callback from final read
            self.future.set_result(True)
        elif payload.rx_count != 6 and len(self.__blocks) == 0:
            # Final read, but unexpected length
            self.future.set_result(False)
        elif payload.rx_count != 0:
            # Unexpected payload length for a write
            self.future.set_result(False)
        else:
            # Read callback.
            self.__blocks = self.__blocks[1:]
            self.__data = self.__data[4:]
            # Write next block or start final write.
            # We should only do this after 7ms
            self.__loop.call_later(0.007, self._send_command)


class RfidNFCDev(Rfid):  # pragma: no cover
    """
    Implementation for rfid reader based on /dev/nfc0
    Relying on st25r391x driver
    """

    DEVICE_PATH = "/dev/nfc0"
    NABAZTAG_SIGNATURE = b"Nb"
    REMOVED_TIMEOUT = 1.5

    def __init__(self):
        self.__state = RfidNFCDevState.DISABLED
        self.__operation = None
        self.__current_tech = None
        self.__current_uid = None
        self.__current_picture = None
        self.__current_app = None
        self.__polling_timer = None
        self.__callback = None
        self.__select_condition = asyncio.Condition()
        if os.path.exists(RfidNFCDev.DEVICE_PATH):
            self.__dev = nfcdev.NFCDev(RfidNFCDev.DEVICE_PATH)
            self.__dev.open()
            asyncio.get_event_loop().add_reader(self.__dev.fd, self._do_read)
        else:
            self.__dev = None

    def _do_read(self):
        """
        Asyncio read callback.
        """
        header, payload = self.__dev.read_message()
        if header.message_type == nfcdev.NFC_SELECTED_TAG_MESSAGE_TYPE:
            tag_uid = self._tag_info_to_uid(payload.tag_type, payload.tag_info)
            if self.__state == RfidNFCDevState.SELECTING:
                if (
                    payload.tag_type == self.__current_tech
                    and tag_uid == self.__current_uid
                ):
                    asyncio.create_task(self._notify_selected())
            elif payload.tag_type == nfcdev.NFC_TAG_TYPE_ST25TB:
                self._process_st25tb_tag(tag_uid)
            else:
                self._process_unsupported_tag(
                    payload.tag_type, tag_uid, payload.tag_info
                )
        elif (
            header.message_type
            == nfcdev.NFC_IDLE_MODE_ACKNOWLEDGE_MESSAGE_TYPE
        ):
            if self.__state in (
                RfidNFCDevState.POLLING_AND_SELECT,
                RfidNFCDevState.POLLING_REPEAT,
            ):
                self._start_polling()
            elif self.__state == RfidNFCDevState.SELECTING:
                self._start_selecting()
            elif self.__state != RfidNFCDevState.DISABLED:
                logging.error(
                    "Unexpected idle ack packet, "
                    f"current state is {self.__state}"
                )
                self.__state = RfidNFCDevState.POLLING_AND_SELECT
                self._start_polling()
        elif (
            header.message_type
            == nfcdev.NFC_TRANSCEIVE_FRAME_RESPONSE_MESSAGE_TYPE
            and self.__state == RfidNFCDevState.RUNNING_OPERATION
        ):
            self.__operation.process_frame(payload)
        else:
            logging.error(
                "Unexpected packet from RFID reader, "
                f"header={header}, payload={payload}"
            )

    def _start_polling(self):
        self.__dev.write_message(
            nfcdev.NFCDiscoverModeRequestMessage(
                nfcdev.NFC_TAG_PROTOCOL_ALL,
                0,
                0,
                0,
                nfcdev.NFC_DISCOVER_FLAGS_SELECT,
            )
        )

    def _start_selecting(self):
        native_id = self._current_uid_to_native_id()
        self.__dev.write_message(
            nfcdev.NFCSelectTagMessage(
                int(self.__current_tech),
                native_id,
            )
        )

    def _transition_to_polling_select(self):
        self.__dev.write_message(nfcdev.NFCIdleModeRequestMessage())
        self.__operation = None
        self.__state = RfidNFCDevState.POLLING_AND_SELECT

    def _transition_to_polling_repeat(self):
        """
        Invoked when a tag is present to be notified when it's gone.
        """
        self.__dev.write_message(nfcdev.NFCIdleModeRequestMessage())
        self.__operation = None
        self.__state = RfidNFCDevState.POLLING_REPEAT
        self._start_timer()

    def _transition_to_disabled(self):
        self.__dev.write_message(nfcdev.NFCIdleModeRequestMessage())
        self.__operation = None
        self.__state = RfidNFCDevState.DISABLED

    def _timer_cb(self):
        """
        Timer invoked when no read happened after a given timeout.
        Used to find out when tag is removed.
        """
        # Previous tag has been removed.
        if self.__current_uid:
            self._invoke_callback(None, TagFlags.REMOVED, None)
        self.__current_tech = None
        self.__current_uid = None
        if (
            self.__state != RfidNFCDevState.DISABLED
            and self.__state != RfidNFCDevState.POLLING_AND_SELECT
        ):
            self.__state = RfidNFCDevState.POLLING_AND_SELECT
            self._start_polling()

    def _start_timer(self):
        self.__polling_timer = Timer(
            RfidNFCDev.REMOVED_TIMEOUT, self._timer_cb
        )
        self.__polling_timer.start()

    def _cancel_timer(self):
        if self.__polling_timer:
            self.__polling_timer.cancel()
            self.__polling_timer = None

    # ST25TB support
    def _process_st25tb_tag(self, tag_uid):
        if (
            self.__state != RfidNFCDevState.POLLING_AND_SELECT
            and self.__state != RfidNFCDevState.POLLING_REPEAT
        ):
            return
        if self.__state == RfidNFCDevState.POLLING_REPEAT:
            self._cancel_timer()
            if (
                tag_uid == self.__current_uid
                and TagTechnology.ST25TB == self.__current_tech
            ):
                # Tag is still here. Simply reset timer
                self._transition_to_polling_repeat()
                return
            # Another tag was selected, assume previous tag has been
            # removed
            if self.__current_uid:
                self._invoke_callback(None, TagFlags.REMOVED, None)
        self.__current_uid = tag_uid
        self.__current_tech = TagTechnology.ST25TB
        self.__current_picture = None
        self.__current_app = None
        if RfidNFCDev.st25tb_is_compatible(tag_uid):
            # Start reading, with system block last
            self.__state = RfidNFCDevState.RUNNING_OPERATION
            blocks = [7, 8, 9, 10, 11, 12, 13, 14, 15, 255]
            self.__operation = RfidNFCOperationReadST25(
                self.__dev, blocks, self._st25tb_read_callback
            )
            # We don't need a timer here, as we'll get an error message.
        else:
            # Transition to polling repeat
            self._invoke_callback(None, TagFlags.UNKNOWN_PICC, None)
            self._transition_to_polling_repeat()

    def _st25tb_read_callback(self, success, data):
        if success:
            # check read data.
            first_block_le = data[0:4]
            first_block = bytearray(first_block_le)
            first_block.reverse()
            flags = 0
            app_data = None
            if self._is_locked(data[36:40]):
                flags |= TagFlags.READONLY
            if first_block[0:2] == RfidNFCDev.NABAZTAG_SIGNATURE:
                self.__current_picture = first_block[2]
                self.__current_app = first_block[3]
                app_data = data[4:36]
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
            self._invoke_callback(app_data, flags, None)
        else:
            # We got some I/O problem with the tag
            # Maybe it was removed, but we'll wait for the timeout to kick in
            self._invoke_callback(None, TagFlags.UNKNOWN_PICC, None)
        self._transition_to_polling_repeat()

    async def _notify_selected(self):
        async with self.__select_condition:
            self.__select_condition.notify()

    def _is_locked(self, system_block_le):
        """
        Determine if user data is locked, based on STMicroelectronics
        datasheets (we currently only support STMicroelectronics tags)
        """
        system_block_int = int.from_bytes(system_block_le, byteorder="little")
        return system_block_int & 0xFF800000 != 0xFF800000

    @staticmethod
    def st25tb_is_compatible(uid_be):  # pragma: cover
        """
        Determine if tag is compatible based on UID.
        We currently support:
        - STMicroelectronics SRI512 (Violet ztamps)
        - STMicroelectronics SRT512 (Lemet' contactless transport tickets)
        - STMicroelectronics SRIX4K, SRI4K, SRI2K
        """
        if uid_be[0] != 0xD0:
            return False
        if uid_be[1] != 0x02:
            # STMicroelectronics
            return False
        if uid_be[2] & 0xFC == 0b00011000:
            # SRI512
            return True
        if uid_be[2] & 0xFC == 0b00110000:
            # SRT512
            return True
        if uid_be[2] & 0xFC == 0b00011100:
            # SRI4K
            return True
        if uid_be[2] & 0xFC == 0b00001100:
            # SRIX4K
            return True
        if uid_be[2] & 0xFC == 0b00111100:
            # SRIX2K
            return True
        return False

    # UNSUPPORTED TAGS
    def _process_unsupported_tag(self, tag_type, tag_uid, tag_info):
        if not tag_uid:
            # We cannot report this tag as we don't know its uid
            self._transition_to_polling_repeat()
            return
        if self.__state == RfidNFCDevState.POLLING_REPEAT:
            self._cancel_timer()
            if (
                tag_uid == self.__current_uid
                and tag_type == self.__current_tech
            ):
                # Tag is still here. Simply reset timer
                self._transition_to_polling_repeat()
                return
            # Another tag was selected, assume previous tag has been
            # removed
            if self.__current_uid:
                self._invoke_callback(None, TagFlags.REMOVED, None)
        self.__current_tech = TagTechnology(tag_type)
        self.__current_uid = tag_uid
        exported_tag_info = dict()
        for attr in ["ats", "sak", "application_data", "protocol_info"]:
            if hasattr(tag_info, attr):
                value = getattr(tag_info, attr)
                if type(value) is int:
                    exported_tag_info[attr] = value
                else:
                    exported_tag_info[attr] = " ".join(
                        "{:02x}".format(c) for c in bytearray(value)
                    )
        self.__current_picture = None
        self.__current_app = None
        # Transition to polling repeat
        self._invoke_callback(None, TagFlags.UNKNOWN_PICC, exported_tag_info)
        self._transition_to_polling_repeat()

    def _tag_info_to_uid(self, tag_type, tag_info):
        if tag_type == nfcdev.NFC_TAG_TYPE_ST25TB:
            tag_uid = bytearray(tag_info.uid)
            tag_uid.reverse()
        elif hasattr(tag_info, "uid"):
            tag_uid = tag_info.uid
        elif hasattr(tag_info, "pupi"):
            tag_uid = tag_info.pupi
        return tag_uid

    def _current_uid_to_native_id(self):
        if self.__current_tech == TagTechnology.ST25TB:
            native_id = bytearray(self.__current_uid)
            native_id.reverse()
        else:
            native_id = self.__current_uid
        return native_id

    def _invoke_callback(self, app_data, flags, tag_info):
        if self.__callback is not None:
            (loop, callback) = self.__callback
            partial = functools.partial(
                callback,
                self.__current_tech,
                self.__current_uid,
                self.__current_picture,
                self.__current_app,
                app_data,
                flags,
                tag_info,
            )
            loop.call_soon_threadsafe(partial)

    @staticmethod
    def is_available():
        return os.path.exists(RfidNFCDev.DEVICE_PATH)

    def on_detect(self, loop, callback):
        self.__callback = (loop, callback)
        if self.__state == RfidNFCDevState.DISABLED and self.__dev is not None:
            self.__state = RfidNFCDevState.POLLING_AND_SELECT
            self._start_polling()

    def disable_polling(self):
        if self.__state != RfidNFCDevState.DISABLED:
            self._transition_to_disabled()
            self._cancel_timer()

    def enable_polling(self):
        if self.__state == RfidNFCDevState.DISABLED and self.__dev is not None:
            self.__state = RfidNFCDevState.POLLING_AND_SELECT
            self._start_polling()

    async def write(
        self,
        tech: TagTechnology,
        uid: str,
        picture: int,
        app: int,
        data: bytes,
    ):
        """
        Write a tag.
        This function is synchronous, so we use an async condition to wait
        for completion.
        """
        if self.__dev is None:
            return False
        self.__state = RfidNFCDevState.SELECTING
        self.__current_uid = uid
        self.__current_tech = tech
        first_block = RfidNFCDev.NABAZTAG_SIGNATURE + bytes([picture, app])
        first_block = bytearray(first_block)
        first_block.reverse()
        write_data = first_block
        if data:
            # Add terminator.
            if len(data) < 32:
                data = bytearray(data) + b"\xFF"
            # Pad to 32 bits boundaries.
            while len(data) % 4 > 0:
                data = bytearray(data) + b"\xFF"
        else:
            data = b"\xFF\xFF\xFF\xFF"
        write_data = write_data + data
        blocks_count = len(data) // 4 + 1
        blocks = range(7, blocks_count + 7)
        try:
            async with self.__select_condition:
                self._start_selecting()
                await self.__select_condition.wait()

                self.__state = RfidNFCDevState.RUNNING_OPERATION
                self.__operation = RfidNFCAsyncOperationWriteST25(
                    self.__dev, blocks, write_data
                )
                result = await self.__operation.future
                self.__operation = None
                return result
        finally:
            if (
                self.__state != RfidNFCDevState.POLLING_REPEAT
                and self.__state != RfidNFCDevState.POLLING_AND_SELECT
            ):
                self._transition_to_polling_select()
