import abc
import asyncio
import time
from asyncio import Event

from .choreography import ChoreographyInterpreter
from .ears import Ears
from .leds import Led


class NabIO(object, metaclass=abc.ABCMeta):
    """Interface for I/O interactions with a nabaztag"""

    # https://github.com/nabaztag2018/hardware/blob/master/RPI_Nabaztag.PDF
    MODEL_2018 = 1
    # https://github.com/nabaztag2018/hardware/blob/master/
    # pyNab_V4.1_voice_reco.PDF
    MODEL_2019_TAG = 2
    # with RFID
    MODEL_2019_TAGTAG = 3

    # Each info loop lasts 15 seconds
    INFO_LOOP_LENGTH = 15.0

    def __init__(self):
        super().__init__()
        self.cancel_event = Event()

    async def setup_ears(self, left_ear, right_ear):
        """
        Init ears and move them to the initial position.
        """
        await self.ears.reset_ears(left_ear, right_ear)

    async def move_ears(self, left_ear, right_ear):
        """
        Move ears to a given position and return only when they reached this
        position.
        """
        await self.ears.go(Ears.LEFT_EAR, left_ear, Ears.FORWARD_DIRECTION)
        await self.ears.go(Ears.RIGHT_EAR, right_ear, Ears.FORWARD_DIRECTION)
        await self.ears.wait_while_running()

    async def move_ears_with_leds(self, color, new_left, new_right):
        """
        If ears are not in given position, set LEDs to given color, move ears,
        turn LEDs off and return.
        """
        do_move = False
        current_left, current_right = await self.ears.get_positions()
        if current_left != new_left:
            if not self.ears.is_broken(Ears.LEFT_EAR):
                do_move = True
        if current_right != new_right:
            if not self.ears.is_broken(Ears.RIGHT_EAR):
                do_move = True
        if do_move:
            self.set_leds(color, color, color, color, color)
            await self.move_ears(new_left, new_right)
        self.set_leds(None, None, None, None, None)

    async def detect_ears_positions(self):
        """
        Detect ears positions and return the position before the detection.
        A second call will return the current position.
        """
        return await self.ears.detect_positions()

    def set_leds(self, nose, left, center, right, bottom):
        """
        Set the leds. None means to turn them off.
        """
        for (led_ix, led) in [
            (Led.NOSE, nose),
            (Led.LEFT, left),
            (Led.CENTER, center),
            (Led.RIGHT, right),
            (Led.BOTTOM, bottom),
        ]:
            if led is None:
                (r, g, b) = (0, 0, 0)
            else:
                (r, g, b) = led
            self.leds.set1(led_ix, r, g, b)

    def pulse(self, led, color):
        """
        Set a led to pulse.
        """
        (r, g, b) = color
        self.leds.pulse(led, r, g, b)

    async def rfid_detected_feedback(self):
        ci = ChoreographyInterpreter(self.leds, self.ears, self.sound)
        await ci.start("nabd/rfid.chor")
        await self.sound.play_list(["rfid/rfid.wav"], False)
        await ci.stop()
        self.set_leds(None, None, None, None, None)

    def rfid_awaiting_feedback(self):
        """
        Turn nose red.
        """
        self.leds.set1(Led.NOSE, 255, 0, 0)

    def rfid_done_feedback(self):
        """
        Turn everything off.
        """
        self.set_leds((0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0))

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
        self.button.on_event(loop, callback)

    def bind_ears_event(self, loop, callback):
        """
        Define the callback for ears events.
        callback is cb(ear) ear being the ear moved.

        Make sure the callback is called on the provided event loop, with
        loop.call_soon_threadsafe
        """
        self.ears.on_move(loop, callback)

    def bind_rfid_event(self, loop, callback):
        """
        Define the callback for rfid events.
        callback is cb(uid, picture, app, data, flags)

        Make sure the callback is called on the provided event loop, with
        loop.call_soon_threadsafe
        """
        self.rfid.on_detect(loop, callback)

    async def play_info(self, condvar, tempo, colors):
        """
        Play an info animation.
        tempo & colors are as described in the nabd protocol.
        Run the animation in loop for the complete info duration (15 seconds)
        or until condvar is notified

        If 'left'/'center'/'right' slots are absent, the light is off.
        Return true if condvar was notified
        """
        animation = [NabIO._convert_info_color(color) for color in colors]
        step_ms = tempo * 10
        start = time.time()
        index = 0
        notified = False
        while time.time() - start < NabIO.INFO_LOOP_LENGTH:
            step = animation[index]
            for led_ix, rgb in step:
                r, g, b = rgb
                self.leds.set1(led_ix, r, g, b)
            if await NabIO._wait_on_condvar(condvar, step_ms):
                index = (index + 1) % len(animation)
            else:
                notified = True
                break
        self.clear_info()
        return notified

    def clear_info(self):
        for led in (Led.LEFT, Led.CENTER, Led.RIGHT):
            self.leds.set1(led, 0, 0, 0)

    @staticmethod
    async def _wait_on_condvar(condvar, ms):
        timeout = False
        try:
            await asyncio.wait_for(condvar.wait(), ms / 1000)
        except asyncio.TimeoutError:
            timeout = True
        return timeout

    @staticmethod
    def _convert_info_color(color):
        animation = []
        for led_ix, led in [
            (Led.LEFT, "left"),
            (Led.CENTER, "center"),
            (Led.RIGHT, "right"),
        ]:
            values = []
            if color[led]:
                int_value = int(color[led], 16)
                values.append((int_value >> 16) & 0xFF)  # r
                values.append((int_value >> 8) & 0xFF)  # g
                values.append(int_value & 0xFF)  # b
            else:
                values.append(0)
                values.append(0)
                values.append(0)
            animation.append((led_ix, values))
        return animation

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
        self.cancel_event.clear()
        # Turn leds red while ears go to 0, 0
        await self.move_ears_with_leds((255, 0, 0), 0, 0)
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
        self.set_leds(None, None, None, None, None)

    async def play_sequence(self, sequence):
        """
        Play a simple sequence
        """
        self.cancel_event.clear()
        preloaded = await self._preload(sequence)
        ci = ChoreographyInterpreter(self.leds, self.ears, self.sound)
        await self._play_preloaded(ci, preloaded, None)

    async def _play_preloaded(self, ci, preloaded, default_chor):
        for seq_item in preloaded:
            if self.cancel_event.is_set():
                break
            if "choreography" in seq_item:
                chor = seq_item["choreography"]
            else:
                chor = default_chor
            if chor is not None:
                await ci.start(chor)
            else:
                await ci.stop()
            if "audio" in seq_item:
                await self.sound.play_list(
                    seq_item["audio"], True, self.cancel_event
                )
                if chor is not None:
                    await ci.stop()
            elif "choreography" in seq_item:
                await ci.wait_until_complete(self.cancel_event)

    async def _preload(self, sequence):
        preloaded_sequence = []
        for seq_item in sequence:
            if self.cancel_event.is_set():
                break
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

    async def cancel(self, feedback=False):
        """
        Cancel currently running sequence or info animation.
        """
        self.cancel_event.set()
        if feedback:
            await self.sound.play_list(["nabd/abort.wav"], False)

    @abc.abstractmethod
    async def gestalt(self):
        """Return a structure representing hardware info."""
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    def has_sound_input(self):
        """Determine if we have sound input"""
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    def has_rfid(self):
        """Determine if we have an rfid reader"""
        raise NotImplementedError("Should have implemented")

    async def test(self, test):
        if test == "ears":
            (
                left_ear_position,
                right_ear_position,
            ) = await self.ears.get_positions()
            await self.ears.go(Ears.LEFT_EAR, 8, Ears.BACKWARD_DIRECTION)
            await self.ears.go(Ears.RIGHT_EAR, 8, Ears.BACKWARD_DIRECTION)
            await self.ears.wait_while_running()
            for x in range(0, 17):
                await self.ears.move(Ears.LEFT_EAR, 1, Ears.FORWARD_DIRECTION)
                await self.ears.move(
                    Ears.RIGHT_EAR, 1, Ears.BACKWARD_DIRECTION
                )
                await self.ears.wait_while_running()
                await asyncio.sleep(0.2)
            for x in range(0, 17):
                await self.ears.move(Ears.LEFT_EAR, 1, Ears.BACKWARD_DIRECTION)
                await self.ears.move(Ears.RIGHT_EAR, 1, Ears.FORWARD_DIRECTION)
                await self.ears.wait_while_running()
                await asyncio.sleep(0.2)
            await self.ears.go(Ears.LEFT_EAR, 0, Ears.FORWARD_DIRECTION)
            await self.ears.go(Ears.RIGHT_EAR, 0, Ears.FORWARD_DIRECTION)
            await self.ears.wait_while_running()
            if left_ear_position is not None:
                await self.ears.go(
                    Ears.LEFT_EAR, left_ear_position, Ears.FORWARD_DIRECTION
                )
            if right_ear_position is not None:
                await self.ears.go(
                    Ears.RIGHT_EAR, right_ear_position, Ears.FORWARD_DIRECTION
                )
            await self.ears.wait_while_running()
            if self.ears.is_broken(Ears.LEFT_EAR):
                return False
            if self.ears.is_broken(Ears.RIGHT_EAR):
                return False
            return True
        elif test == "leds":
            for color in [
                (0, 0, 0),
                (255, 0, 0),
                (0, 255, 0),
                (0, 0, 255),
                (255, 255, 255),
                (127, 127, 127),
                (0, 0, 0),
            ]:
                r, g, b = color
                for led_ix in [
                    Led.NOSE,
                    Led.LEFT,
                    Led.CENTER,
                    Led.RIGHT,
                    Led.BOTTOM,
                ]:
                    self.leds.set1(led_ix, r, g, b)
                    await asyncio.sleep(0.2)
                await asyncio.sleep(1.0)
            return True
        else:
            return False
