import asyncio
import json
import datetime
import collections
import sys
import getopt
import os
import socket
import logging
import subprocess
import dateutil.parser
import time
import traceback
import gc
from enum import Enum
from lockfile.pidlockfile import PIDLockFile
from lockfile import AlreadyLocked, LockFailed
from nabcommon import nablogging
from nabcommon import settings
from nabcommon.nabservice import NabService
from .leds import Led
from .ears import Ears
from .rfid import (
    TagFlags,
    TAG_APPLICATIONS,
    TAG_APPLICATION_NONE,
    DEFAULT_RFID_TIMEOUT,
)


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

    def __init__(self, nabio):
        settings.configure(type(self).__name__.lower())
        self.nabio = nabio
        self.idle_cv = asyncio.Condition()
        self.idle_queue = collections.deque()
        # Current position of ears in idle mode
        self.ears = {
            "left": Nabd.INIT_EAR_POSITION,
            "right": Nabd.INIT_EAR_POSITION,
        }
        self.info = {}  # Info persists across service connections.
        self.state = State.IDLE
        # Dictionary of writers, i.e. connected services
        # For each writer, value is the list of registered events
        self.service_writers = {}
        self.interactive_service_writer = None
        # Events registered in interactive mode
        self.interactive_service_events = []
        self.running = True
        self.loop = None
        self._ears_moved_task = None
        self.playing_cancelable = False
        self.playing_request_id = None
        self.boot = True
        Nabd.leds_boot(self.nabio, 2)
        if self.nabio.has_sound_input():
            from . import i18n
            from .asr import ASR
            from .nlu import NLU

            config = i18n.Config.load()
            self._asr_locale = ASR.get_locale(config.locale)
            self.asr = ASR(self._asr_locale)
            Nabd.leds_boot(self.nabio, 3)
            self._nlu_locale = NLU.get_locale(config.locale)
            self.nlu = NLU(self._nlu_locale)
            Nabd.leds_boot(self.nabio, 4)

    async def reload_config(self):
        """
        Reload configuration.
        """
        self.boot = True
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
        self.nabio.pulse(Led.BOTTOM, (255, 0, 255))
        await self.boot_playsound()

    async def boot_playsound(self):
        """
        Play sound indicating end of boot.
        """
        if (self.boot):
            await self.nabio.play_sequence([{"audio": ["boot/*.mp3"]}])
            self.boot = False

    async def _do_transition_to_idle(self):
        """
        Transition to idle.
        Lock is acquired.
        Thread: service or idle_worker_loop
        """
        left, right = self.ears["left"], self.ears["right"]
        await self.nabio.move_ears_with_leds((255, 0, 255), left, right)
        self.nabio.pulse(Led.BOTTOM, (255, 0, 255))
        await self.boot_playsound()

    async def sleep_setup(self):
        self.nabio.set_leds(None, None, None, None, None)
        await self.boot_playsound()
        await self.nabio.move_ears(
            Nabd.SLEEP_EAR_POSITION, Nabd.SLEEP_EAR_POSITION
        )

    async def idle_worker_loop(self):
        """
        Idle worker loop is responsible for playing enqueued messages and
        displaying info items.
        """
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

    async def process_idle_item(self, item):
        """
        Process an item from the idle queue.
        The lock is acquired when this function is called.
        Thread: idle_worker_loop
        """
        while True:
            if "expiration" in item[0] and self.is_past(item[0]["expiration"]):
                self.write_response_packet(
                    item[0], {"status": "expired"}, item[1]
                )
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
                        self.write_response_packet(
                            item[0], {"status": "ok"}, item[1]
                        )
                        await self.set_state(State.ASLEEP)
                        break
                elif (
                    item[0]["type"] == "mode"
                    and item[0]["mode"] == "interactive"
                ):
                    self.write_response_packet(
                        item[0], {"status": "ok"}, item[1]
                    )
                    await self.set_state(State.INTERACTIVE)
                    self.interactive_service_writer = item[1]
                    if "events" in item[0]:
                        self.interactive_service_events = item[0]["events"]
                    else:
                        self.interactive_service_events = ["ears", "button"]
                    break
                elif item[0]["type"] == "test":
                    await self.do_process_test_packet(item[0], item[1])
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

    async def process_info_packet(self, packet, writer):
        """ Process an info packet """
        if "info_id" in packet:
            if "animation" in packet:
                if (
                    "tempo" not in packet["animation"]
                    or "colors" not in packet["animation"]
                ):
                    self.write_response_packet(
                        packet,
                        {
                            "status": "error",
                            "class": "MalformedPacket",
                            "message": "Missing required tempo & colors slots "
                            "in animation",
                        },
                        writer,
                    )
                else:
                    self.info[packet["info_id"]] = packet["animation"]
            elif packet["info_id"] in self.info:
                del self.info[packet["info_id"]]
            self.write_response_packet(packet, {"status": "ok"}, writer)
            # Signal idle loop to make sure we display updated info
            async with self.idle_cv:
                self.idle_cv.notify()
        else:
            self.write_response_packet(
                packet,
                {
                    "status": "error",
                    "class": "MalformedPacket",
                    "message": "Missing required info_id slot",
                },
                writer,
            )

    async def process_ears_packet(self, packet, writer):
        """ Process an ears packet """
        if "left" in packet:
            self.ears["left"] = packet["left"]
        if "right" in packet:
            self.ears["right"] = packet["right"]
        if self.state == State.IDLE:
            if "event" in packet and packet["event"]:
                # Simulate an ears_event
                self.broadcast_event(
                    "ears",
                    {
                        "type": "ears_event",
                        "left": self.ears["left"],
                        "right": self.ears["right"],
                    },
                )
            await self.nabio.move_ears(self.ears["left"], self.ears["right"])
        self.write_response_packet(packet, {"status": "ok"}, writer)

    async def process_command_packet(self, packet, writer):
        """ Process a command packet """
        await self.process_perform_packet("sequence", packet, writer)

    async def process_message_packet(self, packet, writer):
        """ Process a message packet """
        await self.process_perform_packet("body", packet, writer)

    async def process_perform_packet(self, slot, packet, writer):
        if slot in packet:
            if self.interactive_service_writer == writer:
                # interactive => play command immediately, asynchronously
                self.loop.create_task(self.perform(packet, writer))
            else:
                async with self.idle_cv:
                    self.idle_queue.append((packet, writer))
                    self.idle_cv.notify()
        else:
            self.write_response_packet(
                packet,
                {
                    "status": "error",
                    "class": "MalformedPacket",
                    "message": f"Missing required {slot} slot",
                },
                writer,
            )

    async def process_cancel_packet(self, packet, writer):
        """ Process a cancel packet """
        if "request_id" in packet:
            request_id = packet["request_id"]
            if self.playing_request_id == request_id:
                if self.playing_cancelable:
                    self.playing_canceled = True
                    await self.nabio.cancel()
                else:
                    self.write_response_packet(
                        packet,
                        {
                            "status": "error",
                            "class": "NotCancelable",
                            "message": "Playing command is not cancelable",
                        },
                        writer,
                    )
            else:
                self.write_response_packet(
                    packet,
                    {
                        "status": "error",
                        "class": "NotPlaying",
                        "message": "Cancel packet does not refer to running"
                        " command",
                    },
                    writer,
                )
        else:
            self.write_response_packet(
                packet,
                {
                    "status": "error",
                    "class": "MalformedPacket",
                    "message": "Missing required request_id slot",
                },
                writer,
            )

    async def process_wakeup_packet(self, packet, writer):
        """ Process a wakeup packet """
        self.write_response_packet(packet, {"status": "ok"}, writer)
        if self.state == State.ASLEEP:
            await self.transition_to(State.IDLE)

    async def process_sleep_packet(self, packet, writer):
        """ Process a sleep packet """
        if self.state == State.ASLEEP:
            self.write_response_packet(packet, {"status": "ok"}, writer)
        else:
            async with self.idle_cv:
                self.idle_queue.append((packet, writer))
                self.idle_cv.notify()

    async def process_mode_packet(self, packet, writer):
        """ Process a mode packet """
        if "mode" in packet and packet["mode"] == "interactive":
            if writer == self.interactive_service_writer:
                if "events" in packet:
                    self.interactive_service_events = packet["events"]
                else:
                    self.interactive_service_events = ["ears", "button"]
                self.write_response_packet(packet, {"status": "ok"}, writer)
            elif self.interactive_service_writer is not None:
                self.write_response_packet(
                    packet,
                    {
                        "status": "error",
                        "class": "AlreadyInInteractiveMode",
                        "message": "Nabd is already in interactive mode",
                    },
                    writer,
                )
            else:
                async with self.idle_cv:
                    self.idle_queue.append((packet, writer))
                    self.idle_cv.notify()
        elif "mode" in packet and packet["mode"] == "idle":
            if "events" in packet:
                self.service_writers[writer] = packet["events"]
            else:
                self.service_writers[writer] = []
            if writer == self.interactive_service_writer:
                # exit interactive mode.
                await self.exit_interactive()
            self.write_response_packet(packet, {"status": "ok"}, writer)
        else:
            logging.debug(f"unknown mode packet from service: {packet}")
            self.write_response_packet(
                packet,
                {
                    "status": "error",
                    "class": "UnknownPacket",
                    "message": "Unknown or malformed mode packet",
                },
                writer,
            )

    async def process_gestalt_packet(self, packet, writer):
        """ Process a gestalt packet """
        proc = subprocess.Popen(
            ["ps", "-o", "etimes", "-p", str(os.getpid()), "--no-headers"],
            stdout=subprocess.PIPE,
        )
        proc.wait()
        results = proc.stdout.readlines()
        uptime = int(results[0].strip())
        response = {}
        response["state"] = self.state.value
        response["uptime"] = uptime
        response["connections"] = len(self.service_writers)
        response["hardware"] = await self.nabio.gestalt()
        self.write_response_packet(packet, response, writer)

    async def process_config_update_packet(self, packet, writer):
        """ Process a config_update packet """
        if not "service" in packet:
            self.write_response_packet(
                packet,
                {
                    "status": "error",
                    "class": "UnknownPacket",
                    "message": "Unknown or malformed mode packet",
                },
                writer,
            )
        else:
            if packet["service"] == "nabd":
                if "slot" in packet and packet["slot"] == "locale":
                    await self.reload_config()
                    self.write_response_packet(
                        packet, {"status": "ok"}, writer
                    )

    async def process_test_packet(self, packet, writer):
        """ Process a test packet (for hardware tests) """
        if self.state == State.ASLEEP:
            await self.do_process_test_packet(packet, writer)
        else:
            async with self.idle_cv:
                self.idle_queue.append((packet, writer))
                self.idle_cv.notify()

    async def do_process_test_packet(self, packet, writer):
        if "test" in packet:
            response = {}
            result = await self.nabio.test(packet["test"])
            if result:
                response["status"] = "ok"
            else:
                response["status"] = "failure"
            self.write_response_packet(packet, response, writer)
        else:
            logging.debug(f"unknown test packet from service: {packet}")
            self.write_response_packet(
                packet,
                {
                    "status": "error",
                    "class": "UnknownPacket",
                    "message": "Unknown or malformed test packet",
                },
                writer,
            )

    async def process_rfid_write_packet(self, packet, writer):
        """ Process a rfid_write packet """
        if self.state == State.ASLEEP:
            await self.do_process_rfid_write_packet(packet, writer)
        else:
            async with self.idle_cv:
                self.idle_queue.append((packet, writer))
                self.idle_cv.notify()

    async def do_process_rfid_write_packet(self, packet, writer):
        """ Process a rfid_write packet """
        if "uid" in packet and "picture" in packet and "app" in packet:
            uid = bytes.fromhex(packet["uid"].replace(":", ""))
            picture = packet["picture"]
            app_str = packet["app"]
            app = self._get_rfid_app_id(app_str)
            if "data" in packet:
                data = packet["data"].encode("utf8")
            else:
                data = None
            if "timeout" in packet:
                timeout = packet["timeout"]
            else:
                timeout = DEFAULT_RFID_TIMEOUT
            self.nabio.rfid_awaiting_feedback()
            try:
                success = await asyncio.wait_for(
                    self.nabio.rfid.write(uid, picture, app, data),
                    timeout=timeout,
                )
                if success:
                    self.write_response_packet(
                        packet, {"status": "ok", "uid": packet["uid"]}, writer
                    )
                else:
                    self.write_response_packet(
                        packet,
                        {"status": "error", "uid": packet["uid"]},
                        writer,
                    )
            except asyncio.TimeoutError:
                self.write_response_packet(
                    packet,
                    {
                        "status": "timeout",
                        "message": "RFID write timed out "
                        "(RFID tag not found?)",
                    },
                    writer,
                )
            finally:
                self.nabio.rfid_done_feedback()
        else:
            logging.debug(
                f"Malformed rfid_write packet from service: {packet}"
            )
            self.write_response_packet(
                packet,
                {
                    "status": "error",
                    "class": "UnknownPacket",
                    "message": "Unknown or malformed rfid_write packet",
                },
                writer,
            )

    async def process_os_shutdown_packet(self, packet, writer):
        self.write_response_packet(packet, {"status": "ok"}, writer)
        if "mode" in packet:
            perform_reboot = packet["mode"] == "reboot"
        else:
            perform_reboot = False
        asyncio.ensure_future(self._shutdown(perform_reboot))

    async def process_packet(self, packet, writer):
        """
        Process a packet from a service
        Thread: service_loop
        """
        logging.debug(f"packet from service: {packet}")
        if "type" in packet:
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
                    {
                        "status": "error",
                        "class": "UnknownPacket",
                        "message": "Unknown type " + str(packet["type"]),
                    },
                    writer,
                )
        else:
            self.write_response_packet(
                packet,
                {
                    "status": "error",
                    "class": "MalformedPacket",
                    "message": "Missing type slot",
                },
                writer,
            )

    def write_packet(self, response, writer):
        writer.write((json.dumps(response) + "\r\n").encode("utf8"))

    def _test_event_mask(self, event_type, events):
        matching = event_type in events
        if not matching and "/" in event_type:
            event_type0 = event_type.split("/", 1)[0]
            matching = event_type0 + "/*" in events
        return matching

    def broadcast_event(self, event_type, response):
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

    def write_response_cancelable(self, original_packet, writer):
        if self.playing_canceled:
            status = "canceled"
        else:
            status = "ok"
        self.write_response_packet(original_packet, {"status": status}, writer)

    def write_response_packet(self, original_packet, template, writer):
        response_packet = template
        if "request_id" in original_packet:
            response_packet["request_id"] = original_packet["request_id"]
        response_packet["type"] = "response"
        self.write_packet(response_packet, writer)

    def broadcast_state(self):
        for sw in self.service_writers:
            self.write_state_packet(sw)

    def write_state_packet(self, writer):
        self.write_packet({"type": "state", "state": self.state.value}, writer)

    # Handle service through TCP/IP protocol
    async def service_loop(self, reader, writer):
        self.write_state_packet(writer)
        self.service_writers[writer] = []
        try:
            while not reader.at_eof():
                line = await reader.readline()
                if line != b"" and line != b"\r\n":
                    try:
                        packet = json.loads(line.decode("utf8"))
                        await self.process_packet(packet, writer)
                    except UnicodeDecodeError as e:
                        logging.debug(f"Unicode Error {e} with service packet")
                        logging.debug(f"{packet}")
                        self.write_packet(
                            {
                                "type": "response",
                                "status": "error",
                                "class": "UnicodeDecodeError",
                                "message": str(e),
                            },
                            writer,
                        )
                    except json.decoder.JSONDecodeError as e:
                        logging.debug(f"JSON Error {e} with service packet")
                        logging.debug(f"{line}")
                        self.write_packet(
                            {
                                "type": "response",
                                "status": "error",
                                "class": "JSONDecodeError",
                                "message": str(e),
                            },
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

    async def perform(self, packet, writer):
        if "request_id" in packet:
            self.playing_request_id = packet["request_id"]
        self.playing_cancelable = (
            "cancelable" not in packet or packet["cancelable"]
        )
        self.playing_canceled = False
        if packet["type"] == "command":
            await self.nabio.play_sequence(packet["sequence"])
        else:
            signature = {}
            if "signature" in packet:
                signature = packet["signature"]
            await self.nabio.play_message(signature, packet["body"])
        self.write_response_cancelable(packet, writer)
        self.playing_request_id = None
        self.playing_cancelable = False

    def button_callback(self, button_event, event_time):
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
        await self.transition_to(State.RECORDING)
        await self.nabio.start_acquisition(self.asr.decode_chunk)

    async def stop_asr(self):
        await self.nabio.end_acquisition()
        now = time.time()
        decoded_str = await self.asr.get_decoded_string(True)
        # ASR model needs to be improved, log outcome.
        logging.debug(f"ASR string: {decoded_str}")
        response = await self.nlu.interpret(decoded_str)
        logging.debug(f"NLU response: {str(response)}")
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
        inTesting = os.path.basename(sys.argv[0]) in ("pytest", "py.test")
        if not inTesting:
            logging.debug(f"Initiating system command : {sytemCommandStr}")
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
                self.write_packet(
                    {"type": "ear_event", "ear": ear_str},
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
                self.broadcast_event(
                    "ears",
                    {"type": "ears_event", "left": left, "right": right},
                )

    def rfid_callback(self, uid, picture, app, app_data, flags):
        # bytes.hex(sep) is python 3.8+
        uid_str = ":".join("{:02x}".format(c) for c in uid)
        packet = {"type": "rfid_event", "uid": uid_str}
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
                    self.service_loop, "localhost", NabService.PORT_NUMBER
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
            print(traceback.format_exc())
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
        if not self.loop.is_closed():
            self.loop.call_soon_threadsafe(lambda: self.loop.stop())

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
        usage = (
            f"nabd [options]\n"
            f" -h                  display this message\n"
            f" --pidfile=<pidfile> define pidfile (default = {pidfilepath})\n"
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
        pidfile = PIDLockFile(pidfilepath, timeout=-1)
        try:
            with pidfile:
                from .nabio_hw import NabIOHW

                nabio = NabIOHW()
                Nabd.leds_boot(nabio, 1)
                nabd = Nabd(nabio)
                nabd.run()
        except AlreadyLocked:
            print(f"nabd already running? (pid={pidfile.read_pid()})")
            exit(1)
        except LockFailed:
            print(
                f"Cannot write pid file to {pidfilepath}, please fix "
                f"permissions"
            )
            exit(1)


if __name__ == "__main__":
    Nabd.main(sys.argv[1:])
