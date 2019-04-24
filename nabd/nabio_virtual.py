import asyncio
from . import nabio

class NabIOVirtual(nabio.NabIO):
  """ Virtual implementation for testing purposes """

  async def setup_ears(self, left_ear, right_ear):
    pass

  async def move_ears(self, left_ear, right_ear):
    print('move_ears left_ear={left_ear}, right_ear={right_ear}'.format(left_ear=left_ear, right_ear=right_ear))

  async def detect_ears_positions(self):
    return (0, 0)


  def set_leds(self, nose, left, center, right, bottom):
    print('set_leds left={left}, center={center}, right={right}, nose={nose}, bottom={bottom}'.format(left=left, center=center, right=right, nose=nose, bottom=bottom))

  def bind_button_event(self, loop, callback):
    self.button_event_cb = {'callback': callback, 'loop': loop}

  def bind_ears_event(self, loop, callback):
    self.ears_event_cb = {'callback': callback, 'loop': loop}

  async def play_info(self, condvar, tempo, colors):
    print('play_info tempo={tempo}, colors={colors}'.format(tempo=tempo, colors=colors))
    try:
      await asyncio.wait_for(self.idle_cv.wait(), NabIO.INFO_LOOP_LENGTH)
    except asyncio.TimeoutError:
      pass

  async def play_sequence(self, sequence):
    print('play_sequence sequence={sequence}'.format(sequence=sequence))
    await asyncio.sleep(10)

  def cancel(self):
    pass
