import asyncio
from .nabio import NabIO
from .ears import Ears
from .ears_gpio import EarsGPIO
from .button import Button
from .button_gpio import ButtonGPIO
from .leds_neopixel import LedsNeoPixel
from .sound_alsa import SoundAlsa

class NabIOHW(NabIO):
  """
  Implementation of nabio for Raspberry Pi hardware.
  """

  def __init__(self):
    super().__init__()
    self.leds = LedsNeoPixel()
    self.ears = EarsGPIO()
    self.sound = SoundAlsa()
    self.button = ButtonGPIO()

  async def setup_ears(self, left_ear, right_ear):
    await self.ears.reset_ears(left_ear, right_ear)

  async def move_ears(self, left_ear, right_ear):
    await self.ears.go(Ears.LEFT_EAR, left_ear, Ears.FORWARD_DIRECTION)
    await self.ears.go(Ears.RIGHT_EAR, right_ear, Ears.FORWARD_DIRECTION)
    await self.ears.wait_while_running()

  async def detect_ears_positions(self):
    return await self.ears.detect_positions()

  def set_leds(self, left, center, right, nose, bottom):
    print('set_leds left={left}, center={center}, right={right}, nose={nose}, bottom={bottom}'.format(left=left, center=center, right=right, nose=nose, bottom=bottom))

  def bind_button_event(self, loop, callback):
    self.button.on_event(loop, callback)

  def bind_ears_event(self, loop, callback):
    self.ears.on_move(loop, callback)

  async def play_info(self, tempo, colors):
    print('play_info tempo={tempo}, colors={colors}'.format(tempo=tempo, colors=colors))
    await asyncio.sleep(1)

  def cancel(self):
    pass
