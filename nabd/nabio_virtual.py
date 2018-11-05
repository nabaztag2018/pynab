import asyncio
from . import nabio

class NabIOVirtual(nabio.NabIO):
  """ Virtual implementation for testing purposes """

  def set_ears(self, left_ear, right_ear):
    print(f'set_ears left_ear={left_ear}, right_ear={right_ear}')

  def set_leds(self, left, center, right, nose, bottom):
    print(f'set_leds left={left}, center={center}, right={right}, nose={nose}, bottom={bottom}')

  def bind_button_event(self, loop, callback):
    self.button_event_cb = {'callback': callback, 'loop': loop}

  def bind_ears_event(self, loop, callback):
    self.ears_event_cb = {'callback': callback, 'loop': loop}

  async def play_info(self, tempo, colors):
    print(f'play_info tempo={tempo}, colors={colors}')
    await asyncio.sleep(1)

  async def play_sequence(self, sequence):
    print(f'play_sequence sequence={sequence}')
    await asyncio.sleep(10)

  def cancel(self):
    pass
