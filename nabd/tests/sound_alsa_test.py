import asyncio
import asynctest
import os
import sys
import time
import unittest
import wave
import pytest
from utils import close_old_async_connections


@pytest.mark.skipif(
    sys.platform != "linux", reason="Alsa is only available on Linux"
)
@pytest.mark.django_db
class TestPlaySound(unittest.TestCase):
    def setUp(self):
        from nabd.sound_alsa import SoundAlsa
        from nabd.nabio import NabIO

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            if SoundAlsa.sound_configuration()[1] == "sndrpihifiberry":
                model = NabIO.MODEL_2018
            else:
                if SoundAlsa.sound_configuration()[1] == "tagtagtagsound":
                    model = NabIO.MODEL_2019_TAGTAG
                else:
                    raise unittest.SkipTest("No compatible sound card found")
        except RuntimeError as error:
            raise unittest.SkipTest(
                "Runtime error getting sound card %s" % str(error)
            )
        self.sound = SoundAlsa(model)

    def tearDown(self):
        close_old_async_connections()

    def test_mp3(self):
        start_task = self.loop.create_task(
            self.sound.start_playing("choreographies/3notesE5A5C6.mp3")
        )
        self.loop.run_until_complete(start_task)
        wait_task = self.loop.create_task(self.sound.wait_until_done())
        self.loop.run_until_complete(wait_task)

    def test_two_mp3s(self):
        start_task = self.loop.create_task(
            self.sound.start_playing("choreographies/3notesA4G5G5.mp3")
        )
        self.loop.run_until_complete(start_task)
        wait_task = self.loop.create_task(self.sound.wait_until_done())
        self.loop.run_until_complete(wait_task)
        start_task = self.loop.create_task(
            self.sound.start_playing("choreographies/2notesE5E4.mp3")
        )
        self.loop.run_until_complete(start_task)
        wait_task = self.loop.create_task(self.sound.wait_until_done())
        self.loop.run_until_complete(wait_task)

    def test_two_wavs(self):
        start_task = self.loop.create_task(
            self.sound.start_playing("nabmastodond/communion.wav")
        )
        self.loop.run_until_complete(start_task)
        wait_task = self.loop.create_task(self.sound.wait_until_done())
        self.loop.run_until_complete(wait_task)
        start_task = self.loop.create_task(
            self.sound.start_playing("nabmastodond/communion.wav")
        )
        self.loop.run_until_complete(start_task)
        wait_task = self.loop.create_task(self.sound.wait_until_done())
        self.loop.run_until_complete(wait_task)

    def test_wav(self):
        start_task = self.loop.create_task(
            self.sound.start_playing("nabmastodond/communion.wav")
        )
        self.loop.run_until_complete(start_task)
        wait_task = self.loop.create_task(self.sound.wait_until_done())
        self.loop.run_until_complete(wait_task)


@pytest.mark.skipif(
    sys.platform != "linux", reason="Alsa is only available on Linux"
)
@pytest.mark.django_db
class TestWaitUntilComplete(asynctest.TestCase):
    def setUp(self):
        from nabd.sound_alsa import SoundAlsa
        from nabd.nabio import NabIO

        # Workaround for asynctest bug?
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "yes"

        try:
            if SoundAlsa.sound_configuration()[1] == "sndrpihifiberry":
                model = NabIO.MODEL_2018
            else:
                if SoundAlsa.sound_configuration()[1] == "tagtagtagsound":
                    model = NabIO.MODEL_2019_TAGTAG
                else:
                    raise unittest.SkipTest("No compatible sound card found")
        except RuntimeError as error:
            raise unittest.SkipTest(
                "Runtime error getting sound card %s" % str(error)
            )
        self.sound = SoundAlsa(model)

    async def test_wait_until_done(self):
        before = time.time()
        await self.sound.start_playing("fr_FR/asr/failed/5.mp3")
        await self.sound.wait_until_done()
        after = time.time()
        self.assertGreater(after - before, 3.0)

    async def test_wait_until_done_with_event_not_set(self):
        before = time.time()
        await self.sound.start_playing("fr_FR/asr/failed/5.mp3")
        event = asyncio.Event()
        await self.sound.wait_until_done(event)
        after = time.time()
        self.assertGreater(after - before, 3.0)

    async def test_wait_until_done_with_event_set(self):
        before = time.time()
        await self.sound.start_playing("fr_FR/asr/failed/5.mp3")
        event = asyncio.Event()
        self.loop.call_later(1.5, lambda: event.set())
        await self.sound.wait_until_done(event)
        after = time.time()
        self.assertLess(after - before, 3.0)


@pytest.mark.skipif(
    sys.platform != "linux", reason="Alsa is only available on Linux"
)
@pytest.mark.django_db
class TestRecord(unittest.TestCase):
    def setUp(self):
        from nabd.sound_alsa import SoundAlsa
        from nabd.nabio import NabIO

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            if SoundAlsa.sound_configuration()[1] != "tagtagtagsound":
                raise unittest.SkipTest(
                    "Test should be run on a 2019 card only"
                )
        except RuntimeError as error:
            raise unittest.SkipTest(
                "Runtime error getting sound card %s" % str(error)
            )
        self.sound = SoundAlsa(NabIO.MODEL_2019_TAGTAG)
        self.recorded_raw = open("test_recording.raw", "wb")

    def tearDown(self):
        self.recorded_raw.close()
        close_old_async_connections()

    def test_recording_playback(self):
        import alsaaudio

        start_task = self.loop.create_task(
            self.sound.start_playing("asr/listen.mp3")
        )
        self.loop.run_until_complete(start_task)
        wait_task = self.loop.create_task(self.sound.wait_until_done())
        self.loop.run_until_complete(wait_task)
        start_task = self.loop.create_task(
            self.sound.start_recording(self.record_cb)
        )
        self.loop.run_until_complete(start_task)
        time.sleep(5)
        stop_task = self.loop.create_task(self.sound.stop_recording())
        self.loop.run_until_complete(stop_task)
        start_task = self.loop.create_task(
            self.sound.start_playing("asr/acquired.mp3")
        )
        self.loop.run_until_complete(start_task)
        wait_task = self.loop.create_task(self.sound.wait_until_done())
        self.loop.run_until_complete(wait_task)

    def record_cb(self, data, finalize):
        self.recorded_raw.write(data)
