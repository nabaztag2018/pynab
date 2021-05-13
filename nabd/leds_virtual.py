from .leds import Led, LedsSoft


class LedsVirtual(LedsSoft):
    def __init__(self, nabio_virtual):
        super().__init__()
        self.nabio_virtual = nabio_virtual
        self.leds = {
            Led.BOTTOM: (0, 0, 0),
            Led.RIGHT: (0, 0, 0),
            Led.CENTER: (0, 0, 0),
            Led.LEFT: (0, 0, 0),
            Led.NOSE: (0, 0, 0),
        }

    def do_set(self, led, red, green, blue):
        self.leds[led] = (red, green, blue)

    def do_show(self):
        self.nabio_virtual.update_rabbit()
