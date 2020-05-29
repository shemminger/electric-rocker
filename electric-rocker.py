#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Electrc Rocker LED animation
# Author Stephen Hemminger <stephen@networkplumber.org>

import signal
import time
from math import floor

from ant.core import driver
from ant.core.node import Node, Network, ChannelID
from ant.core.constants import NETWORK_KEY_ANT_PLUS, NETWORK_NUMBER_PUBLIC, TIMEOUT_NEVER
from ant.core.exceptions import DriverError
from ant.plus.power import *

from rpi_ws281x import PixelStrip, Color

# Rider configuration
FTP = 250

# Zwift power zone color map
COLORMAP = [
    {
        "base": 0,
        "rgb": [0, 0, 0]
    },  # Black
    {
        "base": 1,
        "rgb": [64, 64, 64]
    },  # White
    {
        "base": 60,
        "rgb": [0, 0, 127]
    },  # Blue
    {
        "base": 76,
        "rgb": [0, 127, 0]
    },  # Green
    {
        "base": 90,
        "rgb": [127, 127, 0]
    },  # Yellow
    {
        "base": 105,
        "rgb": [127, 63, 0]
    },  # Orange
    {
        "base": 119,
        "rgb": [255, 0, 0]
    },  # Red
]

# LED strip configuration:
LED_COUNT = 120  # Number of LED pixels.
LED_PIN = 18  # GPIO pin connected to the pixels (18 uses PWM!).
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10  # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 255  # Set to 0 for darkest and 255 for brightest
LED_INVERT = False  # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL = 0  # set to '1' for GPIOs 13, 19, 41, 45 or 53


# Define functions which animate LEDs in various ways.
def colorWipe(strip, color, wait_ms=50):
    """Wipe color across display a pixel at a time."""
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms / 1000.0)


def theaterChase(strip, color, wait_ms=50, iterations=10):
    """Movie theater light style chaser animation."""
    for j in range(iterations):
        for q in range(3):
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i + q, color)
            strip.show()
            time.sleep(wait_ms / 1000.0)
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i + q, 0)


# convert power value to zone color
def zone_color(power):
    percent = (100. * power) / FTP
    for z in COLORMAP:
        b = z['base']
        if percent < b:
            break
        rgb = z['rgb']
    return Color(*rgb)


class PowerMeter(BicyclePower):
    def __init__(self, node, network):
        super(PowerMeter, self).__init__(
            node, network, callbacks={'onPowerData': self.power_data})
        self.previous_count = None
        self.previous_power = None
        self.power = None
        self.cadence = None

    def power_data(self, count, _differ, _ratio, cadence, apower, ipower):
        if cadence is not None:
            self.cadence = cadence
        if self.previous_count is None:
            self.power = ipower
        else:
            # use accumulated power to bridge gaps
            events = self.wrapDifference(count, self.previous_count, 256)
            if events == 0:
                return
            total = self.wrapDifference(apower, self.previous_power, 65536)
            self.power = total / events
        self.previous_power = apower
        self.previous_count = count

    def get(self):
        return (self.power, self.cadence)


def sigterm_handler(_signo, _stack_frame):
    # Raises SystemExit(0):
    sys.exit(0)


if __name__ == "__main__":
    # Create NeoPixel object with appropriate configuration.
    strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT,
                       LED_BRIGHTNESS, LED_CHANNEL)
    # Intialize the library (must be called once before other functions).
    strip.begin()

    # Initial animation
    colorWipe(strip, Color(127, 0, 0), wait_ms=5)  # Red  wipe

    # Configure ANT
    print('Configure..')
    device = driver.USB2Driver(idVendor=0x0fcf, idProduct=0x1009)

    print('Starting...')
    antnode = Node(device)
    antnode.start()

    # Ready animation
    colorWipe(strip, Color(127, 127, 0), wait_ms=5)  # Yellow wipe

    network = Network(key=NETWORK_KEY_ANT_PLUS, name='N:ANT+')
    antnode.setNetworkKey(NETWORK_NUMBER_PUBLIC, network)
    print('Ant...')

    powermeter = PowerMeter(antnode, network)
    powermeter.open(searchTimeout=TIMEOUT_NEVER)
    print('Powermeter...')

    signal.signal(signal.SIGTERM, sigterm_handler)
    colorWipe(strip, Color(0, 0, 127), wait_ms=5)  # Green wipe

    try:
        avg_power = 0
        while True:
            # read powermeter every second
            (power, cadence) = powermeter.get()
            if power is None:
                time.sleep(5)
                continue

            avg_power = (power + 3 * avg_power) / 4
            color = zone_color(avg_power)

            if cadence is None:
                # solid color if no cadence
                colorWipe(strip, color, wait_ms=1000 / LED_COUNT)
            elif cadence == 0:
                # sleep if not pedaling
                time.sleep(1)
            else:
                # default animation of 50ms == cadence 200
                delay_ms = 10000 / cadence
                repeats = floor(1000 / delay_ms)
                theaterChase(
                    strip, color, wait_ms=delay_ms, iterations=repeats)
    finally:
        colorWipe(strip, Color(0, 0, 0), wait_ms=10)
        powermeter.close()
        antnode.stop()
