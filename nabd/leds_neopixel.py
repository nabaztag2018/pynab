from rpi_ws281x import Adafruit_NeoPixel, Color
from .leds import LedsSoft


class LedsNeoPixel(LedsSoft):  # pragma: no cover
    LED_PIN = 13  # GPIO pin connected to the pixels (18 uses PWM!).
    LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
    LED_DMA = 12  # DMA channel to use for generating signal (try 10)
    LED_BRIGHTNESS = 200  # Set to 0 for darkest and 255 for brightest
    # True to invert the signal (when using NPN transistor level shift)
    LED_INVERT = False
    LED_CHANNEL = 1  # set to '1' for GPIOs 13, 19, 41, 45 or 53
    LED_COUNT = 5

    PULSING_RATE = 0.100  # every 100ms

    def __init__(self):
        super().__init__()
        self.strip = Adafruit_NeoPixel(
            LedsNeoPixel.LED_COUNT,
            LedsNeoPixel.LED_PIN,
            LedsNeoPixel.LED_FREQ_HZ,
            LedsNeoPixel.LED_DMA,
            LedsNeoPixel.LED_INVERT,
            LedsNeoPixel.LED_BRIGHTNESS,
            LedsNeoPixel.LED_CHANNEL,
        )
        # Intialize the library (must be called once before other functions).
        self.strip.begin()

    def do_set(self, led, red, green, blue):
        # NeoPixel indexes on the strip do match the (original) values
        led_ix = led.value
        self.strip.setPixelColor(led_ix, Color(red, green, blue))

    def do_show(self):
        self.strip.show()
