import gc

VERSION    = "1"   # Software version
DB_VERSION = "1"   # Database version

import network
MAC_ADDRESS = "".join("%02x" % d for d in network.WLAN().config('mac'))
del(network)

import machine
rtc=machine.RTC()

from configdata import *
CONFIG_DATA = ConfigData(read = rtc.memory,
                         write = rtc.memory,
                         version=DB_VERSION,
                         data = {
                            'apmode': {
                                'essid': "%s-%s" % (DEVICE_NAME, MAC_ADDRESS[6:]),
                                'password': "zippydoda",
                            },
                        
                            'host': {
                                'ap': {
                                    'essid': ''
                                    'password': ''
                                },
                            },
                         })

del(rtc)
del(memory)

gc.collect()

from lora_test import *

lora=LoRaHandler()
lora.init()

