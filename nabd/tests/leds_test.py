import time
import unittest

from nabd.leds import Led, LedsSoft


class LedsInterface(LedsSoft):
    def __init__(self):
        super().__init__()
        self.calls = []

    def do_set(self, led, red, green, blue):
        self.calls.append(("do_set", led, red, green, blue))

    def do_show(self):
        self.calls.append("do_show")


class TestLeds(unittest.TestCase):
    def setUp(self):
        self.leds = LedsInterface()

    def tearDown(self):
        self.leds.stop()

    def test_set1(self):
        self.leds.set1(0, 10, 20, 30)
        time.sleep(0.1)
        self.assertEqual(
            self.leds.calls, [("do_set", 0, 10, 20, 30), "do_show"]
        )

    def test_setall(self):
        self.leds.setall(10, 20, 30)
        time.sleep(0.1)
        self.assertEqual(
            self.leds.calls,
            [
                ("do_set", Led.BOTTOM, 10, 20, 30),
                ("do_set", Led.RIGHT, 10, 20, 30),
                ("do_set", Led.CENTER, 10, 20, 30),
                ("do_set", Led.LEFT, 10, 20, 30),
                ("do_set", Led.NOSE, 10, 20, 30),
                "do_show",
            ],
        )

    def test_pulse(self):
        self.leds.pulse(Led.BOTTOM, 10, 20, 30)
        time.sleep(8)
        self.assertEqual(
            self.leds.calls[:44],
            [
                ("do_set", Led.BOTTOM, 0, 0, 0),
                "do_show",
                ("do_set", Led.BOTTOM, 0, 0, 1),
                "do_show",
                ("do_set", Led.BOTTOM, 0, 1, 2),
                "do_show",
                ("do_set", Led.BOTTOM, 1, 2, 3),
                "do_show",
                ("do_set", Led.BOTTOM, 1, 2, 4),
                "do_show",
                ("do_set", Led.BOTTOM, 1, 3, 5),
                "do_show",
                ("do_set", Led.BOTTOM, 1, 3, 6),
                "do_show",
                ("do_set", Led.BOTTOM, 2, 4, 7),
                "do_show",
                ("do_set", Led.BOTTOM, 2, 5, 8),
                "do_show",
                ("do_set", Led.BOTTOM, 3, 6, 9),
                "do_show",
                ("do_set", Led.BOTTOM, 3, 6, 10),
                "do_show",
                ("do_set", Led.BOTTOM, 3, 7, 11),
                "do_show",
                ("do_set", Led.BOTTOM, 4, 8, 12),
                "do_show",
                ("do_set", Led.BOTTOM, 4, 8, 13),
                "do_show",
                ("do_set", Led.BOTTOM, 4, 9, 14),
                "do_show",
                ("do_set", Led.BOTTOM, 4, 9, 15),
                "do_show",
                ("do_set", Led.BOTTOM, 5, 10, 16),
                "do_show",
                ("do_set", Led.BOTTOM, 5, 11, 17),
                "do_show",
                ("do_set", Led.BOTTOM, 5, 11, 18),
                "do_show",
                ("do_set", Led.BOTTOM, 6, 12, 19),
                "do_show",
                ("do_set", Led.BOTTOM, 6, 13, 20),
                "do_show",
                ("do_set", Led.BOTTOM, 6, 13, 21),
                "do_show",
            ],
        )
