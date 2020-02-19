import random
import time
import asyncio
from .resources import Resources
from .leds import Led
from .ears import Ears
from contextlib import suppress
from .cancel import wait_with_cancel_event
import logging
import traceback
import urllib.request


class ChoreographyInterpreter:
    def __init__(self, leds, ears, sound):
        self.leds = leds
        self.ears = ears
        self.sound = sound
        self.running_task = None
        self.running_ref = None
        self.timescale = 0
        self.cancel_event = None
        # Random is for ifne, only used in taichi.
        # Generator based on original code yielding 0-29, not exactly
        # uniformly.
        # Original code:
        # set chorrandom=((Iecholn rand&255)*30)>>8; // v16
        #
        # 0 has a probability of 9/256
        # 1-28 have a probabilty of 8/256
        # 29 has a probability of 7/256.
        self.taichi_random = int(random.randint(0, 255) * 30 >> 8)
        self.taichi_directions = [0, 0]
        self.current_palette = [(0, 0, 0) for x in range(8)]

    STREAMING_URN = "urn:x-chor:streaming"
    DATA_MTL_BINARY_SCHEME = "data:application/x-nabaztag-mtl-choreography"

    # from nominal.010120_as3.mtl
    MTL_OPCODE_HANDLDERS = [
        "nop",
        "frame_duration",
        "undefined",
        "undefined",
        "undefined",
        "undefined",
        "undefined",  # 'set_color', but commented
        "set_led_color",
        "set_motor",
        "set_leds_color",  # v16
        "set_led_off",  # v17
        "undefined",
        "undefined",
        "undefined",
        "set_led_palette",
        "undefined",  # 'set_palette', but commented
        "randmidi",
        "avance",
        "ifne",  # only used for taichi
        "attend",
        "setmotordir",  # v16
    ]

    STREAMING_OPCODE_HANDLERS = [
        "nop",
        "nop_1",  # frame_duration is ignored
        "undefined",
        "undefined",
        "undefined",
        "undefined",
        "undefined",  # 'set_color', but commented
        "set_led_color",
        "undefined",
        "undefined",  # v16
        "set_led_off",  # v17
        "undefined",
        "undefined",
        "undefined",
        "set_led_palette_streaming",
        "undefined",  # 'set_palette', but commented
        "undefined",
        "undefined",
        "undefined",  # only used for taichi
        "undefined",
        "undefined",  # v16
    ]

    # from Nabaztag_wait.vasm
    VASM_OPCODE_HANDLERS = [
        "nop",
        "frame_duration",
        "play_midi",
        "stop_midi",
        "play_sound",
        "stop_sound",
        "echo",
        "set_led_color",
        "set_motor",
        "avance",
        "attend",
        "end",
        "wait_music",
        "set",
        "ifne",
        "rand",
    ]

    MIDI_LIST = [
        "choreographies/1noteA4.mp3",
        "choreographies/1noteB5.mp3",
        "choreographies/1noteBb4.mp3",
        "choreographies/1noteC5.mp3",
        "choreographies/1noteE4.mp3",
        "choreographies/1noteF4.mp3",
        "choreographies/1noteF5.mp3",
        "choreographies/1noteG5.mp3",
        "choreographies/2notesC6C4.mp3",
        "choreographies/2notesC6F5.mp3",
        "choreographies/2notesD4A5.mp3",
        "choreographies/2notesD4G4.mp3",
        "choreographies/2notesD5G4.mp3",
        "choreographies/2notesE5A5.mp3",
        "choreographies/2notesE5C6.mp3",
        "choreographies/2notesE5E4.mp3",
        "choreographies/3notesA4G5G5.mp3",
        "choreographies/3notesB5A5F5.mp3",
        "choreographies/3notesB5D5C6.mp3",
        "choreographies/3notesD4E4G4.mp3",
        "choreographies/3notesE5A5C6.mp3",
        "choreographies/3notesE5C6D5.mp3",
        "choreographies/3notesE5D5A5.mp3",
        "choreographies/3notesF5C6G5.mp3",
    ]

    STREAMING_CHOREGRAPHIES = "nabd/streaming/*.chor"

    PALETTES = [
        [
            (255, 12, 0),
            (0, 255, 31),
            (255, 242, 0),
            (0, 3, 255),
            (255, 242, 0),
            (0, 255, 31),
            (255, 12, 0),
            (0, 0, 0),
        ],  # acidulée
        [
            (95, 0, 255),
            (127, 0, 255),
            (146, 0, 255),
            (191, 0, 255),
            (223, 0, 255),
            (255, 0, 223),
            (255, 0, 146),
            (0, 0, 0),
        ],  # violet
        [
            (255, 255, 255),
            (255, 255, 255),
            (255, 255, 255),
            (255, 255, 255),
            (255, 255, 255),
            (255, 255, 255),
            (255, 255, 255),
            (0, 0, 0),
        ],  # lumiere
        [
            (254, 128, 2),
            (243, 68, 2),
            (216, 6, 7),
            (200, 4, 13),
            (170, 0, 24),
            (218, 5, 96),
            (207, 6, 138),
            (0, 0, 0),
        ],  # emotion
        [
            (20, 155, 18),
            (255, 0, 0),
            (252, 243, 5),
            (20, 155, 18),
            (252, 243, 5),
            (255, 0, 0),
            (20, 155, 18),
            (0, 0, 0),
        ],  # oriental
        [
            (252, 238, 71),
            (206, 59, 69),
            (85, 68, 212),
            (78, 167, 82),
            (243, 75, 153),
            (151, 71, 196),
            (255, 255, 255),
            (0, 0, 0),
        ],  # pastel
        [
            (204, 255, 102),
            (204, 255, 0),
            (153, 255, 0),
            (51, 204, 0),
            (0, 153, 51),
            (0, 136, 0),
            (0, 102, 51),
            (0, 0, 0),
        ],  # nature
    ]

    # Leds in choreographies are reversed
    LEDS = {
        0: Led.BOTTOM,
        1: Led.RIGHT,  # when looking at the rabbit
        2: Led.CENTER,
        3: Led.LEFT,
        4: Led.NOSE,
    }

    OPCODE_HANDLERS = {
        "mtl": MTL_OPCODE_HANDLDERS,
        "vasm": VASM_OPCODE_HANDLERS,
        "streaming": STREAMING_OPCODE_HANDLERS,
    }

    async def nop(self, index, chor):
        return index

    async def nop_1(self, index, chor):
        return index + 1

    async def frame_duration(self, index, chor):
        self.timescale = 10 * chor[index]
        return index + 1

    async def set_led_color(self, index, chor):
        led = ChoreographyInterpreter.LEDS[chor[index]]
        r = chor[index + 1]
        g = chor[index + 2]
        b = chor[index + 3]
        self.leds.set1(led, r, g, b)
        return index + 6

    async def set_motor(self, index, chor):
        motor = chor[index]
        position = chor[index + 1]
        direction = chor[index + 2]
        await self.ears.go(motor, position, direction)
        return index + 3

    async def set_leds_color(self, index, chor):
        r = chor[index]
        g = chor[index + 1]
        b = chor[index + 2]
        self.leds.setall(r, g, b)
        return index + 3

    async def set_led_off(self, index, chor):
        led = ChoreographyInterpreter.LEDS[chor[index]]
        self.leds.set1(led, 0, 0, 0)
        return index + 1

    async def set_led_palette(self, index, chor):
        led = ChoreographyInterpreter.LEDS[chor[index]]
        palette_ix = chor[index + 1] & 7
        (r, g, b) = self.current_palette[palette_ix]
        self.leds.set1(led, r, g, b)
        return index + 2

    async def set_led_palette_streaming(self, index, chor):
        led = ChoreographyInterpreter.LEDS[chor[index]]
        col_ix = chor[index + 1] & 3
        palette_ix = self.chorst_palettecolors[col_ix]
        (r, g, b) = self.current_palette[palette_ix]
        self.leds.set1(led, r, g, b)
        return index + 2

    async def randmidi(self, index, chor):
        await self.sound.start_playing(
            random.choice(ChoreographyInterpreter.MIDI_LIST)
        )
        return index

    async def avance(self, index, chor):
        motor = chor[index]
        delta = chor[index + 1]
        direction = self.taichi_directions[motor]
        await self.ears.move(motor, delta, direction)
        return index + 2

    async def ifne(self, index, chor):
        if self.taichi_random == chor[index]:
            return index + 3
        rel = (chor[index + 1] << 8) + chor[index + 2]
        if rel >= 32768:  # assumed signed (?)
            rel = rel - 65536
        return index + rel + 3

    async def attend(self, index, chor):
        await self.ears.wait_while_running()
        await self.sound.wait_until_done(self.cancel_event)
        return index

    async def setmotordir(self, index, chor):
        motor = chor[index]
        dir = chor[index + 1]
        self.taichi_directions[motor] = dir
        return index + 2

    async def play_binary(self, chor, opcodes="mtl", timescale=0):
        if chor[0] == 1 and chor[1] == 1 and chor[2] == 1 and chor[3] == 1:
            # Consider this is the header
            await self.do_play_binary(4, chor, opcodes, timescale)
        else:
            await self.do_play_binary(0, chor, opcodes, timescale)

    async def do_play_binary(self, start_index, chor, opcodes, timescale):
        index = start_index
        self.timescale = timescale

        next_time = time.time()
        opcode_handlers = ChoreographyInterpreter.OPCODE_HANDLERS[opcodes]
        while index < len(chor):
            wait = chor[index]
            # do some wait now
            next_time = next_time + (wait * self.timescale / 1000.0)
            sleep_delta = next_time - time.time()
            if sleep_delta > 0:
                await asyncio.sleep(sleep_delta)
            index = index + 2
            if index > len(chor):
                # taichi.chor ends with a wait
                break
            opcode = chor[index - 1]
            try:
                opcode_handler = opcode_handlers[opcode]
                handler = getattr(self, opcode_handler)
            except IndexError as err:
                # 255 apparently used for end.
                if opcode != 255:
                    print(f"Unknown opcode {opcode}")
                return
            except AttributeError as err:
                print(f"Unknown opcode {opcode} {err}")
                return
            index = await handler(index, chor)

    async def play_streaming(self, ref):
        ref0 = ref[len(ChoreographyInterpreter.STREAMING_URN) :]
        if ref0 == "":
            self.current_palette_is_random = True
        else:
            self.current_palette_is_random = False
            self.current_palette = ChoreographyInterpreter.PALETTES[
                int(ref0[1:]) & 7
            ]
        chorst_oreille_chance = None
        while True:
            if chorst_oreille_chance is None:
                chorst_oreille_chance = 0
                left, right = random.choice([(0, 10), (10, 0)])
                await self.ears.go(Ears.LEFT_EAR, left, Ears.FORWARD_DIRECTION)
                await self.ears.go(
                    Ears.RIGHT_EAR, right, Ears.FORWARD_DIRECTION
                )
            else:
                if random.randint(0, chorst_oreille_chance) == 0:
                    pos = random.choice([0, 5, 10, 14])
                    await self.ears.go(
                        Ears.LEFT_EAR, pos, Ears.FORWARD_DIRECTION
                    )
                    pos = random.choice([0, 5, 10, 14])
                    await self.ears.go(
                        Ears.RIGHT_EAR, pos, Ears.FORWARD_DIRECTION
                    )
                    chorst_oreille_chance = (chorst_oreille_chance + 1) % 4
            file = await Resources.find(
                "choreographies",
                ChoreographyInterpreter.STREAMING_CHOREGRAPHIES,
            )
            chor = file.read_bytes()
            chorst_tempo = 160 + random.randint(0, 90)
            chorst_loops = 3 + random.randint(0, 17)
            if self.current_palette_is_random:
                self.current_palette = random.choice(
                    ChoreographyInterpreter.PALETTES
                )
            self.chorst_palettecolors = [
                random.randint(0, 7),
                random.randint(0, 7),
                random.randint(0, 7),
            ]
            for ix in range(chorst_loops):
                await self.play_binary(chor, "streaming", chorst_tempo)

    async def start(self, ref):
        if ref != self.running_ref:
            if self.running_task:
                self.running_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self.running_task
            self.running_task = asyncio.ensure_future(self.play(ref))
            self.running_ref = ref

    async def stop(self):
        if self.running_task:
            self.running_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.running_task
            self.running_task = None
            self.running_ref = None

    async def wait_until_complete(self, event=None):
        self.cancel_event = event
        await wait_with_cancel_event(self.running_task, event, self.stop)
        self.running_task = None
        self.running_ref = None
        self.cancel_event = None

    async def play(self, ref):
        self.cancel_event = None
        try:
            if ref.startswith(ChoreographyInterpreter.STREAMING_URN):
                await self.play_streaming(ref)
            elif ref.startswith(
                ChoreographyInterpreter.DATA_MTL_BINARY_SCHEME
            ):
                chor = urllib.request.urlopen(ref).read()
                await self.play_binary(chor)
            else:
                # Assume a resource for now.
                file = await Resources.find("choreographies", ref)
                chor = file.read_bytes()
                await self.play_binary(chor)
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.info(
                f"Crash in choreography interpreter: {traceback.format_exc()}"
            )
