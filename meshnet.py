#
# MeshNet driver
#

from time import sleep
from ulock import *
from uqueue import *
from sx127x import SX127x_driver
from machine import SPI, Pin


_SX127x_DIO0  = const(26)   # DIO0 interrupt pin
_SX127x_DIO1  = const(35)   # DIO1 interrupt pin
_SX127x_DIO2  = const(34)   # DIO2 interrupt pin
_SX127x_SCK   = const(5)
_SX127x_MOSI  = const(27)
_SX127x_MISO  = const(19)
_SX127x_SS    = const(18)
_SX127x_RESET = const(14)
_SX127x_WANTED_VERSION = const(0x12)

class MeshNet(SX127x_driver):

    def __init__(self, domain, **kwargs):
        SX127x_driver.__init__(self, domain, **kwargs)

        self._meshlock = rlock()
        self._transmit_queue = queue()
        self._receive_queue = queue()

    def init(self):
        self._spi = SPI(baudrate=10000000, polarity=0, phase=0, bits=8, firstbit = SPI.MSB,
                        sck = Pin(_SX127x_SCK, Pin.OUT, Pin.PULL_DOWN),
                        mosi = Pin(_SX127x_MOSI, Pin.OUT, Pin.PULL_UP),
                        miso = Pin(_SX127x_MISO, Pin.IN, Pin.PULL_UP))

        self._ss = Pin(_SX127x_SS, Pin.OUT)
        self._reset = Pin(_SX127x_RESET, Pin.OUT)
        self._dio_table = [ Pin(_SX127x_DIO0, Pin.IN), Pin(_SX127x_DIO1, Pin.IN), Pin(_SX127x_DIO2, Pin.IN) ]
        self._ping_count = 0
        self._power = None # not True nor False

        # Perform base class init
        super().init(_SX127x_WANTED_VERSION)

        # Set power state
        self.set_power()

    # Reset device
    def reset(self):
        self._reset.value(0)
        sleep(0.1)
        self._reset.value(1)

    # Read register from SPI port
    def read_register(self, address):
        return int.from_bytes(self._spi_transfer(address & 0x7F), 'big')

    # Write register to SPI port
    def write_register(self, address, value):
        self._spi_transfer(address | 0x80, value)

    def _spi_transfer(self, address, value = 0):
        response = bytearray(1)
        self._ss.value(0)
        self._spi.write(bytes([address]))
        self._spi.write_readinto(bytes([value]), response)
        self._ss.value(1)
        return response

    # Read block of data from SPI port
    def read_buffer(self, address, length):
        response = bytearray(length)
        self._ss.value(0)
        self._spi.write(bytes([address & 0x7F]))
        self._spi.readinto(response)
        self._ss.value(1)
        return response

    # Write block of data to SPI port
    def write_buffer(self, address, buffer, size):
        self._ss.value(0)
        self._spi.write(bytes([address | 0x80]))
        self._spi.write(memoryview(buffer)[0:size])
        self._ss.value(1)

    def attach_interrupt(self, dio, callback):
        if dio < 0 or dio >= len(self._dio_table):
            raise Exception("DIO %d out of range (0..%d)" % (dio, len(self._dio_table) - 1))

        self._dio_table[dio].irq(handler=callback, trigger=Pin.IRQ_RISING if callback else 0)

    def onReceive(self, packet, crc_ok, rssi):
        print("onReceive: crc_ok %s packet %s rssi %d" % (crc_ok, packet, rssi))
        if crc_ok:
            # Check addresses etc
            self._receive_queue.put({'rssi': rssi, 'data': packet })

    def receive_packet(self):
        return self._receive_queue.get()

    # Finished transmitting - see if we can transmit another
    # If we have another packet, return it to caller.
    def onTransmit(self):
        # Delete top packet in queue
        packet = self._transmit_queue.get(wait=0)
        del packet

        # Return head of queue.
        return self._transmit_queue.head()

    # Put packet into transmit queue.  If queue was empty, start transmitting
    def send_packet(self, packet):
        with self._meshlock:
            # print("Appending to queue: %s" % packet.decode())
            self._transmit_queue.put(packet)
            if len(self._transmit_queue) == 1:
                self.transmit_packet(packet)

    def close(self):
        print("MeshNet handler close called")
        # Close DIO interrupts
        for dio in self._dio_table:
            dio.irq(handler=None, trigger=0)

        super().close()
        if self._spi:
            self._spi.deinit()
            self._spi = None

        self.set_power(False)

    def set_power(self, power=True):
        # print("set_power %s" % power)

        if power != self._power:
            self._power = power

            # Call base class
            super().set_power(power)

    def __del__(self):
        self.close()


