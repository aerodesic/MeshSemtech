import gc

VERSION    = "1"   # Software version
DB_VERSION = "1"   # Database version

DEVICE_NAME = "pinger_test"

import network
MAC_ADDRESS = "".join("%02x" % d for d in network.WLAN().config('mac'))
del(network)

import machine
rtc=machine.RTC()

from configdata import *
CONFIG_DATA = ConfigData(read = rtc.memory,
                         write = rtc.memory,
                         version = DB_VERSION,
                         data = {
                            'device': {
                                'name': DEVICE_NAME,
                            },

                            'apmode': {
                                'essid': "%s-%s" % (DEVICE_NAME, MAC_ADDRESS[6:]),
                                'password': "zippydoda",
                            },
                        
                            'host': {
                                'ap': {
                                    'essid': '',
                                    'password': ''
                                },
                            },
                         })

del(rtc)
del(machine)

gc.threshold(20000)
gc.collect()

from ssd1306_i2c import Display
display = Display()
display.show_text_wrap("Starting...")

from lora_test import *
from loradomains import US902_928 as domain
lora=LoRaHandler(domain, channel=('up', 64), display=lambda text, line=0, clear=False : display.show_text_wrap(text, start_line=line, clear_first=clear))
lora.init()

# Start web server
from lorawebserver import *
webserver = LoRaWebserver(config=CONFIG_DATA, display=lambda text, line=4, clear=False : display.show_text_wrap(text, start_line=line, clear_first=clear))
webserver.start()

from time import sleep

# Watch memory
while True:
    sleep(30)
    gc.collect()
    display.show_text_wrap("Mem: %d" % gc.mem_free(), start_line=6, clear_first=False)
    display.show_text_wrap("Tx %d Rx %d" % (lora._tx_interrupts, lora._rx_interrupts), start_line=7, clear_first=False)

