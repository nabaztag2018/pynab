import asyncio
import os
import logging
import functools
from threading import Timer
from enum import Enum
from .rfid import TagFlags, Rfid


class RfidDevState(Enum):  # pragma: no cover
    DISABLED = "disabled"
    POLLING_ONCE = "polling_once"
    POLLING_REPEAT = "polling_repeat"
    READING_BLOCKS = "reading"
    WRITING_BLOCKS = "writing"


class RfidDev(Rfid):  # pragma: no cover
    """
    Implementation for rfid reader based on /dev/rfid0
    Relying on cr14 driver
    """

    DEVICE_PATH = "/dev/rfid0"
    NABAZTAG_SIGNATURE = b"Nb"
    POLLING_TIMEOUT = 1.0

    def __init__(self):
        self.__state = RfidDevState.DISABLED
        self.__current_uid = None
        self.__current_picture = None
        self.__current_app = None
        self.__polling_timer = None
        self.__callback = None
        self.__write_condition = asyncio.Condition()
        self.__written_data = None
        if os.path.exists(RfidDev.DEVICE_PATH):
            self.__fd = os.open(RfidDev.DEVICE_PATH, os.O_RDWR)
            asyncio.get_event_loop().add_reader(self.__fd, self._do_read)
        else:
            self.__fd = None

    def _do_read_n_bytes(self, n):
        packet = b""
        while len(packet) < n:
            packet = packet + os.read(self.__fd, n - len(packet))
        return packet

    def _do_read(self):
        """
        Asyncio read callback.
        """
        self._cancel_timer()
        packet_header = os.read(self.__fd, 1)
        if packet_header == b"u":
            # UID packet.
            uid_le = self._do_read_n_bytes(8)
            self._process_uid(uid_le)
        elif packet_header == b"R":
            # Read multiple blocks packet
            count_bin = os.read(self.__fd, 1)
            data = self._do_read_n_bytes(count_bin[0] * 4)
            self._process_read_blocks(data)
        elif packet_header == b"W":
            # Write multiple blocks packet
            count_bin = os.read(self.__fd, 1)
            data = self._do_read_n_bytes(count_bin[0] * 4)
            self._process_write_blocks(data)
        else:
            logging.error(
                f"Unexpected packet from rfid reader, header={packet_header}"
            )

    def _timer_cb(self):
        """
        Timer invoked when no read happened after a given timeout.
        """
        # Previouse tag has been removed.
        if self.__current_uid:
            self._invoke_callback(None, TagFlags.REMOVED)
        self.__current_uid = None
        if self.__state != RfidDevState.DISABLED:
            self.__state = RfidDevState.POLLING_ONCE
            os.write(self.__fd, b"p")

    def _start_timer(self):
        self.__polling_timer = Timer(RfidDev.POLLING_TIMEOUT, self._timer_cb)
        self.__polling_timer.start()

    def _cancel_timer(self):
        if self.__polling_timer:
            self.__polling_timer.cancel()
            self.__polling_timer = None

    def _process_uid(self, uid_le):
        if (
            self.__state != RfidDevState.POLLING_ONCE
            and self.__state != RfidDevState.POLLING_REPEAT
        ):
            return
        uid = bytearray(uid_le)
        uid.reverse()
        if self.__state == RfidDevState.POLLING_REPEAT:
            if uid == self.__current_uid:
                # Simply reset timer
                self._start_timer()
                return
            else:
                # Previous tag has been removed
                if self.__current_uid:
                    self._invoke_callback(None, TagFlags.REMOVED)
        self.__current_uid = uid
        self.__current_picture = None
        self.__current_app = None
        if RfidDev.is_compatible(uid):
            # Read system and blocks 7-15
            os.write(
                self.__fd,
                b"R"
                + uid_le
                + b"\x0A\x07\x08\x09\x0A\x0B\x0C\x0D\x0E\x0F\xFF",
            )
            self.__state = RfidDevState.READING_BLOCKS
            self._start_timer()
        else:
            self._invoke_callback(None, TagFlags.UNKNOWN_PICC)
            self.__state = RfidDevState.POLLING_ONCE
            os.write(self.__fd, b"p")

    def _process_read_blocks(self, data):
        if self.__state != RfidDevState.READING_BLOCKS:
            return
        # check read data.
        first_block_le = data[0:4]
        first_block = bytearray(first_block_le)
        first_block.reverse()
        flags = 0
        app_data = None
        if self._is_locked(data[36:40]):
            flags |= TagFlags.READONLY
        if first_block[0:2] == RfidDev.NABAZTAG_SIGNATURE:
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
        self._invoke_callback(app_data, flags)
        self.__state = RfidDevState.POLLING_REPEAT
        os.write(self.__fd, b"P")
        self._start_timer()

    def _process_write_blocks(self, data):
        if self.__state != RfidDevState.WRITING_BLOCKS:
            return
        # Tag is probably still there, avoid unnecessary events.
        self.__state = RfidDevState.POLLING_REPEAT
        os.write(self.__fd, b"P")
        asyncio.create_task(self._notify_written_data(data))
        self._start_timer()

    async def _notify_written_data(self, data):
        async with self.__write_condition:
            self.__written_data = data
            self.__write_condition.notify()

    def _is_locked(self, system_block_le):
        """
        Determine if user data is locked, based on STMicroelectronics
        datasheets (we currently only support STMicroelectronics tags)
        """
        system_block_int = int.from_bytes(system_block_le, byteorder="little")
        return system_block_int & 0xFF800000 != 0xFF800000

    @staticmethod
    def is_compatible(uid_be):  # pragma: cover
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

    def _invoke_callback(self, app_data, flags):
        if self.__callback is not None:
            (loop, callback) = self.__callback
            partial = functools.partial(
                callback,
                self.__current_uid,
                self.__current_picture,
                self.__current_app,
                app_data,
                flags,
            )
            loop.call_soon_threadsafe(partial)

    @staticmethod
    def is_available():
        return os.path.exists(RfidDev.DEVICE_PATH)

    def on_detect(self, loop, callback):
        self.__callback = (loop, callback)
        if self.__state == RfidDevState.DISABLED and self.__fd is not None:
            self.__state = RfidDevState.POLLING_ONCE
            os.write(self.__fd, b"p")

    def disable_polling(self):
        if self.__state != RfidDevState.DISABLED:
            self.__state = RfidDevState.DISABLED
            self._cancel_timer()
            os.write(self.__fd, b"i")

    def enable_polling(self):
        if self.__state == RfidDevState.DISABLED and self.__fd is not None:
            self.__state = RfidDevState.POLLING_ONCE
            os.write(self.__fd, b"p")

    async def write(self, uid: str, picture: int, app: int, data: bytes):
        if self.__fd is None:
            return False
        self.__state = RfidDevState.WRITING_BLOCKS
        first_block = bytearray(RfidDev.NABAZTAG_SIGNATURE) + bytes(
            [picture, app]
        )
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
        write_blocks = bytes(range(7, blocks_count + 7))
        blocks_count_bin = bytes([blocks_count])
        try:
            async with self.__write_condition:
                self.__written_data = None
                self.__state = RfidDevState.WRITING_BLOCKS
                uid_le = bytearray(uid)
                uid_le.reverse()
                os.write(
                    self.__fd,
                    b"W"
                    + uid_le
                    + blocks_count_bin
                    + write_blocks
                    + write_data,
                )
                await self.__write_condition.wait()
                if self.__written_data == write_data:
                    return True
                else:
                    logging.error(
                        f"rfid_dev.write write data mismatch, wrote "
                        f"{write_data}, got {self.__written_data}"
                    )
                    return False
        finally:
            if self.__state != RfidDevState.POLLING_REPEAT:
                self.__state = RfidDevState.POLLING_ONCE
                os.write(self.__fd, b"p")
