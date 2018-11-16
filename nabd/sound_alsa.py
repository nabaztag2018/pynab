import wave
from mpg123 import Mpg123
import alsaaudio
import asyncio
from concurrent.futures import ThreadPoolExecutor
from .sound import Sound

class SoundAlsa(Sound):
  ALSA_DEVICE = 'default'

  def __init__(self):
    self.device = alsaaudio.PCM(device=SoundAlsa.ALSA_DEVICE)
    self.executor = ThreadPoolExecutor(max_workers=1)
    self.play_future = None
    self.currently_playing = False

  async def start_preloaded(self, filename):
    await self.stop()
    self.currently_playing = True
    self.play_future = asyncio.get_event_loop().run_in_executor(self.executor, lambda f=filename: self._do_start(f))

  def _do_start(self, filename):
    try:
      if filename.endswith('.wav'):
        with wave.open(args[0], 'rb') as f:
          self._setup_device(f.getnchannels(), f.getframerate(), f.getsampwidth())
          periodsize = int(f.getframerate() / 8)
          data = f.readframes(periodsize)
          while data and self.currently_playing:
            self.device.write(data)
            data = f.readframes(periodsize)
      elif filename.endswith('.mp3'):
        mp3 = Mpg123(filename)
        rate, channels, encoding = mp3.get_format()
        width = mp3.get_width_by_encoding(encoding)
        self._setup_device(channels, rate, width)
        for frame in mp3.iter_frames():
          self.device.write(frame)
    finally:
      self.currently_playing = False

  def _setup_device(self, channels, rate, width):
    # Set attributes
    self.device.setchannels(channels)
    self.device.setrate(rate)

    # 8bit is unsigned in wav files
    if width == 1:
        self.device.setformat(alsaaudio.PCM_FORMAT_U8)
    # Otherwise we assume signed data, little endian
    elif width == 2:
        self.device.setformat(alsaaudio.PCM_FORMAT_S16_LE)
    elif width == 3:
        self.device.setformat(alsaaudio.PCM_FORMAT_S24_3LE)
    elif width == 4:
        self.device.setformat(alsaaudio.PCM_FORMAT_S32_LE)
    else:
        raise ValueError('Unsupported format')

    periodsize = int(rate / 8)
    self.device.setperiodsize(periodsize)

  async def stop(self):
    if self.currently_playing:
      self.currently_playing = False
    await self.wait_until_done()

  async def wait_until_done(self):
    if self.play_future:
      await self.play_future
    self.play_future = None
