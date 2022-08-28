import asyncio
import collections
import datetime
import gc
import getopt
import json
import logging
import os
import socket
import subprocess
import sys
import time
import traceback
from enum import Enum
from typing import Deque, Dict, List, Optional, Tuple, Type, Union, cast

import dateutil.parser
from lockfile import AlreadyLocked, LockFailed  # type: ignore
from lockfile.pidlockfile import PIDLockFile  # type: ignore

from nabcommon import hardware, nablogging, network, settings
from nabcommon.nabservice import NabService
from nabcommon.typing import (
    Animation,
    AnyPacket,
    ButtonEventType,
    CommandPacket,
    CommandSequenceItem,
    EarsPacket,
    EventPacket,
    EventTypes,
    InfoPacket,
    MessagePacket,
    ModePacket,
    NabdPacket,
    ResponseErrorPacketProto,
    ResponseExpiredPacketProto,
    ResponseFailurePacketProto,
    ResponseGestaltPacketProto,
    ResponseOKPacketProto,
    ResponsePacket,
    ResponsePacketProto,
    RfidWritePacket,
    ServicePacket,
    ServiceRequestPacket,
    SleepPacket,
    TestPacket,
)

from .ears import Ears
from .leds import Led
from .nabio import NabIO
from .rfid import (
    DEFAULT_RFID_TIMEOUT,
    TAG_APPLICATION_NONE,
    TAG_APPLICATIONS,
    TagFlags,
    TagTechnology,
)

_PYTEST = os.path.basename(sys.argv[0]) != "nabd.py"


IdleQueueItem = Tuple[ServicePacket, asyncio.StreamWriter]

STATUS_EXPIRED = cast(ResponseExpiredPacketProto, {"status": "expired"})
STATUS_OK = cast(ResponseOKPacketProto, {"status": "ok"})
STATUS_CANCELED = cast(ResponseOKPacketProto, {"status": "canceled"})
STATUS_FAILURE = cast(ResponseFailurePacketProto, {"status": "failure"})


def status_error(
    error_class: str, error_message: str
) -> ResponseErrorPacketProto:
    return cast(
        ResponseErrorPacketProto,
        {"status": "error", "class": error_class, "message": error_message},
    )


def status_error_malformed_packet(
    error_message: str,
) -> ResponseErrorPacketProto:
    return status_error("MalformedPacket", error_message)


class State(Enum):
    IDLE = "idle"
    ASLEEP = "asleep"
    INTERACTIVE = "interactive"
    PLAYING = "playing"
    RECORDING = "recording"


class Nabd:
    SLEEP_EAR_POSITION = 10
    INIT_EAR_POSITION = 0
    EAR_MOVEMENT_TIMEOUT = 0.5

    SYSTEMD_ACTIVATED_FD = 3

    def __init__(self, nabio: NabIO):
        settings.configure(type(self).__name__.lower())
        self.nabio = nabio
        self.idle_cv = asyncio.Condition()
        self.idle_queue: Deque[IdleQueueItem] = collections.deque()
        # Current position of ears in idle mode
        self.ears = {
            "left": Nabd.INIT_EAR_POSITION,
            "right": Nabd.INIT_EAR_POSITION,
        }
        self.info: Dict[
            str, Animation
        ] = {}  # Info persists across service connections.
        self.state = State.IDLE
        # Dictionary of writers, i.e. connected services
        # For each writer, value is the list of registered events
        self.service_writers: Dict[asyncio.StreamWriter, List[str]] = {}
        self.interactive_service_writer: Optional[asyncio.StreamWriter] = None
        # Events registered in interactive mode
        self.interactive_service_events: List[EventTypes] = []
        self.running = True
        self.loop: Optional[asyncio.events.AbstractEventLoop] = None
        self._ears_moved_task: Optional[asyncio.Future] = None
        self.playing_cancelable = False
        self.playing_request_id: Optional[str] = None
        Nabd.leds_boot(self.nabio, 2)
        if self.nabio.has_sound_input():
            from . import i18n
            from .asr import ASR
            from .nlu import NLU

            config = i18n.Config.load()
            self._asr_locale = ASR.get_locale(config.locale)
            self.asr: Optional[ASR] = ASR(self._asr_locale)
            Nabd.leds_boot(self.nabio, 3)
            self._nlu_locale = NLU.get_locale(config.locale)
            self.nlu: Optional[NLU] = NLU(self._nlu_locale)
            Nabd.leds_boot(self.nabio, 4)
        else:
            self.asr = None
            self.nlu = None

    async def reload_config(self):
        """
        Reload configuration.
        """
        if self.nabio.has_sound_input():
            from . import i18n
            from .asr import ASR
            from .nlu import NLU

            config = await i18n.Config.load_async()
            new_asr_locale = ASR.get_locale(config.locale)
            new_nlu_locale = NLU.get_locale(config.locale)
            if new_asr_locale != self._asr_locale:
                Nabd.leds_boot(self.nabio, 2)
                self._asr_locale = new_asr_locale
                self.asr = None
                gc.collect()
                self.asr = ASR(self._asr_locale)
                Nabd.leds_boot(self.nabio, 3)
            if new_nlu_locale != self._nlu_locale:
                Nabd.leds_boot(self.nabio, 3)
                self._nlu_locale = new_nlu_locale
                self.nlu = None
                gc.collect()
                self.nlu = NLU(self._nlu_locale)
                Nabd.leds_boot(self.nabio, 4)
            self.nabio.set_leds(None, None, None, None, None)
        self.nabio.pulse(Led.BOTTOM, (255, 0, 255))  # Fuchsia

    async def _do_transition_to_idle(self):
        """
        Transition to idle.
        Lock is acquired.
        Thread: service or idle_worker_loop
        """
        left, right = self.ears["left"], self.ears["right"]
        await self.nabio.move_ears_with_leds((255, 0, 255), left, right)
        self.nabio.pulse(Led.BOTTOM, (255, 0, 255))  # Fuchsia
        if network.ip_address(self.nabio.network_interface()) is None:
            # not even a local network connection: real bad
            logging.error("no network connection")
            self.nabio.pulse(Led.BOTTOM, (255, 0, 0))  # Red
        elif not network.internet_connection():
            # local network connection, but no Internet access: not so good
            logging.warning("no Internet access")
            self.nabio.pulse(Led.BOTTOM, (255, 165, 0))  # Orange

    async def sleep_setup(self):
        self.nabio.set_leds(None, None, None, None, None)
        await self.nabio.move_ears(
            Nabd.SLEEP_EAR_POSITION, Nabd.SLEEP_EAR_POSITION
        )

    async def idle_worker_loop(self):
        """
        Idle worker loop is responsible for playing enqueued messages and
        displaying info items.
        """
        assert self.loop is not None
        try:
            async with self.idle_cv:
                await self._do_transition_to_idle()
                while self.running:
                    # Check if we have something to do.
                    if self.state == State.IDLE and len(self.idle_queue) > 0:
                        item = self.idle_queue.popleft()
                        await self.process_idle_item(item)
                    else:
                        if (
                            self.state == State.IDLE
                            and len(self.info.items()) > 0
                        ):
                            for key, value in self.info.copy().items():
                                notified = await self.nabio.play_info(
                                    self.idle_cv,
                                    value["tempo"],
                                    value["colors"],
                                )
                                if notified:
                                    break
                        else:
                            await self.idle_cv.wait()
        except KeyboardInterrupt:
            pass
        except Exception:
            logging.debug(traceback.format_exc())
        finally:
            if self.running:
                self.loop.stop()

    async def stop_idle_worker(self):
        async with self.idle_cv:
            self.running = False  # signal to exit
            self.idle_cv.notify()

    async def exit_interactive(self):
        """
        Exit interactive mode.
        Restarts idle loop worker.
        Thread: service_loop
        """
        # interactive -> playing or interactive -> idle depending on the
        # command queue
        self.interactive_service_writer = None
        await self.transition_to(State.IDLE)

    async def process_idle_item(self, item: IdleQueueItem):
        """
        Process an item from the idle queue.
        The lock is acquired when this function is called.
        Thread: idle_worker_loop
        """
        while True:
            if "expiration" in item[0] and self.is_past(
                cast(CommandPacket, item[0])["expiration"]
            ):
                self.write_response_packet(item[0], STATUS_EXPIRED, item[1])
                if len(self.idle_queue) == 0:
                    await self.set_state(State.IDLE)
                    break
                else:
                    item = self.idle_queue.popleft()
            else:
                if item[0]["type"] == "command":
                    await self.set_state(State.PLAYING)
                    await self.perform(item[0], item[1])
                    if len(self.idle_queue) == 0:
                        await self.set_state(State.IDLE)
                        break
                    else:
                        item = self.idle_queue.popleft()
                elif item[0]["type"] == "message":
                    await self.set_state(State.PLAYING)
                    await self.perform(item[0], item[1])
                    if len(self.idle_queue) == 0:
                        await self.set_state(State.IDLE)
                        break
                    else:
                        item = self.idle_queue.popleft()
                elif item[0]["type"] == "sleep":
                    # Check idle_queue doesn't only include 'sleep' items.
                    has_non_sleep = False
                    for other_item in self.idle_queue:
                        if other_item[0]["type"] != "sleep":
                            has_non_sleep = True
                            break
                    if has_non_sleep:
                        self.idle_queue.append(item)
                    else:
                        self.write_response_packet(item[0], STATUS_OK, item[1])
                        await self.set_state(State.ASLEEP)
                        break
                elif (
                    item[0]["type"] == "mode"
                    and item[0]["mode"] == "interactive"
                ):
                    self.write_response_packet(item[0], STATUS_OK, item[1])
                    await self.set_state(State.INTERACTIVE)
                    self.interactive_service_writer = item[1]
                    if "events" in item[0]:
                        self.interactive_service_events = item[0]["events"]
                    else:
                        self.interactive_service_events = ["ears", "button"]
                    break
                elif item[0]["type"] == "test":
                    await self.set_state(State.PLAYING)
                    await self.do_process_test_packet(
                        cast(TestPacket, item[0]), item[1]
                    )
                    if len(self.idle_queue) == 0:
                        await self.set_state(State.IDLE)
                        break
                    else:
                        item = self.idle_queue.popleft()
                elif item[0]["type"] == "rfid_write":
                    await self.do_process_rfid_write_packet(item[0], item[1])
                    if len(self.idle_queue) == 0:
                        await self.set_state(State.IDLE)
                        break
                    else:
                        item = self.idle_queue.popleft()
                else:
                    raise RuntimeError(f"Unexpected packet {item[0]}")

    def is_past(self, isodatestr):
        # Python 3.7's fromisoformat only parses output of isoformat, not all
        # valid ISO 8601 dates.
        parsed = dateutil.parser.isoparse(isodatestr)
        if parsed.tzinfo:
            return parsed < datetime.datetime.now().astimezone()
        else:
            return parsed < datetime.datetime.now()

    async def set_state(self, new_state):
        """
        Thread: idle loop (only called from process_idle_item)
        """
        if new_state != self.state:
            if new_state == State.IDLE:
                await self._do_transition_to_idle()
            if new_state == State.ASLEEP:
                await self.sleep_setup()
            self.state = new_state
            self.broadcast_state()

    async def transition_to(self, new_state):
        """
        Thread: service or run (hw callbacks)
        """
        async with self.idle_cv:
            if self.state != new_state:
                self.state = new_state
                if new_state == State.IDLE:
                    await self._do_transition_to_idle()
                    self.idle_cv.notify()
                self.broadcast_state()

    async def process_info_packet(
        self, any_packet: AnyPacket, writer: asyncio.StreamWriter
    ):
        """Process an info packet"""
        packet = self.__check_info_packet(any_packet, writer)
        if packet:
            if "animation" in packet:
                self.info[packet["info_id"]] = packet["animation"]
            elif packet["info_id"] in self.info:
                del self.info[packet["info_id"]]
            self.write_response_packet(packet, STATUS_OK, writer)
            # Signal idle loop to make sure we display updated info
            async with self.idle_cv:
                self.idle_cv.notify()

    def __check_info_packet(
        self, packet: AnyPacket, writer: asyncio.StreamWriter
    ) -> Optional[InfoPacket]:
        assert packet["type"] == "info"
        if "info_id" not in packet:
            self.write_response_packet(
                packet,
                status_error_malformed_packet("Missing required info_id slot"),
                writer,
            )
            return None
        if not isinstance(packet["info_id"], str):
            self.write_response_packet(
                packet,
                status_error_malformed_packet(
                    "Invalid info_id slot, expected a string"
                ),
                writer,
            )
            return None
        if "animation" in packet:
            if not isinstance(packet["animation"], dict):
                self.write_response_packet(
                    packet,
                    status_error_malformed_packet(
                        "Invalid animation slot, expected a dict"
                    ),
                    writer,
                )
                return None
            if "tempo" not in packet["animation"]:
                self.write_response_packet(
                    packet,
                    status_error_malformed_packet(
                        "Missing required tempo slot in animation"
                    ),
                    writer,
                )
                return None
            if not isinstance(
                packet["animation"]["tempo"], int
            ) and not isinstance(packet["animation"]["tempo"], float):
                self.write_response_packet(
                    packet,
                    status_error_malformed_packet(
                        "Invalid tempo slot in animation, expected a number"
                    ),
                    writer,
                )
                return None
            if "colors" not in packet["animation"]:
                self.write_response_packet(
                    packet,
                    status_error_malformed_packet(
                        "Missing required colors slot in animation"
                    ),
                    writer,
                )
                return None
        return cast(InfoPacket, packet)

    async def process_ears_packet(
        self, any_packet: AnyPacket, writer: asyncio.StreamWriter
    ):
        """Process an ears packet"""
        packet = self.__check_ears_packet(any_packet, writer)
        if packet:
            if "left" in packet:
                self.ears["left"] = packet["left"]
            if "right" in packet:
                self.ears["right"] = packet["right"]
            if self.state == State.IDLE:
                if "event" in packet and packet["event"]:
                    # Simulate an ears_event
                    now = time.time()
                    self.broadcast_event(
                        "ears",
                        {
                            "type": "ears_event",
                            "left": self.ears["left"],
                            "right": self.ears["right"],
                            "time": now,
                        },
                    )
                await self.nabio.move_ears(
                    self.ears["left"], self.ears["right"]
                )
            self.write_response_packet(packet, STATUS_OK, writer)

    def __check_ears_packet(
        self, packet: AnyPacket, writer: asyncio.StreamWriter
    ) -> Optional[EarsPacket]:
        assert packet["type"] == "ears"
        if "left" in packet and not isinstance(packet["left"], int):
            self.write_response_packet(
                packet,
                status_error_malformed_packet(
                    "Invalid left slot, expected an int"
                ),
                writer,
            )
            return None
        if "right" in packet and not isinstance(packet["right"], int):
            self.write_response_packet(
                packet,
                status_error_malformed_packet(
                    "Invalid right slot, expected an int"
                ),
                writer,
            )
            return None
        if "request_id" in packet and not isinstance(
            packet["request_id"], str
        ):
            self.write_response_packet(
                packet,
                status_error_malformed_packet(
                    "Invalid request_id slot, expected a string"
                ),
                writer,
            )
            return None
        if "event" in packet and not isinstance(packet["event"], bool):
            self.write_response_packet(
                packet,
                status_error_malformed_packet(
                    "Invalid event slot, expected a bool"
                ),
                writer,
            )
            return None
        return cast(EarsPacket, packet)

    async def process_command_packet(
        self, packet: AnyPacket, writer: asyncio.StreamWriter
    ):
        """Process a command packet"""
        await self.process_perform_packet("sequence", packet, writer)

    async def process_message_packet(
        self, packet: AnyPacket, writer: asyncio.StreamWriter
    ):
        """Process a message packet"""
        await self.process_perform_packet("body", packet, writer)

    async def process_perform_packet(
        self,
        slot: str,
        any_packet: AnyPacket,
        writer: asyncio.StreamWriter,
    ):
        assert self.loop is not None
        packet = self.__check_perform_packet(any_packet, slot, writer)
        if packet:
            if self.interactive_service_writer == writer:
                # interactive => play command immediately, asynchronously
                self.loop.create_task(self.perform(packet, writer))
            else:
                async with self.idle_cv:
                    self.idle_queue.append((packet, writer))
                    self.idle_cv.notify()

    def __check_perform_packet(
        self, packet: AnyPacket, slot: str, writer: asyncio.StreamWriter
    ) -> Optional[Union[CommandPacket, MessagePacket]]:
        if slot in packet:
            return cast(Union[CommandPacket, MessagePacket], packet)
        self.write_response_packet(
            packet,
            status_error_malformed_packet(f"Missing required {slot} slot"),
            writer,
        )
        return None

    async def process_cancel_packet(
        self, packet: AnyPacket, writer: asyncio.StreamWriter
    ):
        """Process a cancel packet"""
        if "request_id" in packet:
            request_id = packet["request_id"]
            if self.playing_request_id == request_id:
                if self.playing_cancelable:
                    self.playing_canceled = True
                    await self.nabio.cancel()
                else:
                    self.write_response_packet(
                        packet,
                        status_error(
                            "NotCancelable",
                            "Playing command is not cancelable",
                        ),
                        writer,
                    )
            else:
                self.write_response_packet(
                    packet,
                    status_error(
                        "NotPlaying",
                        "Cancel packet does not refer to running command",
                    ),
                    writer,
                )
        else:
            self.write_response_packet(
                packet,
                status_error_malformed_packet(
                    "Missing required request_id slot"
                ),
                writer,
            )

    async def process_wakeup_packet(
        self, packet: AnyPacket, writer: asyncio.StreamWriter
    ):
        """Process a wakeup packet"""
        assert packet["type"] == "wakeup"
        self.write_response_packet(packet, STATUS_OK, writer)
        if self.state == State.ASLEEP:
            await self.transition_to(State.IDLE)

    async def process_sleep_packet(
        self, any_packet: AnyPacket, writer: asyncio.StreamWriter
    ):
        """Process a sleep packet"""
        assert any_packet["type"] == "sleep"
        packet = cast(SleepPacket, any_packet)
        if self.state == State.ASLEEP:
            self.write_response_packet(packet, STATUS_OK, writer)
        else:
            async with self.idle_cv:
                self.idle_queue.append((packet, writer))
                self.idle_cv.notify()

    async def process_mode_packet(
        self, any_packet: AnyPacket, writer: asyncio.StreamWriter
    ):
        """Process a mode packet"""
        packet = self.__check_mode_packet(any_packet, writer)
        if not packet:
            return
        if packet["mode"] == "interactive":
            if writer == self.interactive_service_writer:
                if "events" in packet:
                    self.interactive_service_events = packet["events"]
                else:
                    self.interactive_service_events = ["ears", "button"]
                self.write_response_packet(packet, STATUS_OK, writer)
            elif self.interactive_service_writer is not None:
                self.write_response_packet(
                    packet,
                    status_error(
                        "AlreadyInInteractiveMode",
                        "Nabd is already in interactive mode",
                    ),
                    writer,
                )
            else:
                async with self.idle_cv:
                    self.idle_queue.append((packet, writer))
                    self.idle_cv.notify()
        else:  # packet["mode"] == "idle":
            if "events" in packet:
                self.service_writers[writer] = packet["events"]
            else:
                self.service_writers[writer] = []
            if writer == self.interactive_service_writer:
                # exit interactive mode.
                await self.exit_interactive()
            self.write_response_packet(packet, STATUS_OK, writer)

    def __check_mode_packet(
        self, packet: AnyPacket, writer: asyncio.StreamWriter
    ) -> Optional[ModePacket]:
        if "mode" in packet:
            if packet["mode"] in ("interactive", "idle"):
                return cast(ModePacket, packet)
            logging.debug(f"unknown mode packet from service: {packet}")
            self.write_response_packet(
                packet,
                status_error_malformed_packet(
                    "Mode packet with unknown mode slot"
                ),
                writer,
            )
        else:
            logging.debug(f"malformed mode packet from service: {packet}")
            self.write_response_packet(
                packet,
                status_error_malformed_packet("Missing mode slot"),
                writer,
            )
        return None

    async def process_gestalt_packet(
        self, packet: AnyPacket, writer: asyncio.StreamWriter
    ):
        """Process a gestalt packet"""
        proc = subprocess.Popen(
            ["ps", "-o", "etimes", "-p", str(os.getpid()), "--no-headers"],
            stdout=subprocess.PIPE,
        )
        proc.wait()
        response: ResponseGestaltPacketProto = {
            "state": self.state.value,
            "connections": len(self.service_writers),
            "hardware": await self.nabio.gestalt(),
        }
        if proc.stdout:
            results = proc.stdout.readlines()
            uptime = int(results[0].strip())
            response["uptime"] = uptime
        self.write_response_packet(packet, response, writer)

    async def process_config_update_packet(
        self, packet: AnyPacket, writer: asyncio.StreamWriter
    ):
        """Process a config_update packet"""
        if "service" not in packet:
            self.write_response_packet(
                packet,
                status_error_malformed_packet(
                    "Config update packet with missing service slot"
                ),
                writer,
            )
        else:
            if packet["service"] == "nabd":
                if "slot" in packet and packet["slot"] == "locale":
                    await self.reload_config()
                    self.write_response_packet(packet, STATUS_OK, writer)

    async def process_test_packet(
        self, any_packet: AnyPacket, writer: asyncio.StreamWriter
    ):
        """Process a test packet (for hardware tests)"""
        packet = self.__check_test_packet(any_packet, writer)
        if packet:
            if self.state == State.ASLEEP:
                await self.do_process_test_packet(packet, writer)
            else:
                async with self.idle_cv:
                    self.idle_queue.append((packet, writer))
                    self.idle_cv.notify()

    def __check_test_packet(
        self, packet: AnyPacket, writer: asyncio.StreamWriter
    ) -> Optional[TestPacket]:
        if "test" in packet:
            return cast(TestPacket, packet)
        logging.debug(f"unknown test packet from service: {packet}")
        self.write_response_packet(
            packet,
            status_error_malformed_packet(
                "Test packet with missing test slot"
            ),
            writer,
        )
        return None

    async def do_process_test_packet(
        self, packet: TestPacket, writer: asyncio.StreamWriter
    ):
        response: ResponsePacketProto
        result = await self.nabio.test(packet["test"])
        if result:
            response = STATUS_OK
        else:
            response = STATUS_FAILURE
        self.write_response_packet(packet, response, writer)

    async def process_rfid_write_packet(
        self, any_packet: AnyPacket, writer: asyncio.StreamWriter
    ):
        """Process a rfid_write packet"""
        packet = self.__check_rfid_write_packet(any_packet, writer)
        if packet is not None:
            if self.state == State.ASLEEP:
                await self.do_process_rfid_write_packet(packet, writer)
            else:
                async with self.idle_cv:
                    self.idle_queue.append((packet, writer))
                    self.idle_cv.notify()

    async def do_process_rfid_write_packet(
        self, packet: RfidWritePacket, writer: asyncio.StreamWriter
    ) -> None:
        """Process a rfid_write packet"""
        if self.nabio.rfid is None:
            self.write_response_packet(
                packet,
                status_error(
                    "NFCException", "Unknown exception while writing NFC tag"
                ),
                writer,
            )
            return
        tech = TagTechnology[packet["tech"].upper()]
        uid = bytes.fromhex(packet["uid"].replace(":", ""))
        picture = packet["picture"]
        app_str = packet["app"]
        app = self._get_rfid_app_id(app_str)
        if "data" in packet:
            data: Optional[bytes] = packet["data"].encode("utf8")
        else:
            data = None
        if "timeout" in packet:
            timeout: Union[int, float] = packet["timeout"]
        else:
            timeout = DEFAULT_RFID_TIMEOUT
        self.nabio.rfid_awaiting_feedback()
        try:
            success = await asyncio.wait_for(
                self.nabio.rfid.write(tech, uid, picture, app, data),
                timeout=timeout,
            )
            if success:
                self.write_response_packet(
                    packet, {"status": "ok", "uid": packet["uid"]}, writer
                )
            else:
                self.write_response_packet(
                    packet,
                    status_error(
                        "NFCWriteError",
                        f"NFC write failed for tag (uid={str(packet['uid'])})",
                    ),
                    writer,
                )
        except asyncio.TimeoutError:
            self.write_response_packet(
                packet,
                {
                    "status": "timeout",
                    "message": "NFC write timed out (NFC tag not found?)",
                },
                writer,
            )
        except Exception as err:
            logging.error("Unknown exception with NFC write")
            logging.error(traceback.format_exc())
            self.write_response_packet(
                packet,
                status_error(
                    type(err).__name__,
                    "Unknown exception while writing NFC tag",
                ),
                writer,
            )
        finally:
            self.nabio.rfid_done_feedback()

    def __check_rfid_write_packet(
        self, packet: AnyPacket, writer: asyncio.StreamWriter
    ) -> Optional[RfidWritePacket]:
        if (
            "uid" in packet
            and "picture" in packet
            and "app" in packet
            and "tech" in packet
            and packet["tech"].upper() in TagTechnology.__members__
        ):
            return cast(RfidWritePacket, packet)
        logging.debug(f"Malformed rfid_write packet from service: {packet}")
        self.write_response_packet(
            packet,
            status_error_malformed_packet(
                "rfid_write packet with missing or invalid slots"
            ),
            writer,
        )
        return None

    async def process_os_shutdown_packet(
        self, packet: AnyPacket, writer: asyncio.StreamWriter
    ):
        assert packet["type"] == "shutdown"
        self.write_response_packet(packet, STATUS_OK, writer)
        if "mode" in packet:
            perform_reboot = packet["mode"] == "reboot"
        else:
            perform_reboot = False
        asyncio.ensure_future(self._shutdown(perform_reboot))

    async def process_packet(
        self, packet: AnyPacket, writer: asyncio.StreamWriter
    ):
        """
        Process a packet from a service
        Thread: service_loop
        """
        logging.debug(f"packet from service: {packet}")
        processors = {
            "info": self.process_info_packet,
            "ears": self.process_ears_packet,
            "command": self.process_command_packet,
            "message": self.process_message_packet,
            "cancel": self.process_cancel_packet,
            "wakeup": self.process_wakeup_packet,
            "sleep": self.process_sleep_packet,
            "mode": self.process_mode_packet,
            "gestalt": self.process_gestalt_packet,
            "config-update": self.process_config_update_packet,
            "test": self.process_test_packet,
            "rfid_write": self.process_rfid_write_packet,
            "shutdown": self.process_os_shutdown_packet,
        }
        if packet["type"] in processors:
            await processors[packet["type"]](packet, writer)
        else:
            self.write_response_packet(
                packet,
                status_error_malformed_packet(
                    f"Packet of unknown type ({str(packet['type'])})"
                ),
                writer,
            )

    def write_packet(self, response: NabdPacket, writer: asyncio.StreamWriter):
        writer.write((json.dumps(response) + "\r\n").encode("utf8"))

    def _test_event_mask(self, event_type: str, events: List[str]) -> bool:
        matching = event_type in events
        if not matching and "/" in event_type:
            event_type0 = event_type.split("/", 1)[0]
            matching = event_type0 + "/*" in events
        return matching

    def broadcast_event(self, event_type, response: EventPacket):
        if self.interactive_service_writer is None:
            logging.debug(f"broadcast event: {event_type}, {response}")
            for sw, events in self.service_writers.items():
                if self._test_event_mask(event_type, events):
                    self.write_packet(response, sw)
        elif self._test_event_mask(
            event_type, self.interactive_service_events
        ):
            logging.debug(
                f"send event to interactive service: {event_type}, {response}"
            )
            self.write_packet(response, self.interactive_service_writer)

    def write_response_cancelable(
        self,
        original_packet: Union[CommandPacket, MessagePacket],
        writer: asyncio.StreamWriter,
    ):
        if self.playing_canceled:
            status = STATUS_CANCELED
        else:
            status = STATUS_OK
        self.write_response_packet(original_packet, status, writer)

    def write_response_packet(
        self,
        original_packet: Union[None, AnyPacket, ServicePacket],
        template: ResponsePacketProto,
        writer: asyncio.StreamWriter,
    ):
        response_packet: AnyPacket = cast(AnyPacket, template)
        if original_packet is not None and "request_id" in original_packet:
            response_packet["request_id"] = cast(
                ServiceRequestPacket, original_packet
            )["request_id"]
        response_packet["type"] = "response"
        self.write_packet(cast(ResponsePacket, response_packet), writer)

    def broadcast_state(self):
        for sw in self.service_writers:
            self.write_state_packet(sw)

    def write_state_packet(self, writer: asyncio.StreamWriter):
        self.write_packet({"type": "state", "state": self.state.value}, writer)

    # Handle service through TCP/IP protocol
    async def service_loop(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        self.write_state_packet(writer)
        self.service_writers[writer] = []
        try:
            while not reader.at_eof():
                line = await reader.readline()
                if line != b"" and line != b"\r\n":
                    try:
                        packet = json.loads(line.decode("utf8"))
                        if (
                            not isinstance(packet, dict)
                            or "type" not in packet
                        ):
                            self.write_response_packet(
                                None,
                                status_error_malformed_packet(
                                    "Missing type slot"
                                ),
                                writer,
                            )
                        else:
                            await self.process_packet(packet, writer)
                    except UnicodeDecodeError as e:
                        logging.debug(f"Unicode Error {e} with service packet")
                        logging.debug(f"{packet}")
                        self.write_response_packet(
                            None,
                            status_error("UnicodeDecodeError", str(e)),
                            writer,
                        )
                    except json.decoder.JSONDecodeError as e:
                        logging.debug(f"JSON Error {e} with service packet")
                        logging.debug(str(line))
                        self.write_response_packet(
                            None,
                            status_error("JSONDecodeError", str(e)),
                            writer,
                        )
            writer.close()
            await writer.wait_closed()
        except ConnectionResetError:
            pass
        except BrokenPipeError:
            pass
        except Exception:
            logging.debug(traceback.format_exc())
        finally:
            del self.service_writers[writer]
            if self.interactive_service_writer == writer:
                await self.exit_interactive()

    async def perform(
        self,
        packet: Union[CommandPacket, MessagePacket],
        writer: asyncio.StreamWriter,
    ):
        if "request_id" in packet:
            self.playing_request_id = packet["request_id"]
        self.playing_cancelable = (
            "cancelable" not in packet or packet["cancelable"]
        )
        self.playing_canceled = False
        if packet["type"] == "command":
            await self.nabio.play_sequence(packet["sequence"])
        else:
            signature: CommandSequenceItem = {}
            if "signature" in packet:
                signature = packet["signature"]
            await self.nabio.play_message(signature, packet["body"])
        self.write_response_cancelable(packet, writer)
        self.playing_request_id = None
        self.playing_cancelable = False

    def button_callback(
        self, button_event: ButtonEventType, event_time: float
    ):
        """
        Thread: run_loop
        """
        if button_event == "hold" and self.state == State.IDLE:
            asyncio.ensure_future(self.start_asr())
        elif button_event == "up" and self.state == State.RECORDING:
            asyncio.ensure_future(self.stop_asr())
        elif button_event == "triple_click":
            asyncio.ensure_future(self._shutdown(False))
        elif (
            button_event == "click"
            and (
                self.interactive_service_writer is None
                or "button" not in self.interactive_service_events
            )
            and self.playing_cancelable
        ):
            asyncio.ensure_future(self.nabio.cancel(True))
            self.playing_canceled = True
        else:
            self.broadcast_event(
                "button",
                {
                    "type": "button_event",
                    "event": button_event,
                    "time": event_time,
                },
            )

    async def start_asr(self):
        """
        Thread: run_loop
        """
        assert self.asr is not None
        await self.transition_to(State.RECORDING)
        if self.nabio.rfid is not None:
            self.nabio.rfid.disable_polling()
        await self.nabio.start_acquisition(self.asr.decode_chunk)

    async def stop_asr(self):
        assert self.asr is not None
        assert self.nlu is not None
        await self.nabio.end_acquisition()
        now = time.time()
        decoded_str = await self.asr.get_decoded_string(True)
        # ASR model needs to be improved, log outcome.
        logging.debug(f"ASR string: {decoded_str}")
        response = await self.nlu.interpret(decoded_str)
        logging.debug(f"NLU response: {str(response)}")
        if self.nabio.rfid is not None:
            self.nabio.rfid.enable_polling()
        await self.transition_to(State.IDLE)
        if response is None:
            # Did not understand
            await self.nabio.asr_failed()
        else:
            event_type = "asr/*"
            if "/" in response["intent"]:
                app, _ = response["intent"].split("/", 1)
                event_type = f"asr/{app}"
            self.broadcast_event(
                event_type, {"type": "asr_event", "nlu": response, "time": now}
            )

    async def _shutdown(self, doReboot):
        await self.stop_idle_worker()
        Nabd.leds_boot(self.nabio, 0)
        await self.nabio.move_ears(
            Nabd.SLEEP_EAR_POSITION, Nabd.SLEEP_EAR_POSITION
        )
        if doReboot:
            await self._do_system_command("/sbin/reboot")
        else:
            await self._do_system_command("/sbin/halt")

    async def _do_system_command(self, sytemCommandStr):
        logging.info(f"Initiating system command: {sytemCommandStr}")
        if not _PYTEST:
            os.system(sytemCommandStr)

    def ears_callback(self, ear):
        if self.interactive_service_writer:
            # Cancel any previously registered timer
            if self._ears_moved_task:
                self._ears_moved_task.cancel()
            # Tell services
            if ear == Ears.LEFT_EAR:
                ear_str = "left"
            else:
                ear_str = "right"
            if self._test_event_mask("ears", self.interactive_service_events):
                now = time.time()
                self.write_packet(
                    {"type": "ear_event", "ear": ear_str, "time": now},
                    self.interactive_service_writer,
                )
        else:
            # Wait a little bit for user to continue moving the ears
            # Then we'll run a detection and tell services if we're not
            # sleeping.
            if self._ears_moved_task:
                self._ears_moved_task.cancel()
            self._ears_moved_task = asyncio.ensure_future(self._ears_moved())

    async def _ears_moved(self):
        await asyncio.sleep(Nabd.EAR_MOVEMENT_TIMEOUT)
        if self.interactive_service_writer is None:
            (left, right) = await self.nabio.detect_ears_positions()
            self.ears["left"] = left
            self.ears["right"] = right
            if self.state != State.ASLEEP:
                now = time.time()
                self.broadcast_event(
                    "ears",
                    {
                        "type": "ears_event",
                        "left": left,
                        "right": right,
                        "time": now,
                    },
                )

    def rfid_callback(
        self, tech, uid, picture, app, app_data, flags, tag_info
    ):
        # bytes.hex(sep) is python 3.8+
        uid_str = ":".join("{:02x}".format(c) for c in uid)
        packet = {
            "type": "rfid_event",
            "tech": tech.name.lower(),
            "uid": uid_str,
            "time": time.time(),
        }
        if flags & TagFlags.REMOVED:
            packet["event"] = "removed"
        else:
            packet["event"] = "detected"
            if flags & TagFlags.FORMATTED:
                support = "formatted"
            elif flags & TagFlags.FOREIGN_DATA:
                support = "foreign-data"
            elif flags & TagFlags.READONLY:
                support = "locked"
            elif flags & TagFlags.CLEAR:
                support = "empty"
            else:
                support = "unknown"
            packet["support"] = support
            if flags & TagFlags.READONLY:
                packet["locked"] = True
        event_type = "rfid/*"
        if picture is not None:
            packet["picture"] = picture
        if tag_info is not None:
            packet["tag_info"] = tag_info
        if app is not None and app != TAG_APPLICATION_NONE:
            app_str = self._get_rfid_app(app)
            packet["app"] = app_str
            if app_data is not None:
                app_data_str_bin = app_data.split(b"\xFF", 1)[0]
                app_data_str = app_data_str_bin.decode("utf8")
                packet["data"] = app_data_str
            event_type = "rfid/" + app_str
        if self.state != State.ASLEEP and not flags & TagFlags.REMOVED:
            asyncio.ensure_future(self.nabio.rfid_detected_feedback())
        self.broadcast_event(event_type, packet)

    def _get_rfid_app(self, app):
        if app in TAG_APPLICATIONS:
            return TAG_APPLICATIONS[app]
        else:
            return f"{app}"

    def _get_rfid_app_id(self, app):
        for id, name in TAG_APPLICATIONS.items():
            if name == app:
                return id
        try:
            return int(app)
        except ValueError:
            return TAG_APPLICATION_NONE

    def run(self):
        self.loop = asyncio.get_event_loop()
        self.nabio.bind_button_event(self.loop, self.button_callback)
        self.nabio.bind_ears_event(self.loop, self.ears_callback)
        self.nabio.bind_rfid_event(self.loop, self.rfid_callback)
        idle_task = self.loop.create_task(self.idle_worker_loop())
        if os.environ.get("LISTEN_PID", None) == str(os.getpid()):
            server_task = self.loop.create_task(
                asyncio.start_server(
                    self.service_loop,
                    sock=socket.fromfd(
                        Nabd.SYSTEMD_ACTIVATED_FD,
                        socket.AF_INET,
                        socket.SOCK_STREAM,
                    ),
                )
            )
        else:
            server_task = self.loop.create_task(
                asyncio.start_server(
                    self.service_loop, NabService.HOST, NabService.PORT_NUMBER
                )
            )
        try:
            self.loop.run_forever()
            for t in [idle_task, server_task]:
                if t.done():
                    t_ex = t.exception()
                    if t_ex:
                        raise t_ex
        except KeyboardInterrupt:
            pass
        except Exception:
            error_msg = f"Unhandled error: {traceback.format_exc()}"
            print(error_msg)
            logging.critical(error_msg)
        finally:
            self.loop.run_until_complete(self.stop_idle_worker())
            server = server_task.result()
            server.close()
            for writer in self.service_writers.copy():
                writer.close()
                self.loop.run_until_complete(writer.wait_closed())
            tasks = asyncio.all_tasks(self.loop)
            for t in [t for t in tasks if not (t.done() or t.cancelled())]:
                # give canceled tasks the last chance to run
                try:
                    self.loop.run_until_complete(t)
                except asyncio.CancelledError:
                    pass
            self.loop.close()

    def stop(self):
        assert self.loop is not None
        if not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.loop.stop)

    @staticmethod
    def leds_boot(nabio, step):
        """
        Animation to indicate boot progress.
        Useful as loading ASR/NLU model takes some time.
        """
        # Step 0 is actually used for shutdown. Same values are in nabboot.py
        # for startup led values.
        if step == 0:
            nabio.set_leds(
                (255, 0, 255),
                (255, 0, 255),
                (255, 0, 255),
                (255, 0, 255),
                (255, 0, 255),
            )
        if step == 1:
            nabio.set_leds(
                (255, 0, 255),
                (255, 255, 255),
                (255, 0, 255),
                (255, 0, 255),
                (255, 0, 255),
            )
        if step == 2:
            nabio.set_leds(
                (255, 0, 255),
                (255, 255, 255),
                (255, 0, 255),
                (255, 0, 255),
                (255, 0, 255),
            )
        if step == 3:
            nabio.set_leds(
                (255, 0, 255),
                (255, 255, 255),
                (255, 255, 255),
                (255, 0, 255),
                (255, 0, 255),
            )
        if step == 4:
            nabio.set_leds(
                (255, 0, 255),
                (255, 255, 255),
                (255, 255, 255),
                (255, 255, 255),
                (255, 0, 255),
            )

    @staticmethod
    def main(argv):
        nablogging.setup_logging("nabd")
        pidfilepath = "/run/nabd.pid"
        hardware_platform = hardware.device_model()
        if hardware.is_pi_zero(hardware_platform):
            # running on Pi Zero or Zero 2 hardware
            from .nabio_hw import NabIOHW

            nabiocls: Type[NabIO] = NabIOHW
        else:
            # other hardware: go virtual
            from .nabio_virtual import NabIOVirtual

            nabiocls: Type[NabIO] = NabIOVirtual
        usage = (
            f"nabd [options]\n"
            f" -h                  display this message\n"
            f" --pidfile=<pidfile> define pidfile (default = {pidfilepath})\n"
            " --nabio=<nabio> define nabio class "
            f"(default = {nabiocls.__module__}.{nabiocls.__name__})\n"
        )
        try:
            opts, args = getopt.getopt(argv, "h", ["pidfile=", "nabio="])
        except getopt.GetoptError:
            print(usage)
            exit(2)
        for opt, arg in opts:
            if opt == "-h":
                print(usage)
                exit(0)
            elif opt == "--pidfile":
                pidfilepath = arg
            elif opt == "--nabio":
                from pydoc import locate

                nabiocls = cast(Type[NabIO], locate(arg))
        pidfile = PIDLockFile(pidfilepath, timeout=-1)
        try:
            with pidfile:
                nabio = nabiocls()
                Nabd.leds_boot(nabio, 1)
                nabd = Nabd(nabio)
                logging.info(f"running on {hardware_platform}")
                nabd.run()
        except AlreadyLocked:
            error_msg = f"nabd already running? (pid={pidfile.read_pid()})"
            print(error_msg)
            logging.critical(error_msg)
            exit(1)
        except LockFailed:
            error_msg = (
                f"Cannot write pid file to {pidfilepath}, please fix "
                f"permissions"
            )
            print(error_msg)
            logging.critical(error_msg)
            exit(1)
        except Exception:
            error_msg = f"Unhandled error: {traceback.format_exc()}"
            print(error_msg)
            logging.critical(error_msg)
            exit(3)


if __name__ == "__main__":
    Nabd.main(sys.argv[1:])
