import asyncio
import asynctest
import base64
import pytest
import unittest
from nabd.choreography import ChoreographyInterpreter
from mock import EarsMock, LedsMock, SoundMock
from utils import close_old_async_connections


class TestChoreographyBase(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.loop.set_debug(True)
        asyncio.set_event_loop(self.loop)
        self.leds = LedsMock()
        self.ears = EarsMock()
        self.sound = SoundMock()
        self.ci = ChoreographyInterpreter(self.leds, self.ears, self.sound)


class TestChoreographyInterpreter(TestChoreographyBase):
    def test_set_led_color(self):
        chor = base64.b16decode("0007020304050607")
        task = self.loop.create_task(self.ci.play_binary(chor))
        self.loop.run_until_complete(task)
        self.assertEqual(self.leds.called_list, ["set1(Led.CENTER,3,4,5)"])
        self.assertEqual(self.ears.called_list, [])
        self.assertEqual(self.sound.called_list, [])

    def test_set_motor(self):
        chor = base64.b16decode("0008010300")
        task = self.loop.create_task(self.ci.play_binary(chor))
        self.loop.run_until_complete(task)
        self.assertEqual(self.leds.called_list, [])
        self.assertEqual(self.ears.called_list, ["go(1,3,0)"])
        self.assertEqual(self.sound.called_list, [])

    def test_set_leds_color(self):
        chor = base64.b16decode("0009020304")
        task = self.loop.create_task(self.ci.play_binary(chor))
        self.loop.run_until_complete(task)
        self.assertEqual(self.leds.called_list, ["setall(2,3,4)"])
        self.assertEqual(self.ears.called_list, [])
        self.assertEqual(self.sound.called_list, [])

    def test_set_led_off(self):
        chor = base64.b16decode("000A02")
        task = self.loop.create_task(self.ci.play_binary(chor))
        self.loop.run_until_complete(task)
        self.assertEqual(self.leds.called_list, ["set1(Led.CENTER,0,0,0)"])
        self.assertEqual(self.ears.called_list, [])
        self.assertEqual(self.sound.called_list, [])

    def test_set_led_palette(self):
        chor = base64.b16decode("000E0203")
        task = self.loop.create_task(self.ci.play_binary(chor))
        self.loop.run_until_complete(task)
        self.assertEqual(self.leds.called_list, ["set1(Led.CENTER,0,0,0)"])
        self.assertEqual(self.ears.called_list, [])
        self.assertEqual(self.sound.called_list, [])

    def test_avance(self):
        chor = base64.b16decode("00110102")
        task = self.loop.create_task(self.ci.play_binary(chor))
        self.loop.run_until_complete(task)
        self.assertEqual(self.leds.called_list, [])
        self.assertEqual(self.ears.called_list, ["move(1,2,0)"])
        self.assertEqual(self.sound.called_list, [])

    def test_setmotordir(self):
        chor = base64.b16decode("0014010100110102")
        task = self.loop.create_task(self.ci.play_binary(chor))
        self.loop.run_until_complete(task)
        self.assertEqual(self.leds.called_list, [])
        self.assertEqual(self.ears.called_list, ["move(1,2,1)"])
        self.assertEqual(self.sound.called_list, [])

    def test_ifne(self):
        chor = base64.b16decode("0012000000000A02")
        task = self.loop.create_task(self.ci.play_binary(chor))
        self.loop.run_until_complete(task)
        self.assertEqual(self.leds.called_list, ["set1(Led.CENTER,0,0,0)"])
        self.assertEqual(self.ears.called_list, [])
        self.assertEqual(self.sound.called_list, [])

    def test_rfidok(self):
        chor = base64.b16decode(
            "0101010100010E0007030000FF000000"
            + "07020000FF00000007010000FF000001"
            + "07030000000000000702000000000000"
            + "070100000000000107040000FF000002"
            + "070400000000000107040000FF000002"
            + "0A04"
        )
        task = self.loop.create_task(self.ci.play_binary(chor))
        self.loop.run_until_complete(task)
        self.assertEqual(
            self.leds.called_list,
            [
                "set1(Led.LEFT,0,0,255)",
                "set1(Led.CENTER,0,0,255)",
                "set1(Led.RIGHT,0,0,255)",
                "set1(Led.LEFT,0,0,0)",
                "set1(Led.CENTER,0,0,0)",
                "set1(Led.RIGHT,0,0,0)",
                "set1(Led.NOSE,0,0,255)",
                "set1(Led.NOSE,0,0,0)",
                "set1(Led.NOSE,0,0,255)",
                "set1(Led.NOSE,0,0,0)",
            ],
        )
        self.assertEqual(self.ears.called_list, [])
        self.assertEqual(self.sound.called_list, [])


class TestCancelEvent(asynctest.TestCase):
    def setUp(self):
        self.leds = LedsMock()
        self.ears = EarsMock()
        self.sound = SoundMock()
        self.ci = ChoreographyInterpreter(self.leds, self.ears, self.sound)

    async def test_wait_until_complete(self):
        chor_bin = base64.b16decode("0001050507020304050607")
        chor_b64 = base64.b64encode(chor_bin).decode()
        chor = (
            ChoreographyInterpreter.DATA_MTL_BINARY_SCHEME
            + ";base64,"
            + chor_b64
        )
        await self.ci.start(chor)
        await self.ci.wait_until_complete()
        self.assertEqual(self.leds.called_list, ["set1(Led.CENTER,3,4,5)"])
        self.assertEqual(self.ears.called_list, [])
        self.assertEqual(self.sound.called_list, [])

    async def test_wait_until_complete_with_no_event(self):
        chor_bin = base64.b16decode("0001050507020304050607")
        chor_b64 = base64.b64encode(chor_bin).decode()
        chor = (
            ChoreographyInterpreter.DATA_MTL_BINARY_SCHEME
            + ";base64,"
            + chor_b64
        )
        await self.ci.start(chor)
        event = asyncio.Event()
        await self.ci.wait_until_complete(event)
        self.assertEqual(self.leds.called_list, ["set1(Led.CENTER,3,4,5)"])
        self.assertEqual(self.ears.called_list, [])
        self.assertEqual(self.sound.called_list, [])

    async def test_wait_until_complete_with_event(self):
        chor_bin = base64.b16decode("0001050507020304050607")
        chor_b64 = base64.b64encode(chor_bin).decode()
        chor = (
            ChoreographyInterpreter.DATA_MTL_BINARY_SCHEME
            + ";base64,"
            + chor_b64
        )
        await self.ci.start(chor)
        event = asyncio.Event()
        self.loop.call_later(0.1, lambda: event.set())
        await self.ci.wait_until_complete(event)
        self.assertEqual(self.leds.called_list, [])
        self.assertEqual(self.ears.called_list, [])
        self.assertEqual(self.sound.called_list, [])


@pytest.mark.django_db
class TestRandMidi(TestChoreographyBase):
    def tearDown(self):
        close_old_async_connections()

    def test_randmidi(self):
        chor = base64.b16decode("0010")
        task = self.loop.create_task(self.ci.play_binary(chor))
        self.loop.run_until_complete(task)
        self.assertEqual(self.leds.called_list, [])
        self.assertEqual(self.ears.called_list, [])
        self.assertEqual(len(self.sound.called_list), 1)
        soundcall = self.sound.called_list[0]
        self.assertRegex(soundcall, r"start_playing_preloaded\(.+\)")


# Taichi choreographies are mostly about waiting, test them in parallel,
# using asyncio
class TaichiTestEnvironment:
    def __init__(self, test, random):
        super().__init__()
        self.test = test
        self.leds = LedsMock()
        self.ears = EarsMock()
        self.sound = SoundMock()
        self.ci = ChoreographyInterpreter(self.leds, self.ears, self.sound)
        self.ci.taichi_random = random

    async def run(self):
        self.sound.called_list = []
        self.leds.called_list = []
        self.ears.called_list = []
        await self.ci.start("nabtaichid/taichi.chor")
        await self.ci.wait_until_complete()
        self.test.assertTrue(len(self.sound.called_list) > 0)
        self.test.assertTrue(len(self.leds.called_list) > 0)
        self.test.assertTrue(len(self.ears.called_list) > 0)
        await self.ci.stop()
        # Check at least some leds were on.
        color_leds = 0
        off_leds = 0
        for ledi in self.leds.called_list:
            if ledi.endswith("0,0,0)"):
                off_leds = off_leds + 1
            else:
                color_leds = color_leds + 1
        self.test.assertTrue(color_leds > 0)
        self.test.assertTrue(off_leds > 0)


@pytest.mark.django_db
class TestTaichiChoreographies(unittest.TestCase):
    def tearDown(self):
        close_old_async_connections()

    def _do_test_task(self, random):
        environment = TaichiTestEnvironment(self, random)
        return environment.run()

    async def _do_test_taichi(self):
        tasks = map(lambda rnd: self._do_test_task(rnd), range(0, 29))
        await asyncio.gather(*tasks)

    def test_taichi(self):
        loop = asyncio.new_event_loop()
        loop.set_debug(True)
        asyncio.set_event_loop(loop)
        asyncio.run(self._do_test_taichi())


@pytest.mark.django_db
class TestStreamingChoregraphy(TestChoreographyBase):
    def tearDown(self):
        close_old_async_connections()

    def test_streaming(self):
        task = self.loop.create_task(
            self.ci.start(ChoreographyInterpreter.STREAMING_URN)
        )
        self.loop.run_until_complete(task)
        task = self.loop.create_task(asyncio.sleep(1))
        self.loop.run_until_complete(task)
        self.assertEqual(self.sound.called_list, [])
        self.assertTrue(len(self.leds.called_list) > 0)
        self.assertTrue(len(self.ears.called_list) > 0)
        task = self.loop.create_task(self.ci.stop())
        self.loop.run_until_complete(task)
        # Check at least some leds were on.
        color_leds = 0
        off_leds = 0
        for ledi in self.leds.called_list:
            if ledi.endswith("0,0,0)"):
                off_leds = off_leds + 1
            else:
                color_leds = color_leds + 1
        self.assertTrue(color_leds > 0)
        self.assertTrue(off_leds > 0)

    def test_streaming_n(self):
        task = self.loop.create_task(
            self.ci.start(ChoreographyInterpreter.STREAMING_URN + ":3")
        )
        self.loop.run_until_complete(task)
        task = self.loop.create_task(asyncio.sleep(1))
        self.loop.run_until_complete(task)
        self.assertEqual(self.sound.called_list, [])
        self.assertTrue(len(self.leds.called_list) > 0)
        self.assertTrue(len(self.ears.called_list) > 0)
        task = self.loop.create_task(self.ci.stop())
        self.loop.run_until_complete(task)

    def test_streaming_chors(self):
        for chor in range(1, 4):
            self.sound.called_list = []
            self.leds.called_list = []
            self.ears.called_list = []
            task = self.loop.create_task(
                self.ci.start(f"nabd/streaming/{chor}.chor")
            )
            self.loop.run_until_complete(task)
            task = self.loop.create_task(asyncio.sleep(4))
            self.loop.run_until_complete(task)
            self.assertEqual(self.sound.called_list, [])
            self.assertTrue(len(self.leds.called_list) > 0)
            self.assertEqual(self.ears.called_list, [])
            task = self.loop.create_task(self.ci.stop())
            self.loop.run_until_complete(task)
