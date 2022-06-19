#!/opt/pynab/venv/bin/python

# Script executed at boot and at shutdown.
# At boot, set leds to orange.
# At shutdown, turn leds off.

import os
import platform
import re
import sys

from rpi_ws281x import Adafruit_NeoPixel, Color  # type: ignore
from smbus2 import SMBus


def set_leds(color):
    LED_COUNT = 5
    LED_PIN = 13  # GPIO pin connected to the pixels (18 uses PWM!).
    LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
    LED_DMA = 12  # DMA channel to use for generating signal (try 10)
    LED_BRIGHTNESS = 200  # Set to 0 for darkest and 255 for brightest
    LED_INVERT = False  # True to invert the signal
    # (when using NPN transistor level shift)
    LED_CHANNEL = 1  # set to '1' for GPIOs 13, 19, 41, 45 or 53

    strip = Adafruit_NeoPixel(
        LED_COUNT,
        LED_PIN,
        LED_FREQ_HZ,
        LED_DMA,
        LED_INVERT,
        LED_BRIGHTNESS,
        LED_CHANNEL,
    )
    # Intialize the library (must be called once before other functions).
    strip.begin()

    for led in range(6):
        strip.setPixelColor(led, color)

    strip.show()


def set_system_led(shutdown):
    # No need to set it at shutdown.
    # It will still blink multiple time after system halt even if it has been
    # disabled in Linux.
    if shutdown:
        return

    with open("/sys/class/leds/led0/trigger", "w") as f:
        f.write("none")

    kernel_version = platform.release()
    matchObj = re.match(r"[0-9]+", kernel_version)
    if matchObj:
        major_version = int(matchObj.group())
        with open("/sys/class/leds/led0/brightness", "w") as f:
            if major_version >= 5:
                f.write("0")
            else:
                f.write("255")


def probe_cr14():
    try:
        with SMBus(1) as bus:
            b = bus.read_byte_data(0x50, 0)
            return b == 0
    except OSError:
        return False


def probe_st25r391x():
    try:
        with SMBus(1) as bus:
            b = bus.read_byte_data(0x50, 0x7F)
            return b == 0b00101010
    except OSError:
        return False


def update_config_and_reboot(enabled, disabled):
    modified = False
    needs_enable = True
    with open("/boot/config.txt", "r") as f:
        content = f.readlines()
        for ix in range(0, len(content)):
            line = content[ix]
            if line.startswith(f"dtoverlay={enabled}"):
                needs_enable = False
            elif line.startswith(f"#dtoverlay={enabled}"):
                content[ix] = f"dtoverlay={enabled}\n"
                needs_enable = False
                modified = True
            elif line.startswith(f"dtoverlay={disabled}"):
                content[ix] = f"#dtoverlay={disabled}\n"
                modified = True
    if needs_enable:
        with open("/boot/config.txt", "a") as f:
            f.write(f"\ndtoverlay={enabled}\n")
            f.flush()
    elif modified:
        with open("/boot/config.txt", "w") as f:
            f.writelines(content)
            f.flush()
    if needs_enable or modified:
        set_leds(Color(0, 0, 255))
        os.system("reboot")


def configure_rfid_driver():
    # Determine if we need to switch drivers as they are conflicting.
    if os.path.exists("/dev/nfc0") or os.path.exists("/dev/rfid0"):
        # One of the driver was successful at loading and probing the device
        return
    if probe_st25r391x():
        update_config_and_reboot("st25r391x", "cr14")
    elif probe_cr14():
        update_config_and_reboot("cr14", "st25r391x")


if __name__ == "__main__":
    shutdown = len(sys.argv) > 1 and sys.argv[1] != "start"
    if shutdown:
        led_color = Color(0, 0, 0)
    else:
        led_color = Color(255, 0, 255)
    set_system_led(shutdown)
    set_leds(led_color)
    if not shutdown:
        configure_rfid_driver()
