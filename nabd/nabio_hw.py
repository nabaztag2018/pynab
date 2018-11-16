import asyncio
from .nabio import NabIO
from .ears import Ears
from .ears_gpio import EarsGPIO
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

  async def setup_ears(self, left_ear, right_ear):
    await self.ears.reset_ears()
    t1 = self.ears.go(Ears.LEFT_EAR, left_ear, 0)
    t2 = self.ears.go(Ears.RIGHT_EAR, right_ear, 1)
    await asyncio.wait([t1, t2])

  def set_ears(self, left_ear, right_ear):
    print('set_ears left_ear={left_ear}, right_ear={right_ear}'.format(left_ear=left_ear, right_ear=right_ear))

  def set_leds(self, left, center, right, nose, bottom):
    print('set_leds left={left}, center={center}, right={right}, nose={nose}, bottom={bottom}'.format(left=left, center=center, right=right, nose=nose, bottom=bottom))

  def bind_button_event(self, loop, callback):
    self.button_event_cb = {'callback': callback, 'loop': loop}

  def bind_ears_event(self, loop, callback):
    self.ears_event_cb = {'callback': callback, 'loop': loop}

  async def play_info(self, tempo, colors):
    print('play_info tempo={tempo}, colors={colors}'.format(tempo=tempo, colors=colors))
    await asyncio.sleep(1)

  def cancel(self):
    pass
