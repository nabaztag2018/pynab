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

    def gestalt(self):
        return {
            "model": "Virtual nab",
            "sound_card": "Virtual sound",
            "sound_input": self.has_sound_input(),
            "rfid": self.has_rfid(),
            "left_ear_status": "virtual",
            "right_ear_status": "virtual",
        }

    def has_sound_input(self):
        return False

    def has_rfid(self):
        return True

    def test(self, test):
        return True

    def update_rabbit(self):
        for writer in self.virtual_clients:
            self.display_rabbit(writer)

    def color_to_ascii(self, color):
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
        return f"\033[4{min_ix}m \033[49m"

    def display_rabbit(self, writer):
        leds = self.leds.leds
        nose = self.color_to_ascii(leds[Led.NOSE])
        left = self.color_to_ascii(leds[Led.LEFT])
        center = self.color_to_ascii(leds[Led.CENTER])
        right = self.color_to_ascii(leds[Led.RIGHT])
        bottom = self.color_to_ascii(leds[Led.BOTTOM])
        writer.write("\033[2J\033[H".encode("utf8"))
        rabbit = (
            "     X   X\n"
            "     X   X\n"
            "     X   X\n"
            "     X   X\n"
            "     XXXXX\n"
            "    XoXXXoX\n"
            f"    XXX{nose}XXX\n"
            "   XXXXXXXXX\n"
            f"   XX{left}X{center}X{right}XX\n"
            "  XXXXXXXXXXX\n"
            f"   XXX{bottom}{bottom}{bottom}XXX\n"
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
