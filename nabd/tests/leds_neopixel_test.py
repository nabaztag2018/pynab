import unittest
import time
import pytest
import sys
import platform
import os
from nabd.leds import Led


@pytest.mark.skipif(
    sys.platform != "linux"
    or "arm" not in platform.machine()
    or "CI" in os.environ,
    reason="Neopixel test only makes sense on a physical Nabaztag",
)
class TestLedsNeopixel(unittest.TestCase):
    def test_set_one(self):
        from nabd.leds_neopixel import LedsNeoPixel

        leds = LedsNeoPixel()
        for (r, g, b) in (
            (255, 255, 255),
            (255, 0, 0),
            (0, 255, 0),
            (0, 0, 255),
            (255, 255, 0),
            (255, 0, 255),
            (0, 255, 255),
            (0, 0, 0),
        ):
            for led in [
                Led.NOSE,
                Led.LEFT,
                Led.CENTER,
                Led.RIGHT,
                Led.BOTTOM,
            ]:
                leds.do_set(led, r, g, b)
                leds.do_show()
                time.sleep(1)

    def test_set_all(self):
        from nabd.leds_neopixel import LedsNeoPixel

        leds = LedsNeoPixel()
        for (r, g, b) in (
            (255, 255, 255),
            (255, 0, 0),
            (0, 255, 0),
            (0, 0, 255),
            (255, 255, 0),
            (255, 0, 255),
            (0, 255, 255),
            (0, 0, 0),
        ):
            for led in [
                Led.NOSE,
                Led.LEFT,
                Led.CENTER,
                Led.RIGHT,
                Led.BOTTOM,
            ]:
                leds.do_set(led, r, g, b)
            leds.do_show()
            time.sleep(1)
