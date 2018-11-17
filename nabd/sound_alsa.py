import wave
from mpg123 import Mpg123
import alsaaudio
import asyncio
from concurrent.futures import ThreadPoolExecutor
from .sound import Sound

class SoundAlsa(Sound):
  def __init__(self):
    self.device = SoundAlsa.select_device()
    self.executor = ThreadPoolExecutor(max_workers=1)
    self.play_future = None
    self.currently_playing = False

  @staticmethod
  def select_device():
    """
    Automatically select a suitable ALSA device by trying to configure them.
    """
    for device in alsaaudio.pcms():
      if device != 'null':
        if SoundAlsa.test_device(device):
          return device
    print('No suitable ALSA device!')
    return 'null'

  @staticmethod
  def test_device(device):
    """
    Test an ALSA device, making sure it handles both stereo and mono and
    both 44.1KHz and 22.05KHz. On a typical RPI configuration, default with
    hifiberry card is not configured to do software-mono, so we'll use
    'sysdefault:CARD=sndrpihifiberry' instead.
    """
    try:
      dev = alsaaudio.PCM(device=device)
      if dev.setchannels(2) != 2:
        return False
      if dev.setchannels(1) != 1:
        return False
      if dev.setrate(44100) != 44100:
        return False
      if dev.setrate(22050) != 22050:
        return False
      if dev.setformat(alsaaudio.PCM_FORMAT_S16_LE) != alsaaudio.PCM_FORMAT_S16_LE:
        return False
    except alsaaudio.ALSAAudioError:
      return False
    finally:
      dev.close()
    return True

  async def start_preloaded(self, filename):
    await self.stop()
    self.currently_playing = True
    self.play_future = asyncio.get_event_loop().run_in_executor(self.executor, lambda f=filename: self._do_start(f))

  def _do_start(self, filename):
    try:
      device = alsaaudio.PCM(device=self.device)
      if filename.endswith('.wav'):
        with wave.open(filename, 'rb') as f:
          channels = f.getnchannels()
          width = f.getsampwidth()
          rate = f.getframerate()
          self._setup_device(device, channels, rate, width)
          periodsize = int(rate / 10) # 1/10th of second
          device.setperiodsize(periodsize)
          data = f.readframes(periodsize)
          chunksize = periodsize * channels * width
          while data and self.currently_playing:
            if len(data) < chunksize:
              data = data + bytearray(chunksize - len(data))
            device.write(data)
            data = f.readframes(periodsize)
      elif filename.endswith('.mp3'):
        mp3 = Mpg123(filename)
        rate, channels, encoding = mp3.get_format()
        width = mp3.get_width_by_encoding(encoding)
        self._setup_device(device, channels, rate, width)
        chunksize = None
        for chunk in mp3.iter_frames():
          if chunksize == None:
            chunksize = len(chunk)
            periodsize = int(chunksize / width / channels)
            device.setperiodsize(periodsize)
          if len(chunk) < chunksize:
            chunk = chunk + bytearray(chunksize - len(chunk))
          device.write(chunk)
          if not self.currently_playing:
            break
    finally:
      self.currently_playing = False
      device.close()

  def _setup_device(self, device, channels, rate, width):
    # Set attributes
    device.setchannels(channels)
    device.setrate(rate)

    # 8bit is unsigned in wav files
    if width == 1:
        device.setformat(alsaaudio.PCM_FORMAT_U8)
    # Otherwise we assume signed data, little endian
    elif width == 2:
        device.setformat(alsaaudio.PCM_FORMAT_S16_LE)
    elif width == 3:
        device.setformat(alsaaudio.PCM_FORMAT_S24_3LE)
    elif width == 4:
        device.setformat(alsaaudio.PCM_FORMAT_S32_LE)
    else:
        raise ValueError('Unsupported format')

  async def stop(self):
    if self.currently_playing:
      self.currently_playing = False
    await self.wait_until_done()

  async def wait_until_done(self):
    if self.play_future:
      await self.play_future
    self.play_future = None
