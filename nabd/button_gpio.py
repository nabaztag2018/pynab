import RPi.GPIO as GPIO
from .button import Button
from .nabio import NabIO
import sys
import atexit
import time
from threading import Timer, Lock


@atexit.register
def cleanup_gpio():  # pragma: no cover
    GPIO.setwarnings(False)
    GPIO.cleanup()


class ButtonGPIO(Button):  # pragma: no cover
    BUTTON_CHANNEL_2018 = 2
    BUTTON_CHANNEL_2019 = 17
    DOWN_VALUE = 0
    UP_VALUE = 1

    HOLD_TIMEOUT = 2.0
    CLICK_AND_HOLD_TIMEOUT = 2.0
    DOUBLE_CLICK_TIMEOUT = 0.15
    TRIPLE_CLICK_TIMEOUT = 0.15

    def __init__(self, hw_model):
        self.callback = None
        self.button_sequence = 0
        self.button_timer = None
        self.button_sequence_lock = Lock()
        self.button_state = "up"
        GPIO.setwarnings(True)
        GPIO.setmode(GPIO.BCM)
        if hw_model == NabIO.MODEL_2018:
            self.button_channel = ButtonGPIO.BUTTON_CHANNEL_2018
        else:
            self.button_channel = ButtonGPIO.BUTTON_CHANNEL_2019
        GPIO.setup(self.button_channel, GPIO.IN)
        try:
            GPIO.add_event_detect(
                self.button_channel, GPIO.BOTH, callback=self._button_event
            )
        except RuntimeError:
            print("Could not set edge detection (please reboot ?)")
            sys.exit(1)

    def on_event(self, loop, callback):
        self.callback = (loop, callback)

    #
    # (0) -- down -> (1) -- timer -> hold
    #                 |
    #                 -- up -> (2) -- timer -> click + goto state 0
    #                           |
    #  _________________________|
    #  |
    #  -- down -> (3) -- timer -> click_and_hold
    #              |
    #              -- up -> (4) -- timer -> double click
    #                        |
    #                        -- down -> (5) -- timer -> click_and_hold
    #
    def _button_event(self, channel):
        now = time.time()
        if self.button_timer:
            self.button_timer.cancel()
            self.button_timer = None
        if self.callback is None:
            return
        (loop, callback) = self.callback
        if (
            GPIO.input(self.button_channel) == ButtonGPIO.UP_VALUE
            and self.button_state == "down"
        ):
            self.button_state = "up"
            loop.call_soon_threadsafe(lambda now=now: callback("up", now))
            with self.button_sequence_lock:
                if self.button_sequence == 5:
                    self.button_sequence = 0
                    # triple click
                    loop.call_soon_threadsafe(
                        lambda now=now: callback("triple_click", now)
                    )
                    self.button_sequence = 0
                elif self.button_sequence == 3:
                    self.button_sequence = 4
                    self.button_timer = Timer(
                        ButtonGPIO.TRIPLE_CLICK_TIMEOUT, self._double_click_cb
                    )
                    self.button_timer.start()
                elif self.button_sequence == 1:
                    self.button_sequence = 2
                    self.button_timer = Timer(
                        ButtonGPIO.DOUBLE_CLICK_TIMEOUT, self._click_cb
                    )
                    self.button_timer.start()
        elif (
            GPIO.input(self.button_channel) == ButtonGPIO.DOWN_VALUE
            and self.button_state == "up"
        ):
            self.button_state = "down"
            loop.call_soon_threadsafe(lambda now=now: callback("down", now))
            with self.button_sequence_lock:
                if self.button_sequence == 0:
                    self.button_sequence = 1
                    self.button_timer = Timer(
                        ButtonGPIO.HOLD_TIMEOUT, self._hold_cb
                    )
                    self.button_timer.start()
                elif self.button_sequence == 2:
                    self.button_sequence = 3
                    self.button_timer = Timer(
                        ButtonGPIO.CLICK_AND_HOLD_TIMEOUT,
                        self._click_and_hold_cb,
                    )
                    self.button_timer.start()
                elif self.button_sequence == 4:
                    self.button_sequence = 5
                    self.button_timer = Timer(
                        ButtonGPIO.TRIPLE_CLICK_TIMEOUT,
                        self._click_and_hold_cb,
                    )
                    self.button_timer.start()

    def _hold_cb(self):
        self._timer_event_cb("hold")

    def _click_and_hold_cb(self):
        self._timer_event_cb("click_and_hold")

    def _click_cb(self):
        self._timer_event_cb("click")

    def _double_click_cb(self):
        self._timer_event_cb("double_click")

    def _timer_event_cb(self, event):
        now = time.time()
        (loop, callback) = self.callback
        with self.button_sequence_lock:
            loop.call_soon_threadsafe(lambda now=now: callback(event, now))
            self.button_timer = None
            self.button_sequence = 0
