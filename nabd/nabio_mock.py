import asyncio
import nabio

class NabIOMock(nabio.NabIO):
  """ Mock for unit tests """
  def __init__(self):
    self.played_infos = []
    self.played_sequences = []

  def set_ears(self, left_ear, right_ear):
    self.left_ear = left_ear
    self.right_ear = right_ear

  def set_leds(self, left, center, right, nose, bottom):
    self.left_led = left
    self.center_led = center
    self.right_led = right
    self.nose_led = nose
    self.bottom_led = bottom

  def bind_button_event(self, loop, callback):
    self.button_event_cb = {'callback': callback, 'loop': loop}

  def bind_ears_event(self, loop, callback):
    self.ears_event_cb = {'callback': callback, 'loop': loop}

  async def play_info(self, tempo, colors):
    self.played_infos.append({'tempo':tempo, 'colors': colors})
    await asyncio.sleep(1)

  async def play_sequence(self, sequence):
    self.played_sequences.append(sequence)
    await asyncio.sleep(10)

  def cancel(self):
    pass

  def button(self, button_event):
    self.button_event_cb.loop.call_soon_threadsafe(self.button_event_cb.callback, button_event)

  def ears(self, left, right):
    self.ears_event_cb.loop.call_soon_threadsafe(self.ears_event_cb.callback, left, right)
