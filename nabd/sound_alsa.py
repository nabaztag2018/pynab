import asyncio
import functools
import io
import logging
import traceback
import wave
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen

import alsaaudio  # type: ignore
from mpg123 import Mpg123  # type: ignore

from .cancel import wait_with_cancel_event
from .sound import Sound


class SoundAlsa(Sound):  # pragma: no cover
    MODEL_2018_CARD_NAME = "sndrpihifiberry"
    MODEL_2019_CARD_NAME = "tagtagtagsound"

    SOUND_CARDS_SUPPORTED = frozenset(
        (MODEL_2018_CARD_NAME, MODEL_2019_CARD_NAME)
    )

    def __init__(self, hw_model):
        self.sound_card = ""
        self.playback_device = "null"
        self.playback_mixer = None
        self.record_device = "null"
        self.record_mixer = None
        self._recorded_raw = None

        try:
            (
                card_index,
                self.sound_card,
                playback_device,
            ) = SoundAlsa.sound_configuration()
            self.playback_device = playback_device

            if self.sound_card == SoundAlsa.MODEL_2019_CARD_NAME:
                self.playback_mixer = alsaaudio.Mixer(
                    control="Playback", cardindex=card_index
                )
                self.record_device = self.playback_device
                self.record_mixer = alsaaudio.Mixer(
                    control="Capture", cardindex=card_index
                )

                if not SoundAlsa.__test_device(self.record_device, True):
                    raise RuntimeError(
                        "Unable to configure sound card for recording"
                    )
            else:
                # do we have anyone else? either way it is not supported
                assert self.sound_card == SoundAlsa.MODEL_2018_CARD_NAME

        except Exception as e:
            logging.error(e)
            if self.sound_card == "":
                logging.warning("no sound card?")

        self.executor = ThreadPoolExecutor(max_workers=1)

        self.future = None
        self.currently_playing = False
        self.currently_recording = False

    @staticmethod
    @functools.lru_cache()
    def sound_configuration():
        """
        Returns the (as a triplet) the card's index (zero based), raw card
        name and the device (playback or recording)
        supported by the hardware as a unicode string.

        @rtype: tuple

        @postcondition: len(return) == 3
        @postcondition: isinstnace(return[0], six.integer_types)
        @postcondition: return[0] >= 0
        @postcondition: return[1] in SoundAlsa.SOUND_CARDS_SUPPORTED
        @postcondition: len(return[1]) > 0
        @postcondition: isinstance(return[2], six.text_type)
        @postcondition: len(return[2]) > 0

        @raise RuntimeError: if no ALSO device could be found or if the
        device found cannot be configured.
        """
        for idx, sound_card in enumerate(alsaaudio.cards()):
            if sound_card in SoundAlsa.SOUND_CARDS_SUPPORTED:
                device = f"plughw:CARD={sound_card}"

                if not SoundAlsa.__test_device(device, False):
                    raise RuntimeError(
                        "Unable to configure sound card for playback"
                    )

                return idx, sound_card, device

        raise RuntimeError(
            "Sound card not found by ALSA (are drivers missing?)"
        )

    def get_sound_card(self):
        """
        Get the sound card for gestalt reporting.
        """
        return self.sound_card

    def _play(self, filename):
        try:
            device = alsaaudio.PCM(device=self.playback_device)
            if (
                filename.startswith("http://")
                or filename.startswith("https://")
            ) and filename.endswith(".mp3"):
                self._stream_mp3(device, filename)
            elif filename.endswith(".wav"):
                self._play_wav_file(device, filename)
            elif filename.endswith(".mp3"):
                self._play_mp3_file(device, filename)
        except Exception as err:
            logging.error(f"{filename}: {err}")
        finally:
            self.currently_playing = False
            device.close()

    def _play_wav_file(self, device, filename):
        with wave.open(filename, "rb") as f:
            channels = f.getnchannels()
            width = f.getsampwidth()
            rate = f.getframerate()
            self._setup_device(device, channels, rate, width)
            periodsize = rate // 10  # 1/10th of second
            device.setperiodsize(periodsize)
            target_chunk_size = periodsize * channels * width

            chunk = io.BytesIO()
            # tracking chunk length is technically useless here but we
            # do it for consistency
            chunk_length = 0
            data = f.readframes(periodsize)
            while data and self.currently_playing:
                chunk_length += chunk.write(data)

                if chunk_length < target_chunk_size:
                    # This (probably) is last iteration.
                    # ALSA device expects chunks of fixed period size
                    # Pad the sound with silence to complete chunk
                    chunk_length += chunk.write(
                        bytearray(target_chunk_size - chunk_length)
                    )

                device.write(chunk.getvalue())
                chunk.seek(0)
                chunk_length = 0
                data = f.readframes(periodsize)

    def _play_mp3_file(self, device, filename):
        mp3 = Mpg123(filename)
        rate, channels, encoding = mp3.get_format()
        width = mp3.get_width_by_encoding(encoding)
        self._setup_device(device, channels, rate, width)
        periodsize = rate // 10  # 1/10th of second
        device.setperiodsize(periodsize)
        target_chunk_size = periodsize * width * channels
        chunk = io.BytesIO()
        chunk_length = 0
        for frames in mp3.iter_frames():
            if (chunk_length + len(frames)) <= target_chunk_size:
                # Chunk is still smaller than what ALSA device expects
                # (0.1 sec)
                chunk_length += chunk.write(frames)
            else:
                frames_view = memoryview(frames)
                remaining = target_chunk_size - chunk_length
                chunk_length += chunk.write(frames_view[:remaining])
                device.write(chunk.getvalue())
                chunk.seek(0)
                chunk_length = 0
                chunk_length += chunk.write(frames_view[remaining:])

            if not self.currently_playing:
                break

        # ALSA device expects chunks of fixed period size
        # Pad the sound with silence to complete last chunk
        if chunk_length > 0:
            remaining = target_chunk_size - chunk_length
            chunk.write(bytearray(remaining))
            device.write(chunk.getvalue())

    def _stream_mp3(self, device, url):
        mp3 = Mpg123()
        # url begins with http:// or https:// (see above)
        response = urlopen(url)  # nosec B310

        mp3chunk = response.read(4096)
        if not mp3chunk:
            return
        mp3.feed(mp3chunk)
        rate, channels, encoding = mp3.get_format()
        width = mp3.get_width_by_encoding(encoding)
        self._setup_device(device, channels, rate, width)
        periodsize = rate // 10  # 1/10th of second
        device.setperiodsize(periodsize)
        target_chunk_size = periodsize * width * channels
        alsachunk = io.BytesIO()
        chunk_length = 0
        while self.currently_playing:
            for frames in mp3.iter_frames():
                if (chunk_length + len(frames)) <= target_chunk_size:
                    # Chunk is still smaller than what ALSA device expects
                    # (0.1 sec)
                    chunk_length += alsachunk.write(frames)
                else:
                    frames_view = memoryview(frames)
                    remaining = target_chunk_size - chunk_length
                    chunk_length += alsachunk.write(frames_view[:remaining])
                    device.write(alsachunk.getvalue())
                    alsachunk.seek(0)
                    chunk_length = 0
                    chunk_length += alsachunk.write(frames_view[remaining:])

                if not self.currently_playing:
                    break
            mp3chunk = response.read(4096)
            if not mp3chunk:
                break
            mp3.feed(mp3chunk)

        # ALSA device expects chunks of fixed period size
        # Pad the sound with silence to complete last chunk
        if chunk_length > 0:
            remaining = target_chunk_size - chunk_length
            alsachunk.write(bytearray(remaining))
            device.write(alsachunk.getvalue())

    def _setup_device(self, device, channels, rate, width):
        # Set attributes
        device.setchannels(channels)
        device.setrate(rate)

        device.setformat(SoundAlsa.__PCM_FORMAT_BY_WIDTH[width])

    async def stop_playing(self):
        if self.currently_playing:
            self.currently_playing = False
        await self.wait_until_done()

    async def wait_until_done(self, event=None):
        await wait_with_cancel_event(self.future, event, self.stop_playing)
        self.future = None

    async def start_recording(self, stream_cb):
        logging.debug("SoundAlsa: start recording")
        await self.stop_playing()
        self.currently_recording = True
        if logging.getLogger(__name__).isEnabledFor(logging.DEBUG):
            logging.debug(
                "SoundAlsa: creating sound_alsa_recording.raw to "
                "save recorded frames"
            )
            self._recorded_raw = open("sound_alsa_recording.raw", "wb")
        self.future = asyncio.get_event_loop().run_in_executor(
            self.executor, lambda cb=stream_cb: self._record(cb)
        )

    def _record(self, cb):
        inp = None
        try:
            inp = alsaaudio.PCM(
                alsaaudio.PCM_CAPTURE,
                alsaaudio.PCM_NORMAL,
                device=self.record_device,
            )
            inp.setchannels(1)
            inp.setrate(16000)
            inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
            inp.setperiodsize(1600)  # 100ms
            finalize = False
            count = 0
            while not finalize:
                l, data = inp.read()
                if not self.currently_recording:
                    finalize = True
                if l or finalize:
                    count += 1
                    if self._recorded_raw is not None:
                        self._recorded_raw.write(data)
                    cb(data, finalize)
            logging.debug(f"SoundAlsa: Recorded {count} frames")
        except Exception:
            print(traceback.format_exc())
        finally:
            self.currently_recording = False
            if inp:
                inp.close()

    async def stop_recording(self):
        logging.debug("SoundAlsa: stop recording")
        if self.currently_recording:
            self.currently_recording = False
        await self.wait_until_done()
        if self._recorded_raw is not None:
            self._recorded_raw.close()
            self._recorded_raw = None

    @staticmethod
    def __test_device(device, record):
        """
        Test selected ALSA device, making sure it handles both stereo and
        mono and both 44.1KHz and 22.05KHz on output, mono and 16 kHz on
        input.

        On a typical RPI configuration, default with hifiberry card is not
        configured to do software-mono, so we'll use
        plughw:CARD=sndrpihifiberry instead.
        Likewise, on 2019 cards, hw:CARD=seeed2micvoicec is not able to run
        mono sound.

        @param device: name of the sound device
        @type device: six.text_type
        @param record: C{True} if this method is looking for recording
        device. C{False} if the device should only playback.
        @type record: bool
        """
        try:
            dev = None

            if record:
                dev = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, device=device)
            else:
                dev = alsaaudio.PCM(device=device)

            if (
                dev.setformat(alsaaudio.PCM_FORMAT_S16_LE)
                != alsaaudio.PCM_FORMAT_S16_LE
            ):
                return False
            if record:
                if dev.setchannels(1) != 1:
                    return False
                if dev.setrate(16000) != 16000:
                    return False
            else:
                if dev.setchannels(2) != 2:
                    return False
                if dev.setchannels(1) != 1:
                    return False
                if dev.setrate(44100) != 44100:
                    return False
                if dev.setrate(22050) != 22050:
                    return False
        except alsaaudio.ALSAAudioError:
            return False
        finally:
            if dev:
                dev.close()
        return True

    async def start_playing_preloaded(self, filename):
        await self.stop_playing()
        self.currently_playing = True
        self.future = asyncio.get_event_loop().run_in_executor(
            self.executor, lambda f=filename: self._play(f)
        )

    __PCM_FORMAT_BY_WIDTH = {
        1: alsaaudio.PCM_FORMAT_U8,  # 8bit is unsigned in wav files
        # Otherwise we assume signed data, little endian
        2: alsaaudio.PCM_FORMAT_S16_LE,
        4: alsaaudio.PCM_FORMAT_S32_LE,
    }
    """ Mapping between the PCM format and the width of a sound """
