import asyncio
import time
import sys

from .button_gpio import ButtonGPIO
from .ears import Ears
from .ears_dev import EarsDev
from .leds import Leds
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
            (Leds.LED_NOSE, nose),
            (Leds.LED_LEFT, left),
            (Leds.LED_CENTER, center),
            (Leds.LED_RIGHT, right),
            (Leds.LED_BOTTOM, bottom),
        ]:
            if led is None:
                (r, g, b) = (0, 0, 0)
            else:
                (r, g, b) = led
            self.leds.set1(led_ix, r, g, b)

    def pulse(self, led_ix, color):
        (r, g, b) = color
        self.leds.pulse(led_ix, r, g, b)

    def bind_button_event(self, loop, callback):
        self.button.on_event(loop, callback)

    def bind_ears_event(self, loop, callback):
        self.ears.on_move(loop, callback)

    async def play_info(self, condvar, tempo, colors):
        animation = [NabIOHW._convert_info_color(color) for color in colors]
        step_ms = tempo * 10
        start = time.time()
        index = 0
        while time.time() - start < NabIO.INFO_LOOP_LENGTH:
            step = animation[index]
            for led_ix, rgb in step:
                r, g, b = rgb
                self.leds.set1(led_ix, r, g, b)
            if await NabIOHW._wait_on_condvar(condvar, step_ms):
                index = (index + 1) % len(animation)
            else:
                break

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
            (Leds.LED_LEFT, "left"),
            (Leds.LED_CENTER, "center"),
            (Leds.LED_RIGHT, "right"),
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

    def cancel(self):
        pass

    def has_sound_input(self):
        return self.model != NabIOHW.MODEL_2018

    def gestalt(self):
        MODEL_NAMES = {
            NabIO.MODEL_2018:"2018",
            NabIO.MODEL_2019_TAG:"2019_TAG",
            NabIO.MODEL_2019_TAGTAG:"2019_TAGTAG",
        }
        if self.model in MODEL_NAMES:
            model_name = MODEL_NAMES[self.model]
        else:
            model_name = f"Unknown model {self.model}"
        left_ear_position, right_ear_position = self.ears.get_positions()
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
            "left_ear_status": left_ear_status,
            "right_ear_status": right_ear_status,
        }

    @staticmethod
    def detect_model():
        _, sound_configuration, _, = SoundAlsa.sound_configuration()

        if sound_configuration == SoundAlsa.MODEL_2019_CARD_NAME:
            return NabIO.MODEL_2019_TAGTAG
        if sound_configuration == SoundAlsa.MODEL_2018_CARD_NAME:
            return NabIO.MODEL_2018
