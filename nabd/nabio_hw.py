import asyncio
import time

from .button_gpio import ButtonGPIO
from .ears import Ears
from .ears_dev import EarsDev
from .rfid_dev import RfidDev
from .leds import Led
from .leds_neopixel import LedsNeoPixel
from .nabio import NabIO
from .sound_alsa import SoundAlsa


class NabIOHW(NabIO):
    """
    Implementation of nabio for Raspberry Pi hardware.
    """

    def __init__(self):
        super().__init__()
        self.model = NabIOHW.detect_model()
        self.leds = LedsNeoPixel()
        self.ears = EarsDev()
        self.rfid = RfidDev()
        self.sound = SoundAlsa(self.model)
        self.button = ButtonGPIO(self.model)

    async def setup_ears(self, left_ear, right_ear):
        await self.ears.reset_ears(left_ear, right_ear)

    async def move_ears(self, left_ear, right_ear):
        await self.ears.go(Ears.LEFT_EAR, left_ear, Ears.FORWARD_DIRECTION)
        await self.ears.go(Ears.RIGHT_EAR, right_ear, Ears.FORWARD_DIRECTION)
        await self.ears.wait_while_running()

    async def detect_ears_positions(self):
        return await self.ears.detect_positions()

    def set_leds(self, nose, left, center, right, bottom):
        for (led_ix, led) in [
            (Led.NOSE, nose),
            (Led.LEFT, left),
            (Led.CENTER, center),
            (Led.RIGHT, right),
            (Led.BOTTOM, bottom),
        ]:
            if led is None:
                (r, g, b) = (0, 0, 0)
            else:
                (r, g, b) = led
            self.leds.set1(led_ix, r, g, b)

    def pulse(self, led_ix, color):
        (r, g, b) = color
        self.leds.pulse(led_ix, r, g, b)

    def rfid_awaiting_feedback(self):
        self.leds.set1(Led.NOSE, 255, 0, 0)

    def bind_button_event(self, loop, callback):
        self.button.on_event(loop, callback)

    def bind_ears_event(self, loop, callback):
        self.ears.on_move(loop, callback)

    def bind_rfid_event(self, loop, callback):
        self.rfid.on_detect(loop, callback)

    async def play_info(self, condvar, tempo, colors):
        animation = [NabIOHW._convert_info_color(color) for color in colors]
        step_ms = tempo * 10
        start = time.time()
        index = 0
        notified = False
        while time.time() - start < NabIO.INFO_LOOP_LENGTH:
            step = animation[index]
            for led_ix, rgb in step:
                r, g, b = rgb
                self.leds.set1(led_ix, r, g, b)
            if await NabIOHW._wait_on_condvar(condvar, step_ms):
                index = (index + 1) % len(animation)
            else:
                notified = True
                break
        self.clear_info()
        return notified

    def clear_info(self):
        for led in (Led.LEFT, Led.CENTER, Led.RIGHT):
            self.leds.set1(led, 0, 0, 0)

    @staticmethod
    async def _wait_on_condvar(condvar, ms):
        timeout = False
        try:
            await asyncio.wait_for(condvar.wait(), ms / 1000)
        except asyncio.TimeoutError:
            timeout = True
        return timeout

    @staticmethod
    def _convert_info_color(color):
        animation = []
        for led_ix, led in [
            (Led.LEFT, "left"),
            (Led.CENTER, "center"),
            (Led.RIGHT, "right"),
        ]:
            values = []
            if color[led]:
                int_value = int(color[led], 16)
                values.append((int_value >> 16) & 0xFF)  # r
                values.append((int_value >> 8) & 0xFF)  # g
                values.append(int_value & 0xFF)  # b
            else:
                values.append(0)
                values.append(0)
                values.append(0)
            animation.append((led_ix, values))
        return animation

    def has_sound_input(self):
        return self.model != NabIOHW.MODEL_2018

    def has_rfid(self):
        return self.model == NabIOHW.MODEL_2019_TAGTAG

    async def gestalt(self):
        MODEL_NAMES = {
            NabIO.MODEL_2018: "2018",
            NabIO.MODEL_2019_TAG: "2019_TAG",
            NabIO.MODEL_2019_TAGTAG: "2019_TAGTAG",
        }
        if self.model in MODEL_NAMES:
            model_name = MODEL_NAMES[self.model]
        else:
            model_name = f"Unknown model {self.model}"
        left_ear_position, right_ear_position = await self.ears.get_positions()
        if self.ears.is_broken(Ears.LEFT_EAR):
            left_ear_status = "broken"
        else:
            if left_ear_position is None:
                left_ear_status = f"ok (position unknown)"
            else:
                left_ear_status = f"ok (position={left_ear_position})"
        if self.ears.is_broken(Ears.RIGHT_EAR):
            right_ear_status = "broken"
        else:
            if right_ear_position is None:
                right_ear_status = f"ok (position unknown)"
            else:
                right_ear_status = f"ok (position={right_ear_position})"
        return {
            "model": model_name,
            "sound_card": self.sound.get_sound_card(),
            "sound_input": self.has_sound_input(),
            "rfid": self.has_rfid(),
            "left_ear_status": left_ear_status,
            "right_ear_status": right_ear_status,
        }

    async def test(self, test):
        if test == "ears":
            (
                left_ear_position,
                right_ear_position,
            ) = await self.ears.get_positions()
            await self.ears.go(Ears.LEFT_EAR, 8, Ears.BACKWARD_DIRECTION)
            await self.ears.go(Ears.RIGHT_EAR, 8, Ears.BACKWARD_DIRECTION)
            await self.ears.wait_while_running()
            for x in range(0, 17):
                await self.ears.move(Ears.LEFT_EAR, 1, Ears.FORWARD_DIRECTION)
                await self.ears.move(
                    Ears.RIGHT_EAR, 1, Ears.BACKWARD_DIRECTION
                )
                await self.ears.wait_while_running()
                await asyncio.sleep(0.2)
            for x in range(0, 17):
                await self.ears.move(Ears.LEFT_EAR, 1, Ears.BACKWARD_DIRECTION)
                await self.ears.move(Ears.RIGHT_EAR, 1, Ears.FORWARD_DIRECTION)
                await self.ears.wait_while_running()
                await asyncio.sleep(0.2)
            await self.ears.go(Ears.LEFT_EAR, 0, Ears.FORWARD_DIRECTION)
            await self.ears.go(Ears.RIGHT_EAR, 0, Ears.FORWARD_DIRECTION)
            await self.ears.wait_while_running()
            if left_ear_position is not None:
                await self.ears.go(
                    Ears.LEFT_EAR, left_ear_position, Ears.FORWARD_DIRECTION
                )
            if right_ear_position is not None:
                await self.ears.go(
                    Ears.RIGHT_EAR, right_ear_position, Ears.FORWARD_DIRECTION
                )
            await self.ears.wait_while_running()
            if self.ears.is_broken(Ears.LEFT_EAR):
                return False
            if self.ears.is_broken(Ears.RIGHT_EAR):
                return False
            return True
        elif test == "leds":
            for color in [
                (0, 0, 0),
                (255, 0, 0),
                (0, 255, 0),
                (0, 0, 255),
                (255, 255, 255),
                (127, 127, 127),
                (0, 0, 0),
            ]:
                r, g, b = color
                for led_ix in [
                    Led.NOSE,
                    Led.LEFT,
                    Led.CENTER,
                    Led.RIGHT,
                    Led.BOTTOM,
                ]:
                    self.leds.set1(led_ix, r, g, b)
                    await asyncio.sleep(0.2)
                await asyncio.sleep(1.0)
            return True
        else:
            return False

    @staticmethod
    def detect_model():
        _, sound_configuration, _, = SoundAlsa.sound_configuration()

        if sound_configuration == SoundAlsa.MODEL_2019_CARD_NAME:
            if RfidDev.is_available():
                return NabIO.MODEL_2019_TAGTAG
            else:
                return NabIO.MODEL_2019_TAG
        if sound_configuration == SoundAlsa.MODEL_2018_CARD_NAME:
            return NabIO.MODEL_2018
