import unittest
import asyncio
import sys
import pytest

@pytest.mark.skipif(sys.platform != 'linux', reason="Alsa is only available on Linux")
@pytest.mark.django_db
class TestSound(unittest.TestCase):
  def setUp(self):
    from nabd.sound_alsa import SoundAlsa
    self.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(self.loop)
    self.sound = SoundAlsa()

  def test_mp3(self):
    start_task = self.loop.create_task(self.sound.start('choreographies/3notesE5A5C6.mp3'))
    self.loop.run_until_complete(start_task)
    wait_task = self.loop.create_task(self.sound.wait_until_done())
    self.loop.run_until_complete(wait_task)

  def test_two_mp3s(self):
    start_task = self.loop.create_task(self.sound.start('choreographies/3notesA4G5G5.mp3'))
    self.loop.run_until_complete(start_task)
    wait_task = self.loop.create_task(self.sound.wait_until_done())
    self.loop.run_until_complete(wait_task)
    start_task = self.loop.create_task(self.sound.start('choreographies/2notesE5E4.mp3'))
    self.loop.run_until_complete(start_task)
    wait_task = self.loop.create_task(self.sound.wait_until_done())
    self.loop.run_until_complete(wait_task)

  def test_two_wavs(self):
    start_task = self.loop.create_task(self.sound.start('nabmastodond/communion.wav'))
    self.loop.run_until_complete(start_task)
    wait_task = self.loop.create_task(self.sound.wait_until_done())
    self.loop.run_until_complete(wait_task)
    start_task = self.loop.create_task(self.sound.start('nabmastodond/communion.wav'))
    self.loop.run_until_complete(start_task)
    wait_task = self.loop.create_task(self.sound.wait_until_done())
    self.loop.run_until_complete(wait_task)

  def test_wav(self):
    start_task = self.loop.create_task(self.sound.start('nabmastodond/communion.wav'))
    self.loop.run_until_complete(start_task)
    wait_task = self.loop.create_task(self.sound.wait_until_done())
    self.loop.run_until_complete(wait_task)
