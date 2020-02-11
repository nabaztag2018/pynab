import abc
from .choreography import ChoreographyInterpreter


class NabIO(object, metaclass=abc.ABCMeta):
    """ Interface for I/O interactions with a nabaztag """

    # https://github.com/nabaztag2018/hardware/blob/master/RPI_Nabaztag.PDF
    MODEL_2018 = 1
    # https://github.com/nabaztag2018/hardware/blob/master/
    # pyNab_V4.1_voice_reco.PDF
    MODEL_2019_TAG = 2
    # with RFID
    MODEL_2019_TAGTAG = 3

    # Each info loop lasts 15 seconds
    INFO_LOOP_LENGTH = 15.0

    @abc.abstractmethod
    async def setup_ears(self, left_ear, right_ear):
        """
        Init ears and move them to the initial position.
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    async def move_ears(self, left_ear, right_ear):
        """
        Move ears to a given position and return only when they reached this
        position.
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    async def detect_ears_positions(self):
        """
        Detect ears positions and return the position before the detection.
        A second call will return the current position.
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    def set_leds(self, nose, left, center, right, bottom):
        """ Set the leds. None means to turn them off. """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    def pulse(self, led, color):
        """ Set a led to pulse. """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    def bind_button_event(self, loop, callback):
        """
        Define the callback for button events.
        callback is cb(event_type, time) with event_type being:
        - 'down'
        - 'up'
        - 'long_down'
        - 'double_click'
        - 'click_and_hold'

        Make sure the callback is called on the provided event loop, with
        loop.call_soon_threadsafe
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    def bind_ears_event(self, loop, callback):
        """
        Define the callback for ears events.
        callback is cb(ear) ear being the ear moved.

        Make sure the callback is called on the provided event loop, with
        loop.call_soon_threadsafe
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    async def play_info(self, condvar, tempo, colors):
        """
        Play an info animation.
        tempo & colors are as described in the nabd protocol.
        Run the animation in loop for the complete info duration (15 seconds)
        or until condvar is notified

        If 'left'/'center'/'right' slots are absent, the light is off.
        Return true if condvar was notified
        """
        raise NotImplementedError("Should have implemented")

    async def start_acquisition(self, acquisition_cb):
        """
        Play listen sound and start acquisition, calling callback with sound
        samples.
        """
        self.set_leds(
            (255, 0, 255), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)
        )
        await self.sound.play_list(["asr/listen.mp3"], False)
        await self.sound.start_recording(acquisition_cb)

    async def end_acquisition(self):
        """
        Play acquired sound and call callback with finalize.
        """
        await self.sound.stop_recording()
        await self.sound.play_list(["asr/acquired.mp3"], False)

    async def asr_failed(self):
        """
        Feedback when ASR or NLU failed.
        """
        await self.sound.play_list(["asr/failed/*.mp3"], False)

    async def play_message(self, signature, body):
        """
        Play a message, i.e. a signature, a body and a signature.
        """
        preloaded_sig = await self._preload([signature])
        preloaded_body = await self._preload(body)
        ci = ChoreographyInterpreter(self.leds, self.ears, self.sound)
        await self._play_preloaded(
            ci, preloaded_sig, ChoreographyInterpreter.STREAMING_URN
        )
        await self._play_preloaded(
            ci, preloaded_body, ChoreographyInterpreter.STREAMING_URN
        )
        await self._play_preloaded(
            ci, preloaded_sig, ChoreographyInterpreter.STREAMING_URN
        )
        await ci.stop()

    async def play_sequence(self, sequence):
        """
        Play a simple sequence
        """
        preloaded = await self._preload(sequence)
        ci = ChoreographyInterpreter(self.leds, self.ears, self.sound)
        played_audio = await self._play_preloaded(ci, preloaded, None)
        if played_audio:
            await ci.stop()
        else:
            await ci.wait_until_complete()

    async def _play_preloaded(self, ci, preloaded, default_chor):
        for seq_item in preloaded:
            if "choreography" in seq_item:
                chor = seq_item["choreography"]
            else:
                chor = default_chor
            if chor is not None:
                await ci.start(chor)
            else:
                await ci.stop()
            if "audio" in seq_item:
                await self.sound.play_list(seq_item["audio"], True)
                return True
            else:
                return False

    async def _preload(self, sequence):
        preloaded_sequence = []
        for seq_item in sequence:
            if "audio" in seq_item:
                preloaded_audio_list = []
                if isinstance(seq_item["audio"], str):
                    print(
                        f"Warning: audio should be a list of resources "
                        f"(sequence item: {seq_item})"
                    )
                    audio_list = [seq_item["audio"]]
                else:
                    audio_list = seq_item["audio"]
                for res in audio_list:
                    f = await self.sound.preload(res)
                    if f is not None:
                        preloaded_audio_list.append(f)
                seq_item["audio"] = preloaded_audio_list
            preloaded_sequence.append(seq_item)
        return preloaded_sequence

    @abc.abstractmethod
    def cancel(self):
        """
        Cancel currently running sequence or info animation.
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    def gestalt(self):
        """ Return a structure representing hardware info. """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    def has_sound_input(self):
        """ Determine if we have sound input """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    async def test(self, test):
        """ Run a given hardware test, returning True if everything is ok """
        raise NotImplementedError("Should have implemented")
