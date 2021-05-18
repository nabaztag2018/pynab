import asyncio
import time
import wave
from concurrent.futures import ThreadPoolExecutor

from mpg123 import Mpg123

from .cancel import wait_with_cancel_event
from .sound import Sound


class SoundVirtual(Sound):
    def __init__(self, nabio_virtual):
        super().__init__()
        self.nabio_virtual = nabio_virtual
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.future = None
        self.currently_playing = False

    def _play(self, filename):
        try:
            if filename.endswith(".wav"):
                with wave.open(filename, "rb") as f:
                    rate = f.getframerate()
                    frames = f.getnframes()
                    duration = frames / float(rate)
                    time.sleep(duration)
            elif filename.endswith(".mp3"):
                mp3 = Mpg123(filename)
                rate, channels, encoding = mp3.get_format()
                frames = mp3.length()
                duration = frames / float(rate)
                time.sleep(duration)
        finally:
            self.currently_playing = False
            self.nabio_virtual.update_rabbit()

    async def start_playing_preloaded(self, filename):
        await self.stop_playing()
        self.currently_playing = True
        self.sound_file = filename
        self.nabio_virtual.update_rabbit()
        self.future = asyncio.get_event_loop().run_in_executor(
            self.executor, lambda f=filename: self._play(f)
        )

    async def wait_until_done(self, event=None):
        await wait_with_cancel_event(self.future, event, self.stop_playing)
        self.future = None

    async def stop_playing(self):
        if self.currently_playing:
            self.currently_playing = False
        await self.wait_until_done()

    async def start_recording(self, stream_cb):
        raise NotImplementedError("Should have implemented")

    async def stop_recording(self):
        raise NotImplementedError("Should have implemented")
