import asyncio

from .button_gpio import ButtonGPIO
from .ears import Ears
from .ears_dev import EarsDev
from .leds import Led
from .leds_neopixel import LedsNeoPixel
from .nabio import NabIO
from .rfid_dev import RfidDev
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
                left_ear_status = "ok (position unknown)"
            else:
                left_ear_status = f"ok (position={left_ear_position})"
        if self.ears.is_broken(Ears.RIGHT_EAR):
            right_ear_status = "broken"
        else:
            if right_ear_position is None:
                right_ear_status = "ok (position unknown)"
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
        (
            _,
            sound_configuration,
            _,
        ) = SoundAlsa.sound_configuration()

        if sound_configuration == SoundAlsa.MODEL_2019_CARD_NAME:
            if RfidDev.is_available():
                return NabIO.MODEL_2019_TAGTAG
            else:
                return NabIO.MODEL_2019_TAG
        if sound_configuration == SoundAlsa.MODEL_2018_CARD_NAME:
            return NabIO.MODEL_2018
