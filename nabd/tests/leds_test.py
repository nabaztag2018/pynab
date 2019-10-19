import unittest, time
from nabd.leds import Leds, LedsSoft

class LedsInterface(LedsSoft):
    def __init__(self):
        super().__init__()
        self.calls = []

    def do_set(self, led, red, green, blue):
        self.calls.append(('do_set', led, red, green, blue))

    def do_show(self):
        self.calls.append('do_show')

class TestLeds(unittest.TestCase):
    def setUp(self):
        self.leds = LedsInterface()

    def tearDown(self):
        self.leds.stop()

    def test_set1(self):
        self.leds.set1(0, 10, 20, 30)
        time.sleep(0.1)
        self.assertEqual(self.leds.calls, [('do_set', 0, 10, 20, 30), 'do_show'])

    def test_setall(self):
        self.leds.setall(10, 20, 30)
        time.sleep(0.1)
        self.assertEqual(self.leds.calls, [('do_set', 0, 10, 20, 30), ('do_set', 1, 10, 20, 30), ('do_set', 2, 10, 20, 30), ('do_set', 3, 10, 20, 30), ('do_set', 4, 10, 20, 30), 'do_show'])

    def test_pulse(self):
        self.leds.pulse(0, 10, 20, 30)
        time.sleep(8)
        self.assertEqual(self.leds.calls[:44], [
                ('do_set', 0, 0, 0, 0), 'do_show',
                ('do_set', 0, 1, 2, 3), 'do_show',
                ('do_set', 0, 2, 4, 6), 'do_show',
                ('do_set', 0, 3, 6, 9), 'do_show',
                ('do_set', 0, 4, 8, 12), 'do_show',
                ('do_set', 0, 5, 10, 15), 'do_show',
                ('do_set', 0, 6, 12, 18), 'do_show',
                ('do_set', 0, 7, 14, 21), 'do_show',
                ('do_set', 0, 8, 16, 24), 'do_show',
                ('do_set', 0, 9, 18, 27), 'do_show',
                ('do_set', 0, 10, 20, 30), 'do_show',
                ('do_set', 0, 9, 18, 27), 'do_show',
                ('do_set', 0, 8, 16, 24), 'do_show',
                ('do_set', 0, 7, 14, 21), 'do_show',
                ('do_set', 0, 6, 12, 18), 'do_show',
                ('do_set', 0, 5, 10, 15), 'do_show',
                ('do_set', 0, 4, 8, 12), 'do_show',
                ('do_set', 0, 3, 6, 9), 'do_show',
                ('do_set', 0, 2, 4, 6), 'do_show',
                ('do_set', 0, 1, 2, 3), 'do_show',
                ('do_set', 0, 0, 0, 0), 'do_show',
                ('do_set', 0, 1, 2, 3), 'do_show',
                ])
