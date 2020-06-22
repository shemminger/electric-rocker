#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
#
# Copyright (c) 2019, Stephen Hemminger

# Lightshow on medal rack

import signal
import time
import sys

from ant.core import driver
from ant.core.node import Node, Network, ChannelID
from ant.core.constants import NETWORK_KEY_ANT_PLUS, NETWORK_NUMBER_PUBLIC, TIMEOUT_NEVER
from ant.core.exceptions import DriverError
from ant.plus.power import *

import board
from adafruit_ws2801 import WS2801

NUMLEDS = 30

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


# convert power value to zone color
def zone_color(power):
    percent = (100. * power) / FTP
    for z in COLORMAP:
        b = z['base']
        if percent < b:
            break
        rgb = z['rgb']
    return Color(*rgb)


# use LED as rolling colors
class PowerMeter(BicyclePower):
    def __init__(self, count):
        super(PowerMeter, self).__init__(
            node, network, callbacks={
                'onPowerData': self.power_data,
            })
        self.previous_count = None
        self.previous_power = None
        self.power = None
        self.cadence = None

    def __str__(self):
        print('(power={}, cadence={})'.format(self.power, self.cadence))

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


def sigterm_handler(_signo, _stack_frame):
    # Raises SystemExit(0):
    sys.exit(0)


if __name__ == "__main__":
    leds = WS2801(board.D6, board.D5, NUMLEDS)
    leds.fill(0)

    # Configure ANT
    print('Configure..')
    device = driver.USB2Driver(idVendor=0x0fcf, idProduct=0x1008)

    print('Starting...')
    antnode = Node(device)
    antnode.start()

    network = Network(key=NETWORK_KEY_ANT_PLUS, name='N:ANT+')
    antnode.setNetworkKey(NETWORK_NUMBER_PUBLIC, network)
    print('Ant...')

    meter = PowerMeter(antnode, network)
    meter.open(searchTimeout=TIMEOUT_NEVER)
    print('Power...')

    signal.signal(signal.SIGTERM, sigterm_handler)

    try:
        avg_power = 0
        while True:
            (power, cadence) = meter.get()
            if power is None:
                time.sleep(5)
                continue

            avg_power = (power + 3 * avg_power) / 4
            color = zone_color(avg_power)

            print('Power: {} Cadence {}'.format(power, cadence))
            leds.append(color)
            leds.show()

    finally:
        meter.close()
        antnode.stop()
