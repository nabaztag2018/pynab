import unittest, time, pytest, sys, platform
from nabd.leds import Leds

@pytest.mark.skipif(sys.platform != 'linux' or not 'arm' in platform.machine(), reason="Neopixel test only makes sens on a physical Nabaztag")
class TestLedsNeopixel(unittest.TestCase):
    def test_set_one(self):
        from nabd.leds_neopixel import LedsNeoPixel
        leds = LedsNeoPixel()
        for (r, g, b) in ((255,255,255), (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255), (0, 0, 0)):
            for i in range(0, 5):
                leds.do_set(i, r, g, b)
                leds.do_show()
                time.sleep(1)

    def test_set_all(self):
        from nabd.leds_neopixel import LedsNeoPixel
        leds = LedsNeoPixel()
        for (r, g, b) in ((255,255,255), (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255), (0, 0, 0)):
            for i in range(0, 5):
                leds.do_set(i, r, g, b)
            leds.do_show()
            time.sleep(1)
