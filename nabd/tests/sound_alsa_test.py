import unittest
import asyncio
import sys
import pytest
import time
import wave

@pytest.mark.skipif(sys.platform != 'linux', reason="Alsa is only available on Linux")
@pytest.mark.django_db
class TestPlaySound(unittest.TestCase):
  def setUp(self):
    from nabd.sound_alsa import SoundAlsa
    from nabd.nabio import NabIO
    self.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(self.loop)
    try:
      if SoundAlsa.sound_card() == 'sndrpihifiberry':
        model = NabIO.MODEL_2018
      else:
        if SoundAlsa.sound_card() == 'seeed2micvoicec':
          model = NabIO.MODEL_2019_TAGTAG
        else:
          raise unittest.SkipTest("No compatible sound card found")
    except RuntimeError as error:
      raise unittest.SkipTest("Runtime error getting sound card %s", error.message)
    self.sound = SoundAlsa(model)

  def test_mp3(self):
    start_task = self.loop.create_task(self.sound.start_playing('choreographies/3notesE5A5C6.mp3'))
    self.loop.run_until_complete(start_task)
    wait_task = self.loop.create_task(self.sound.wait_until_done())
    self.loop.run_until_complete(wait_task)

  def test_two_mp3s(self):
    start_task = self.loop.create_task(self.sound.start_playing('choreographies/3notesA4G5G5.mp3'))
    self.loop.run_until_complete(start_task)
    wait_task = self.loop.create_task(self.sound.wait_until_done())
    self.loop.run_until_complete(wait_task)
    start_task = self.loop.create_task(self.sound.start_playing('choreographies/2notesE5E4.mp3'))
    self.loop.run_until_complete(start_task)
    wait_task = self.loop.create_task(self.sound.wait_until_done())
    self.loop.run_until_complete(wait_task)

  def test_two_wavs(self):
    start_task = self.loop.create_task(self.sound.start_playing('nabmastodond/communion.wav'))
    self.loop.run_until_complete(start_task)
    wait_task = self.loop.create_task(self.sound.wait_until_done())
    self.loop.run_until_complete(wait_task)
    start_task = self.loop.create_task(self.sound.start_playing('nabmastodond/communion.wav'))
    self.loop.run_until_complete(start_task)
    wait_task = self.loop.create_task(self.sound.wait_until_done())
    self.loop.run_until_complete(wait_task)

  def test_wav(self):
    start_task = self.loop.create_task(self.sound.start_playing('nabmastodond/communion.wav'))
    self.loop.run_until_complete(start_task)
    wait_task = self.loop.create_task(self.sound.wait_until_done())
    self.loop.run_until_complete(wait_task)

@pytest.mark.skipif(sys.platform != 'linux', reason="Alsa is only available on Linux")
@pytest.mark.django_db
class TestRecord(unittest.TestCase):
  def setUp(self):
    from nabd.sound_alsa import SoundAlsa
    from nabd.nabio import NabIO
    self.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(self.loop)
    try:
      if SoundAlsa.sound_card() != 'seeed2micvoicec':
        raise unittest.SkipTest("Test should be run on a 2019 card only")
    except RuntimeError as error:
      raise unittest.SkipTest("Runtime error getting sound card %s", error.message)
    self.sound = SoundAlsa(NabIO.MODEL_2019_TAGTAG)
    self.recorded_raw = open('test_recording.raw', 'wb')

  def tearDown(self):
    self.recorded_raw.close()

  def test_recording_playback(self):
    import alsaaudio
    start_task = self.loop.create_task(self.sound.start_playing('asr/listen.mp3'))
    self.loop.run_until_complete(start_task)
    wait_task = self.loop.create_task(self.sound.wait_until_done())
    self.loop.run_until_complete(wait_task)
    start_task = self.loop.create_task(self.sound.start_recording(self.record_cb))
    self.loop.run_until_complete(start_task)
    time.sleep(5)
    stop_task = self.loop.create_task(self.sound.stop_recording())
    self.loop.run_until_complete(stop_task)
    start_task = self.loop.create_task(self.sound.start_playing('asr/acquired.mp3'))
    self.loop.run_until_complete(start_task)
    wait_task = self.loop.create_task(self.sound.wait_until_done())
    self.loop.run_until_complete(wait_task)

  def record_cb(self, data, finalize):
    self.recorded_raw.write(data)
