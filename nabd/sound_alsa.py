import asyncio
import collections
from concurrent.futures import ThreadPoolExecutor
import functools
import re
import six
import traceback
import wave

import alsaaudio
from mpg123 import Mpg123

from .nabio import NabIO
from .sound import Sound


class SoundAlsa(Sound):

  def __init__(self, hw_model):

    if hw_model == NabIO.MODEL_2018:
      self.playback_device, self.snd_card_idx, = SoundAlsa.select_device(False)
      self.playback_mixer = None
      self.record_device = 'null'
      self.record_mixer = None
    if hw_model == NabIO.MODEL_2019_TAG or hw_model == NabIO.MODEL_2019_TAGTAG:
      self.playback_device, self.snd_card_idx, = SoundAlsa.select_device(False)
      self.playback_mixer = alsaaudio.Mixer(control='Playback', cardindex=self.snd_card_idx, device=self.playback_device)
      self.record_device, snd_card_idx, = SoundAlsa.select_device(True)

      if snd_card_idx != -1:
        assert self.snd_card_idx == snd_card_idx or snd_card_idx == -1
        self.record_mixer = alsaaudio.Mixer(control='Capture', cardindex=self.snd_card_idx, device=self.record_device)
      else:
        self.record_mixer = None
    self.executor = ThreadPoolExecutor(max_workers=1)
    self.future = None
    self.currently_playing = False
    self.currently_recording = False

  @staticmethod
  def sound_card():
    it = filter(functools.partial(str.__eq__, "seeed2micvoicec"), alsaaudio.cards())
    sound_card = next(it, None)
    if sound_card is None:
      raise RuntimeError('No sound card found by ALSA (are drivers missing?)')
    if next(it, None) is not None:
      raise RuntimeError('More than one sound card was found')
    return sound_card

  @staticmethod
  def select_device(record):
    """
    Automatically select a suitable ALSA device by trying to configure them.
    """
    if record:
      pcms_list = alsaaudio.pcms(alsaaudio.PCM_CAPTURE)
    else:
      pcms_list = alsaaudio.pcms()

    if not SoundAlsa.__SND_CARD_IDX_BY_NAME:
      matchers = tuple(filter(None, map(SoundAlsa.__SND_CARD_EXTRACTOR.match, alsaaudio.pcms())))
      snd_card_idx_by_name = collections.OrderedDict((m[1], None,) for m in matchers)
      SoundAlsa.__SND_CARD_IDX_BY_NAME = {name:idx for idx, name, in  enumerate(six.iterkeys(snd_card_idx_by_name))}

    matchers = tuple(filter(None, map(SoundAlsa.__SND_CARD_EXTRACTOR.match, pcms_list)))

    for matcher in matchers:
      device, snd_card_idx, = matcher[0], SoundAlsa.__SND_CARD_IDX_BY_NAME[matcher[1]]
      if SoundAlsa.test_device(device, snd_card_idx, record):
        return (device, snd_card_idx,)
    if record:
      print('No suitable ALSA device (v1 card?)')
    else:
      print('No suitable ALSA device!')
    return ('null', -1,)

  @staticmethod
  def test_device(device, snd_card_idx, record):
    """
      Test an ALSA device, making sure it handles both stereo and mono and
      both 44.1KHz and 22.05KHz. On a typical RPI configuration, default with
      hifiberry card is not configured to do software-mono, so we'll use
      'sysdefault:CARD=sndrpihifiberry' instead.

      @param device: name of the sound device
      @type device: six.text_type
      @param snd_card_idx: index of the sound card
      @type snd_card_idx: int
      @param record: C{True} if this method is looking for recording device. C{False} if the device should
      only playback.
      @type record: bool
    """
    try:
      dev = None

      if record is False:
        _ = alsaaudio.Mixer(control='Playback', cardindex=snd_card_idx, device=device)
      else:
        assert record is True
        _ = alsaaudio.Mixer(control='Capture', cardindex=snd_card_idx, device=device)

      if record:
        dev = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, cardindex=snd_card_idx, device=device)
      else:
        dev = alsaaudio.PCM(device=device, cardindex=snd_card_idx,)

      try:
        if dev.setformat(alsaaudio.PCM_FORMAT_S16_LE) != alsaaudio.PCM_FORMAT_S16_LE:
          return False
        if record:
          if dev.setchannels(1) != 1:
            return False
          if dev.setrate(16000) != 16000:
            return False
        else:
          if dev.setchannels(2) != 2:
            return False
          if dev.setchannels(1) not in (1, 2,):
            return False
          if dev.setrate(44100) != 44100:
            return False
          if dev.setrate(22050) != 22050:
            return False
      finally:
        dev.close()

    except alsaaudio.ALSAAudioError:
      return False

    return True

  async def start_playing_preloaded(self, filename):
    await self.stop_playing()
    self.currently_playing = True
    self.future = asyncio.get_event_loop().run_in_executor(self.executor, lambda f=filename: self._play(f))

  def _play(self, filename):
    try:
      device = alsaaudio.PCM(device=self.playback_device, cardindex=self.snd_card_idx)
      if filename.endswith('.wav'):
        with wave.open(filename, 'rb') as f:
          channels = f.getnchannels()
          width = f.getsampwidth()
          rate = f.getframerate()
          self._setup_device(device, channels, rate, width)
          periodsize = int(rate / 10)  # 1/10th of second
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
        periodsize = int(rate / 10)  # 1/10th of second
        device.setperiodsize(periodsize)
        target_chunk_size = periodsize * width * channels
        chunk = bytearray(0)
        for frames in mp3.iter_frames():
          if len(chunk) + len(frames) < target_chunk_size:
            chunk = chunk + frames
          else:
            remaining = target_chunk_size - len(chunk)
            chunk = chunk + frames[:remaining]
            device.write(chunk)
            chunk = frames[remaining:]
          if not self.currently_playing:
            break
        if len(chunk) > 0:
          remaining = target_chunk_size - len(chunk)
          chunk = chunk + bytearray(remaining)
          device.write(chunk)
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

  async def stop_playing(self):
    if self.currently_playing:
      self.currently_playing = False
    await self.wait_until_done()

  async def wait_until_done(self):
    if self.future:
      await self.future
    self.future = None

  async def start_recording(self, stream_cb):
    await self.stop_playing()
    self.currently_recording = True
    self.future = asyncio.get_event_loop().run_in_executor(self.executor, lambda cb=stream_cb: self._record(cb))

  def _record(self, cb):
    inp = None
    try:
      inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL, device='default', cardindex=self.snd_card_idx)
      ch = inp.setchannels(1)
      rate = inp.setrate(16000)
      format = inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
      inp.setperiodsize(1600)  # 100ms
      finalize = False
      while not finalize:
        l, data = inp.read()
        if not self.currently_recording:
          finalize = True
        if l or finalize:
          cb(data, finalize)
    except Exception:
      print(traceback.format_exc())
    finally:
      self.currently_recording = False
      if inp:
        inp.close()

  async def stop_recording(self):
    if self.currently_recording:
      self.currently_recording = False
    await self.wait_until_done()

  __SND_CARD_IDX_BY_NAME = {}
  """ Mapping of sound card indexes as understood by pyalsaaudio by the sound card name"""

  __SND_CARD_EXTRACTOR = re.compile("^[^:]+:CARD=([^,]+),DEV=\d+$")
  """ Compiled regex extracting the name of the card found in the first group """
