import RPi.GPIO as GPIO
from .button import Button
import sys
import atexit
import time
from threading import Timer, Lock

@atexit.register
def cleanup_gpio():
  GPIO.setwarnings(False)
  GPIO.cleanup()

class ButtonGPIO(Button):
  BUTTON_CHANNEL = 2
  DOWN_VALUE = 0
  UP_VALUE = 1

  LONG_DOWN_TIMEOUT = 3.0
  DOUBLE_CLICK_TIMEOUT = 0.1

  def __init__(self):
    self.callback = None
    self.button_sequence = 0
    self.button_timer = None
    self.button_sequence_lock = Lock()
    GPIO.setwarnings(True)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(ButtonGPIO.BUTTON_CHANNEL, GPIO.IN)
    try:
      GPIO.add_event_detect(ButtonGPIO.BUTTON_CHANNEL, GPIO.BOTH, callback=self._button_event)
    except RuntimeError:
      print('Could not set edge detection (please reboot ?)')
      sys.exit(1)

  def on_event(self, loop, callback):
    self.callback = (loop, callback)

  def _button_event(self, channel):
    now = time.time()
    if self.button_timer:
      self.button_timer.cancel()
      self.button_timer = None
    (loop, callback) = self.callback
    if GPIO.input(ButtonGPIO.BUTTON_CHANNEL) == ButtonGPIO.UP_VALUE:
      loop.call_soon_threadsafe(lambda now=now: callback('up', now))
      with self.button_sequence_lock:
        if self.button_sequence == 3:
          # double click
          loop.call_soon_threadsafe(lambda now=now: callback('double_click', now))
          self.button_sequence = 0
        elif self.button_sequence == 1:
          self.button_sequence = 2
          self.button_timer = Timer(ButtonGPIO.DOUBLE_CLICK_TIMEOUT, self._click_cb)
          self.button_timer.start()
    else:
      loop.call_soon_threadsafe(lambda now=now: callback('down', now))
      with self.button_sequence_lock:
        if self.button_sequence == 0:
          self.button_sequence = 1
          self.button_timer = Timer(ButtonGPIO.LONG_DOWN_TIMEOUT, self._long_down_cb)
          self.button_timer.start()
        elif self.button_sequence == 2:
          self.button_sequence = 3
          self.button_timer = Timer(ButtonGPIO.DOUBLE_CLICK_TIMEOUT, self._click_and_hold_cb)
          self.button_timer.start()

  def _long_down_cb(self):
    self._timer_event_cb('long_down')

  def _click_cb(self):
    self._timer_event_cb('click')

  def _click_and_hold_cb(self):
    self._timer_event_cb('click_and_hold')

  def _timer_event_cb(self, event):
    now = time.time()
    (loop, callback) = self.callback
    with self.button_sequence_lock:
      loop.call_soon_threadsafe(lambda now=now: callback(event, now))
      self.button_timer = None
      self.button_sequence = 0
