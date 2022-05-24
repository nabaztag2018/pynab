import asyncio
import logging
import traceback

from nabcommon.nabservice import NabService

from .button_virtual import ButtonVirtual
from .ears_virtual import EarsVirtual
from .leds import Led
from .leds_virtual import LedsVirtual
from .nabio import NabIO
from .rfid_virtual import RfidVirtual
from .sound_virtual import SoundVirtual


class NabIOVirtual(NabIO):
    """
    Virtual implementation of nabio for web development
    """

    def __init__(self):
        super().__init__()
        self.virtual_clients = set()
        self.loop = asyncio.get_event_loop()
        self.loop.create_task(
            asyncio.start_server(
                self.virtual_loop, NabService.HOST, NabService.PORT_NUMBER + 1
            )
        )
        self.ears = EarsVirtual(self)
        self.leds = LedsVirtual(self)
        self.sound = SoundVirtual(self)
        self.button = ButtonVirtual()
        self.rfid = RfidVirtual()

    async def gestalt(self):
        left_ear_position, right_ear_position = await self.ears.get_positions()
        left_ear_status = f"virtual (position={left_ear_position})"
        right_ear_status = f"virtual (position={right_ear_position})"
        return {
            "model": "Virtual nab",
            "sound_card": "Virtual sound",
            "sound_input": self.has_sound_input(),
            "rfid": self.has_rfid(),
            "left_ear_status": left_ear_status,
            "right_ear_status": right_ear_status,
        }

    def has_sound_input(self):
        return False

    def has_rfid(self):
        return False

    def network_interface(self):
        return "eth0"

    def update_rabbit(self):
        for writer in self.virtual_clients:
            self.display_rabbit(writer)

    def color_to_ascii(self, color, black_char=None):
        ANSI_COLORS = {
            (0, 0, 0): 0,
            (255, 0, 0): 1,
            (0, 255, 0): 2,
            (255, 255, 0): 3,
            (0, 0, 255): 4,
            (255, 0, 255): 5,
            (0, 255, 255): 6,
            (255, 255, 255): 7,
        }
        r, g, b = color
        min_delta = None
        min_ix = None
        for ansi_color, ix in ANSI_COLORS.items():
            ansi_r, ansi_g, ansi_b = ansi_color
            delta = (
                (r - ansi_r) * (r - ansi_r)
                + (g - ansi_g) * (g - ansi_g)
                + (b - ansi_b) * (b - ansi_b)
            )
            if min_delta is None or delta < min_delta:
                min_delta = delta
                min_ix = ix
        if min_ix == 0 and black_char is not None:
            return black_char
        return f"\033[4{min_ix}m \033[49m"

    def display_ear(self, ear):
        if ear < 3 or ear > 14:
            return ["XX   ▊", "     ▊", "     ▊", "     ▊", "     ▊"]
        if ear >= 8 and ear < 12:
            return ["XX    ", "      ", "      ", "      ", " ▊▊▊▊▊"]
        return ["XX    ", "  ▊   ", "   ▊  ", "    ▊ ", "     ▊"]

    def display_rabbit(self, writer):
        leds = self.leds.leds
        left_ear = self.display_ear(self.ears.left)
        right_ear = self.display_ear(self.ears.right)
        right_ear = [line[::-1] for line in right_ear]
        ears = ""
        ears_line_ix = 0
        for left_l, right_l in zip(left_ear, right_ear):
            if ears_line_ix == 0:
                left_l = left_l.replace("XX", "{:2d}".format(self.ears.left))
                right_l = right_l.replace(
                    "XX", "{:2d}".format(self.ears.right)
                )
            sep = "   "
            if ears_line_ix == 4:
                sep = "▊▊▊"
            ears = ears + left_l + sep + right_l + "\n"
            ears_line_ix = ears_line_ix + 1
        nose = self.color_to_ascii(leds[Led.NOSE], "T")
        left = self.color_to_ascii(leds[Led.LEFT], "▊")
        center = self.color_to_ascii(leds[Led.CENTER], "▊")
        right = self.color_to_ascii(leds[Led.RIGHT], "▊")
        bottom = self.color_to_ascii(leds[Led.BOTTOM], "▊")
        writer.write("\033[2J\033[H".encode("utf8"))
        if self.sound.currently_playing:
            sound_str = f"🔊 {self.sound.sound_file}\n"
        else:
            sound_str = ""
        rabbit = (
            f"{ears}"
            "    ▊◉▊▊▊◉▊\n"
            f"    ▊▊▊{nose}▊▊▊\n"
            "   ▊▊▊▊▊▊▊▊▊\n"
            f"   ▊▊{left}▊{center}▊{right}▊▊\n"
            "  ▊▊▊▊▊▊▊▊▊▊▊\n"
            f"   ▊▊▊{bottom}{bottom}{bottom}▊▊▊\n"
            f"{sound_str}\n"
        )
        writer.write(rabbit.encode("utf8"))

    # Handle service through TCP/IP protocol
    async def virtual_loop(self, reader, writer):
        self.virtual_clients.add(writer)
        try:
            self.display_rabbit(writer)
            while not reader.at_eof():
                await reader.readline()
            writer.close()
            await writer.wait_closed()
        except ConnectionResetError:
            pass
        except BrokenPipeError:
            pass
        except Exception:
            logging.debug(traceback.format_exc())
        finally:
            self.virtual_clients.remove(writer)
