import gc
from uthread import thread
from urandom import randrange
from time import sleep
import machine

VERSION    = "1"   # Software version
DB_VERSION = "1"   # Database version

DEFAULT_DEVICE_NAME = "pinger_test"

import network
MAC_ADDRESS = "".join("%02x" % d for d in network.WLAN().config('mac'))
del(network)

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
                                'name': DEFAULT_DEVICE_NAME,
                            },

                            'apmode': {
                                'essid': "%s-%s" % (DEFAULT_DEVICE_NAME, MAC_ADDRESS[6:]),
                                'password': "zippydoda",
                            },
                        
                            'host': {
                                'ap': {
                                    'essid': '',
                                    'password': ''
                                },
                            },
                            'mesh': {
                                'address': '1',
                                'channel': '0',
                                'datarate': '0',
                            },
                         })

gc.threshold(20000)
gc.collect()

from ssd1306_i2c import Display
display = Display()
display.show_text_wrap("Starting...")

_ADDRESS = int(CONFIG_DATA.get("mesh.address", "1"))

from meshdomains import US902_MESHNET as domain
from meshnet import MeshNet, DataPacket, BROADCAST_ADDRESS

meshnet=MeshNet(
        domain,
        enable_crc=True,
        address=_ADDRESS,
        channel=(int(CONFIG_DATA.get("mesh.channel", default='64')), int(CONFIG_DATA.get("mesh.datarate", default='-1'))),
)
meshnet.set_promiscuous(True)
meshnet.set_debug(True)
meshnet.start()

# Start web server
from meshnetwebserver import *
webserver = MeshNetWebServer(
        config=CONFIG_DATA,
        display=lambda text, line=4, clear=False : display.show_text_wrap(text, start_line=line, clear_first=clear),
)
webserver.start()

led = machine.Pin(25, machine.Pin.OUT)

import sys

# Input is a byte array of data.  Output is bytes with escape chars
def escape_buffer(data):
    out = bytearray()
    for i in range(len(data)):
        ch = data[i]
        if ch < 32 or ch >= 127 or ch in [ ord('$'), ord('%'), ord(':'), ord(';') ]:
            out.append(ord('%'))
            hexval = "%02x" % ch
            out.append(ord(hexval[0]))
            out.append(ord(hexval[1]))
        else:
            out.append(ch)
            
    return bytes(out)

# Remove #xx escapes from message and return message cksum
def unescape_data(buffer):
    # print("escape_process in: %s" % buffer)
    out = bytearray()
    index = 0
    while index < len(buffer):
        ch = buffer[index]
        if ch == ord('%'):
            # Accept two hex values as a character
            out.append(int("0x%c%c" % (buffer[index + 1], buffer[index+2])) % 256)
            index += 2
        else:
            out.append(ch)
        index += 1

    return bytes(out)

def handle_meshnet_receive(t):
    global _ADDRESS

    while t.running:
        # Wait for a packet from the network
        packet = meshnet.receive_packet()
        led.on()

        # Display the packet contents
        if packet.promiscuous():
            print("RCVD: %s" % (str(packet)))

        elif type(packet) == DataPacket:
            # Process the packet if we can
            display.show_text_wrap("from %d %d" % (packet.source(), packet.rssi()), start_line=1, clear_first=False)
            display.show_text_wrap("protocol %d" % packet.protocol(), start_line=2, clear_first=False)

            output = "%d;%d;%s;%d" % (packet.source(), packet.protocol(), escape_buffer(packet.payload()), packet.rssi())
            cksum = checksum_buffer(output)
        
            # Send packet as text: <source address>;<protocol id>;<rssi>;<payload>:<checksum of chars before ';'>
            sys.stdout.write("$%s:%d\r\n" % (output, cksum % 0x10000))

            # if a PING packet, reply with 'reply' packet
            if packet.payload(start=0, end=5) == b'ping ':
                # Send response to the originating address
                newpacket = DataPacket(payload="reply %s (%d)" % (packet.payload(start=5).decode(), packet.rssi()), dest=packet.source(), protocol=packet.protocol())
                print("newpacket %s" % str(newpacket))
                meshnet.send_packet(newpacket)

        led.off()

    return 0


def checksum_buffer(buffer):
    if type(buffer) == str:
        buffer = bytearray(buffer)
    sum = 0
    for ch in buffer:
        sum += ch
    return sum

# $<address>;<protocol>;<payload>:<checksum>
def handle_meshnet_send(t):
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
                    cksum = int(value, 16)
                    found = checksum_buffer(buffer)
                    if found == cksum:
                        # Split buffer into address, protocol and payload
                        address, protocol, payload = split(buffer, ';')
                        # Remove escape chars from payload
                        payload = unescape_data(payload)

                        # Create a packet to the destination address with the declared payload and protocol
                        packet = DataPacket(protocol=int(protocol), dest=int(address), payload=payload)
                        mesh_net.send_packet(packet)
                    else:
                        print("-ERROR: wanted %04x found %04x" % (found, cksum))

                except Exception as e:
                    print("-ERROR: %s" % str(e))

                state = 'start'

            else:
                value.extend(ch)


### def send_packet_to(address, buffer):
###     global _ADDRESS
### 
###     # print("send_packet_to: %04x: %s" % (address, buffer))
### 
###     address = bytearray(((address >> 8) % 256, address % 256))
### 
###     header = bytearray((randrange(0, 256), (_ADDRESS >> 8) % 256, _ADDRESS % 256))
### 
###     if type(buffer) == str:
###         buffer = bytearray(buffer)
### 
###     buffer = header + buffer
### 
###     ######################
###     # Encrypt buffer here
###     ######################
### 
###     meshnet.send_packet(address + buffer)
###     # print("sent %s" % bytes(address + buffer))
### 
###     gc.collect()

from time import ticks_ms, ticks_diff
ping_counter = 0
last_time = ticks_ms()

def send_packet_button(event):
    global ping_counter
    global last_time

    now = ticks_ms()

    if ticks_diff(now, last_time) > 500:
        ping_counter += 1
        # Send to broadcast unit on our network
        packet = DataPacket(payload="ping %d" % ping_counter, dest=int(CONFIG_DATA.get("mesh.target")), next=BROADCAST_ADDRESS, protocol=99)
        # send_packet_to(packet)
        meshnet.send_packet(packet)
        last_time = now

# Set up interrupt on a pin to send a broadcast packet
button = machine.Pin(0)
button.irq(handler=send_packet_button, trigger=machine.Pin.IRQ_FALLING)

# Start thread to handle input from Mesh network
input_thread = thread(run=handle_meshnet_receive, stack=8192)
input_thread.start()

# output_thread = thread(run=handle_meshnet_send, stack=8192)
# output_thread.start()

display.show_text_wrap(CONFIG_DATA.get("apmode.essid"), clear_first=False)


# Watch memory
while False:
    sleep(5)
    gc.collect()
    display.show_text_wrap("Mem: %d" % gc.mem_free(), start_line=6, clear_first=False)
    display.show_text_wrap("Tx %d Rx %d" % (meshnet._tx_interrupts, meshnet._rx_interrupts), start_line=7, clear_first=False)

