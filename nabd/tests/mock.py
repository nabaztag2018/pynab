import asyncio
import functools
import threading
import time
from unittest import TestCase
from nabcommon import nabservice
from nabd.nabio import NabIO
from nabd.ears import Ears
from nabd.leds import Leds, Led
from nabd.rfid import Rfid
from nabd.sound import Sound


class NabIOMock(NabIO):
    def __init__(self):
        super().__init__()
        self.leds = LedsMock()
        self.ears = EarsMock()
        self.rfid = RfidMock()
        self.sound = SoundMock()
        self.played_infos = []
        self.played_sequences = []
        self.called_list = []
        self.left_ear = 0
        self.right_ear = 0

    async def setup_ears(self, left_ear, right_ear):
        self.left_ear = left_ear
        self.right_ear = right_ear
        self.called_list.append(f"setup_ears({left_ear}, {right_ear})")

    async def move_ears(self, left_ear, right_ear):
        self.left_ear = left_ear
        self.right_ear = right_ear
        self.called_list.append(f"move_ears({left_ear}, {right_ear})")

    async def detect_ears_positions(self):
        self.called_list.append("detect_ears_positions()")
        return (self.left_ear, self.right_ear)

    def set_leds(self, nose, left, center, right, bottom):
        self.left_led = left
        self.center_led = center
        self.right_led = right
        self.nose_led = nose
        self.bottom_led = bottom

    def pulse(self, led, color):
        if led == Led.NOSE:
            self.nose_led = f"pulse({color})"
        elif led == Led.LEFT:
            self.left_led = f"pulse({color})"
        elif led == Led.CENTER:
            self.left_center = f"pulse({color})"
        elif led == Led.RIGHT:
            self.left_right = f"pulse({color})"
        elif led == Led.BOTTOM:
            self.bottom_led = f"pulse({color})"

    def bind_button_event(self, loop, callback):
        self.button_event_cb = {"callback": callback, "loop": loop}

    def bind_ears_event(self, loop, callback):
        self.ears_event_cb = {"callback": callback, "loop": loop}

    def bind_rfid_event(self, loop, callback):
        self.rfid.on_detect(loop, callback)

    async def play_info(self, condvar, tempo, colors):
        self.played_infos.append({"tempo": tempo, "colors": colors})
        try:
            await asyncio.wait_for(condvar.wait(), NabIO.INFO_LOOP_LENGTH)
        except asyncio.TimeoutError:
            pass

    async def play_sequence(self, sequence):
        self.played_sequences.append(sequence)
        await super().play_sequence(sequence)

    def button(self, button_event):
        self.button_event_cb.loop.call_soon_threadsafe(
            self.button_event_cb.callback, button_event
        )

    def ears(self, left, right):
        self.ears_event_cb.loop.call_soon_threadsafe(
            self.ears_event_cb.callback, left, right
        )

    def has_sound_input(self):
        return False

    def has_rfid(self):
        return False

    async def gestalt(self):
        return {"model": "Test mock"}

    def test(self, test):
        return True


class EarsMock(Ears):
    def __init__(self):
        self.called_list = []
        self.left = 0
        self.right = 0

    def on_move(self, loop, callback):
        self.called_list.append("on_move()")
        self.cb = (loop, callback)

    async def reset_ears(self, target_left, target_right):
        self.called_list.append(f"reset_ears({target_left},{target_right})")

    async def move(self, ear, delta, direction):
        self.called_list.append(f"move({ear},{delta},{direction})")
        if ear == Ears.LEFT_EAR:
            self.left = (self.left + delta) % Ears.STEPS
        else:
            self.right = (self.right + delta) % Ears.STEPS

    async def detect_positions(self):
        self.called_list.append("detect_positions()")
        return (self.left, self.right)

    async def get_positions(self):
        self.called_list.append("get_positions()")
        return (self.left, self.right)

    async def go(self, ear, position, direction):
        self.called_list.append(f"go({ear},{position},{direction})")
        if ear == Ears.LEFT_EAR:
            self.left = position % Ears.STEPS
        else:
            self.right = position % Ears.STEPS

    async def wait_while_running(self):
        self.called_list.append("wait_while_running()")

    async def is_broken(self, ear):
        self.called_list.append(f"is_broken({ear})")
        return False


class LedsMock(Leds):
    def __init__(self):
        self.called_list = []

    def set1(self, led, red, green, blue):
        self.called_list.append(f"set1({led},{red},{green},{blue})")

    def pulse(self, led, red, green, blue):
        self.called_list.append(f"pulse({led},{red},{green},{blue})")

    def setall(self, red, green, blue):
        self.called_list.append(f"setall({red},{green},{blue})")


class SoundMock(Sound):
    def __init__(self):
        self.called_list = []

    async def start_playing_preloaded(self, filename):
        self.called_list.append(f"start_playing_preloaded({filename})")

    async def wait_until_done(self, event=None):
        self.called_list.append("wait_until_done({event})")
        if event:
            try:
                await asyncio.wait_for(event.wait(), 1.0)
            except asyncio.TimeoutError:
                pass
        else:
            await asyncio.sleep(1.0)

    async def stop_playing(self):
        self.called_list.append("stop_playing()")

    async def start_recording(self, stream_cb):
        self.called_list.append("start_recording()")

    async def stop_recording(self):
        self.called_list.append("stop_recording()")

    async def preload(self, res):
        return res


class RfidMock(Rfid):
    def __init__(self):
        self.called_list = []
        self.cb = None

    def on_detect(self, loop, callback):
        self.called_list.append("on_detect()")
        self.cb = (loop, callback)

    async def write(self, uid, picture, app, data):
        self.called_list.append(f"write({uid},{picture},{app},{data})")
        if hasattr(self, "write_handler"):
            return self.write_handler(uid, picture, app, data)
        return True

    def enable_polling(self):
        self.called_list.append("enable_polling")

    def disable_polling(self):
        self.called_list.append("enable_polling")

    def send_detect_event(self, uid, picture, app, data, flags):
        (loop, callback) = self.cb
        partial = functools.partial(callback, uid, picture, app, data, flags)
        loop.call_soon_threadsafe(partial)


class NabdMockTestCase(TestCase):
    """
    Base class to test services, starting a mock nabd handler in a separate
    thread.
    """

    async def mock_nabd_service_handler(self, reader, writer):
        self.service_writer = writer
        if (
            hasattr(self, "mock_connection_handler")
            and self.mock_connection_handler is not None
        ):
            await self.mock_connection_handler(reader, writer)

    def mock_nabd_thread_entry_point(self, kwargs):
        self.mock_nabd_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.mock_nabd_loop)
        server_task = self.mock_nabd_loop.create_task(
            asyncio.start_server(
                self.mock_nabd_service_handler,
                "localhost",
                nabservice.NabService.PORT_NUMBER,
            )
        )
        try:
            self.mock_nabd_loop.run_forever()
        finally:
            server = server_task.result()
            server.close()
            if self.service_writer:
                self.service_writer.close()
            self.mock_nabd_loop.close()

    def setUp(self):
        self.service_writer = None
        self.mock_nabd_loop = None
        self.mock_nabd_thread = threading.Thread(
            target=self.mock_nabd_thread_entry_point, args=[self]
        )
        self.mock_nabd_thread.start()
        time.sleep(1)

    def tearDown(self):
        self.mock_nabd_loop.call_soon_threadsafe(
            lambda: self.mock_nabd_loop.stop()
        )
        self.mock_nabd_thread.join(3)
        if self.mock_nabd_thread.is_alive():
            raise RuntimeError("mock_nabd_thread still running")

    async def connect_handler(self, reader, writer):
        writer.write(b'{"type":"state","state":"idle"}\r\n')
        self.connect_handler_called += 1

    def do_test_connect(self, service_cls):
        self.mock_connection_handler = self.connect_handler
        self.connect_handler_called = 0
        this_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(this_loop)
        this_loop.call_later(1, lambda: this_loop.stop())
        service = service_cls()
        service.run()
        self.assertEqual(self.connect_handler_called, 1)


class MockWriter(object):
    def __init__(self):
        self.written = []

    def write(self, packet):
        self.written.append(packet)

    async def drain(self):
        pass
