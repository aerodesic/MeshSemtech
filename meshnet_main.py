import gc
from uthread import thread
from urandom import randrange
from time import sleep
import machine

VERSION    = "1"   # Software version
DB_VERSION = "1"   # Database version

DEVICE_NAME = "pinger_test"

import network
MAC_ADDRESS = "".join("%02x" % d for d in network.WLAN().config('mac'))
del(network)

_BROADCAST_UNIT = const(0x3F)

# Simulate nvram storge using flash
# nvram is getting smacked WAY too often
def storage(data=None):
    try:
        if data != None:
            with open('.config', 'w') as f:
                f.write(data)
        else:
            with open('.config') as f:
                data = f.read()

        f.close()
    except:
        pass

    return data

from configdata import *
CONFIG_DATA = ConfigData(read = storage,
                         write = storage,
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
                            'lora': {
                                'network': '0',
                                'unit': '1',
                                'channel': '64',
                                'direction': 'up',
                                '%direction%options': ( 'up', 'down' ),
                                'datarate': '4',
                            },
                         })

gc.threshold(20000)
gc.collect()

from ssd1306_i2c import Display
display = Display()
display.show_text_wrap("Starting...")

_NETWORK = int(CONFIG_DATA.get("lora.network", "0"))
_UNIT = int(CONFIG_DATA.get("lora.unit", "1"))

from loradomains import US902_928 as domain
from loracom import LoRaHandler
lora=LoRaHandler(
        domain,
        enable_crc=False,
        channel=(int(CONFIG_DATA.get("lora.channel", default='64')), CONFIG_DATA.get("lora.direction", default='up'), int(CONFIG_DATA.get("lora.datarate", default='4'))),
)
lora.init()

# Start web server
from lorawebserver import *
webserver = LoRaWebserver(
        config=CONFIG_DATA,
        display=lambda text, line=4, clear=False : display.show_text_wrap(text, start_line=line, clear_first=clear),
)
webserver.start()

led = machine.Pin(25, machine.Pin.OUT)

import sys

# Input is a byte array of data.  Output is bytes with escape chars and returned checksum of array
def escape_data(data, sum=0):
    out = bytearray()
    for i in range(len(data)):
        ch = data[i]
        sum += ch
        if ch < 32 or ch > 127 or ch in [ ord('$'), ord('%'), ord(':') ]:
            out.append(ord('%'))
            hexval = "%02x" % ch
            out.append(ord(hexval[0]))
            out.append(ord(hexval[1]))
        else:
            out.append(ch)
            
    # return out.decode(), sum
    return bytes(out), sum

def handle_lora_receive(t):
    global _NETWORK, _UNIT

    while t.running:
        packet = lora.receive_packet()
        if 'data' in packet:
            led.on()
            data = packet['data']
            print("Rcv: %s" % data)
            # The address is the first two bytes of the message
            address = data[0] * 256 + data[1]
            net = address >> 6
            unit = address % 64
            # If to our network and either broadcast or our unit, process it.
            if (net == _NETWORK and (unit == _BROADCAST_UNIT or unit == _UNIT)):
                ##########################
                # Decrypt packet here...
                ##########################
                fromaddr = data[3] * 256 + data[4]
                display.show_text_wrap("from %x %d" % (fromaddr, packet['rssi']), start_line=1, clear_first=False)
                display.show_text_wrap(data[5:].decode(), start_line=2, clear_first=False)
                # Send packet to output stream
                output, sum = escape_data(data)
                sys.stdout.write("$")
                sys.stdout.write(output)
                sys.stdout.write(":%d:%d\r\n" % (sum % 0x10000, packet['rssi']))

                # if a PING packet, reply with 'reply' packet
                if data[5:10] == b'ping ':
                    # Send reponse to the originating address
                    send_packet_to(fromaddr, "reply %s (%d)" % (data[10:].decode(), packet['rssi']))
            led.off()

    return 0


# Remove #xx escapes from message and return message cksum
def unescape_data(buffer):
    # print("escape_process in: %s" % buffer)
    out = bytearray()
    sum = 0
    index = 0
    while index < len(buffer):
        ch = buffer[index]
        sum += ch
        if ch == ord('%'):
            # Accept two hex values as a character
            out.append(int("0x%c%c" % (buffer[index + 1], buffer[index+2])) % 256)
            index += 2
        else:
            out.append(ch)
        index += 1

    # print("escape_process out: %s, sum %d" % (out, sum))
    return bytes(out), sum

def handle_lora_send(t):
    state = 'start'

    while t.running:
        ch = sys.stdin.read(1)
        if state == 'start':
            if ch == '$':
                # Start over if $
                state = 'data'
                buffer = bytearray()

        elif state == 'data':
            if ch == ':':
                # End of data
                state = 'cksum'
                value = bytearray()

            else:
                buffer.extend(ch)

        elif state == 'cksum':
            if ch == '\n':
                try:
                    value, dummy = unescape_data(value)
                    cksum = int(value, 16)
                    buffer, found = unescape_data(buffer)
                    if found == cksum:
                        # The destination address is taken from the first two bytes
                        # The source address along with the random byte will be generated...
                        address = (buffer[0] << 8) + buffer[1]
                        send_packet_to(address, buffer[2:])
                    else:
                        print("-ERROR: wanted %04x found %04x" % (found, cksum))

                except Exception as e:
                    print("-ERROR: %s" % str(e))

                state = 'start'

            else:
                value.extend(ch)


def send_packet_to(address, buffer):
    global _NETWORK, _UNIT

    # print("send_packet_to: %04x: %s" % (address, buffer))

    address = bytearray(((address >> 8) % 256, address % 256))

    fromaddr = (_NETWORK << 6) + _UNIT
    header = bytearray((randrange(0, 256), (fromaddr >> 8) % 256, fromaddr % 256))

    if type(buffer) == str:
        buffer = bytearray(buffer)

    buffer = header + buffer

    ######################
    # Encrypt buffer here
    ######################

    lora.send_packet(address + buffer)
    # print("sent %s" % bytes(address + buffer))

    gc.collect()

from time import ticks_ms, ticks_diff
ping_counter = 0
last_time = ticks_ms()

def send_button_packet(event):
    global ping_counter
    global last_time

    now = ticks_ms()

    if ticks_diff(now, last_time) > 500:
        ping_counter += 1
        # Send to broadcast unit on our network
        address = (_NETWORK << 6) + _BROADCAST_UNIT
        send_packet_to(address, "ping %d" % ping_counter)
        last_time = now

# Set up interrupt on a pin to send a broadcast packet
button = machine.Pin(0)
button.irq(handler=send_button_packet, trigger=machine.Pin.IRQ_FALLING)

# Start thread to handle input from LORA
input_thread = thread(run=handle_lora_receive, stack=8192)
input_thread.start()

output_thread = thread(run=handle_lora_send, stack=8192)
output_thread.start()

display.show_text_wrap(CONFIG_DATA.get("apmode.essid"), clear_first=False)


# Watch memory
while True:
    sleep(30)
    gc.collect()
    display.show_text_wrap("Mem: %d" % gc.mem_free(), start_line=6, clear_first=False)
    display.show_text_wrap("Tx %d Rx %d" % (lora._tx_interrupts, lora._rx_interrupts), start_line=7, clear_first=False)

