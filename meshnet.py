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

class MeshNetException(Exception):
    pass


_PACKET_DEST                             = const(0)
_PACKET_DEST_LEN                         = const(2)
_PACKET_SOURCE                           = const(_PACKET_DEST + _PACKET_DEST_LEN)
_PACKET_SOURCE_LEN                       = const(2)
_PACKET_ID                               = const(_PACKET_SOURCE + _PACKET_SOURCE_LEN)
_PACKET_ID_LEN                           = const(1)
_PACKET_PAYLOAD                          = const(_PACKET_ID + _PACKET_ID_LEN)

_RANN_PACKET_TYPE                  = const(1)
_RANN_PACKET_FLAGS                       = const(_PACKET_PAYLOAD)
_RANN_PACKET_FLAGS_LEN                   = const(1)
_RANN_PACKET_FLAGS_PORTAL                     = const(0x01)
_RANN_PACKET_HOPCOUNT                    = const(_RANN_PACKET_FLAGS + _RANN_PACKET_FLAGS_LEN)
_RANN_PACKET_HOPCOUNT_LEN                = const(1)
_RANN_PACKET_TTL                         = const(_RANN_PACKET_HOPCOUNT + _RANN_PACKET_HOPCOUNT_LEN)
_RANN_PACKET_TTL_LEN                     = const(1)
_RANN_PACKET_ORIGINATOR                  = const(_RANN_PACKET_TTL + _RANN_PACKET_TTL_LEN)
_RANN_PACKET_ORIGINATOR_LEN              = const(2)
_RANN_PACKET_SEQUENCE                    = const(_RANN_PACKET_ORIGINATOR + _RANN_PACKET_ORIGINATOR_LEN)
_RANN_PACKET_SEQUENCE_LEN                = const(2)
_RANN_PACKET_LIFETIME                    = const(_RANN_PACKET_SEQUENCE + _RANN_PACKET_SEQUENCE_LEN)
_RANN_PACKET_LIFETIME_LEN                = const(2)
_RANN_PACKET_METRIC                      = const(_RANN_PACKET_LIFETIME + _RANN_PACKET_LIFETIME_LEN)
_RANN_PACKET_METRIC_LEN                  = const(2)
_RANN_PACKET_LEN                                = const(_RANN_PACKET_METRIC + _RANN_PACKET_METRIC_LEN)

_RREQ_PACKET_TYPE                  = const(2)
_RREQ_PACKET_FLAGS                       = const(_PACKET_PAYLOAD)
_RREQ_PACKET_FLAGS_LEN                   = const(1)
_RREQ_PACKET_FLAGS_PORTAL_BIT                 = const(0)
_RREQ_PACKET_FLAGS_BROADCAST_BIT              = const(1)
_RREQ_PACKET_FLAGS_RREP_BIT                   = const(2)
_RREQ_PACKET_HOPCOUNT                    = const(_RREQ_PACKET_FLAGS + _RREQ_PACKET_FLAGS_LEN)
_RREQ_PACKET_HOPCOUNT_LEN                = const(1)
_RREQ_PACKET_TTL                         = const(_RREQ_PACKET_HOPCOUNT + _RREQ_PACKET_HOPCOUNT_LEN)
_RREQ_PACKET_TTL_LEN                     = const(1)
_RREQ_PACKET_RREQ_ID                     = const(_RREQ_PACKET_TTL + _RREQ_PACKET_TTL_LEN)
_RREQ_PACKET_RREQ_ID_LEN                 = const(2)
_RREQ_PACKET_ORIGINATOR                  = const(_RREQ_PACKET_RREQ_ID + _RREQ_PACKET_RREQ_ID_LEN)
_RREQ_PACKET_ORIGINATOR_LEN              = const(2)
_RREQ_PACKET_ORIGINATOR_SEQ              = const(_RREQ_PACKET_ORIGINATOR + _RREQ_PACKET_ORIGINATOR_LEN)
_RREQ_PACKET_ORIGINATOR_SEQ_LEN          = const(2)
_RREQ_PACKET_LIFETIME                    = const(_RREQ_PACKET_ORIGINATOR_SEQ + _RREQ_PACKET_ORIGINATOR_SEQ_LEN)
_RREQ_PACKET_LIFETIME_LEN                = const(2)
_RREQ_PACKET_METRIC                      = const(_RREQ_PACKET_LIFETIME + _RREQ_PACKET_LIFETIME_LEN)
_RREQ_PACKET_METRIC_LEN                  = const(2)
_RREQ_PACKET_LEN                                = const(_RREQ_PACKET_METRIC + _RREQ_PACKET_METRIC_LEN)

# A table at end of RREQ.  position starts at 0 relative to RREQ_PACKET_LEN
_RREQ_PACKET_DESTINATION_FLAGS           = const(0)
_RREQ_PACKET_DESTINATION_FLAGS_DO_BIT         = const(0)
_RREQ_PACKET_DESTINATION_FLAGS_RF_BIT         = const(1)
_RREQ_PACKET_DESTINATION_ADDRESS         = const(_RREQ_PACKET_DESTINATION_FLAGS + _RREQ_PACKET_DESTINATION_FLAGS_LEN)
_RREQ_PACKET_DESTINATION_ADDRESS_LEN     = const(2)
_RREQ_PACKET_DESTINATION_SEQUENCE        = const(_RREQ_PACKET_DESTINATION_ADDRESS + _RREQ_PACKET_DESTINATION_ADDRESS_LEN)
_RREQ_PACKET_DESTINATION_SEQUENCE_LEN    = const(2)
_RREQ_PACKET_DESTINATION_LEN             = const(_RREQ_PACKET_DESTINATION_SEQUENCE + _RREQ_PACKET_DESTINATION_SEQUENCE_LEN)

_RREP_PACKET_TYPE                  = const(3)
_RREP_PACKET_MODE_FLAGS                  = const(_PACKET_PAYLOAD)
_RREP_PACKET_MODE_FLAGS_LEN              = const(1)
_RREP_PACKET_HOPCOUNT                    = const(_RREP_PACKET_MODE_FLAGS + _RREP_PACKET_MODE_FLAGS_LEN)
_RREP_PACKET_HOPCOUNT_LEN                = const(1)
_RREP_PACKET_TTL                         = const(_RREP_PACKET_HOPCOUNT + _RREP_PACKET_HOPCOUNT_LEN)
_RREP_PACKET_TTL_LEN                     = const(1)
_RREP_PACKET_DESTINATION                 = const(_RREP_PACKET_TTL + _RREP_PACKET_TTL_LEN)
_RREP_PACKET_DESTINATION_LEN             = const(2)
_RREP_PACKET_DESTINATION_SEQUENCE        = const(_RREP_PACKET_DESTINATION + _RREP_PACKET_DESTINATION_LEN)
_RREP_PACKET_DESTINATION_SEQUENCE_LEN    = const(2)
_RREP_PACKET_LIFETIME                    = const(_RREP_PACKET_DESTINATION_SEQUENCE + _RREP_PACKET_DESTINATION_SEQUENCE_LEN)
_RREP_PACKET_LIFETIME_LEN                = const(2)
_RREP_PACKET_METRIC                      = const(_RREP_PACKET_LIFETIME + _RREP_PACKET_LIFETIME_LEN)
_RREP_PACKET_METRIC_LEN                  = const(2)
_RREP_PACKET_SOURCE                      = const(_RREP_PACKET_METRIC + _RREP_PACKET_METRIC_LEN)
_RREP_PACKET_SOURCE_LEN                  = const(2)
_RREP_PACKET_SOURCE_SEQ                  = const(_RREP_PACKET_SOURCE + _RREP_PACKET_SOURCE_LEN)
_RREP_PACKET_SOURCE_SEQ_LEN              = const(2)
# This is the length of packet *without* ane dependent addr/dsn
_RREP_PACKET_LEN                         = const(_RREP_PACKET_SOURCE_SEQ + _RREP_PACKET_SOURCE_SEQ_LEN)
_RREP_PACKET_DEPENDENCIES                = const(_RREP_PACKET_LEN)

# A table at end of RREP.  position starts at 0 relative to RREP_PACKET_LEN
_RREP_DEPENDENCY_ADDRESS                 = const(0)
_RREP_DEPENDENCY_ADDRESS_LEN             = const(2)
_RREP_DEPENDENCY_SEQUENCE                = const(_RREP_DEPENDENCY_ADDRESS + _RREP_DEPENDENCY_ADDRESS_LEN)
_RREP_DEPENDENCY_SEQUENCE_LEN            = const(2)
_RREP_DEPENDENCY_LEN                     = const(_RREP_DEPENDENCY_SEQUENCE + _RREP_DEPENDENCY_SEQUENCE_LEN)


_RRER_PACKET_TYPE                  = const(4)
_RERR_PACKET_MODE_FLAGS                  = const(_PACKET_PAYLOAD)
_RERR_PACKET_MODE_FLAGS_LEN                     = const(1)
_RERR_PACKET_LEN                                = const(_RERR_PACKET_MODE_FLAGS + _RERR_PACKET_MODE_FLAGS_LEN)
_RERR_PACKET_DESTINATION                 = const(_RREP_PACKET_LEN)

# A destination error pair
_RERR_DESTINATION_ADDR                   = const(0)
_RERR_DESTINATION_ADDR_LEN               = const(2)
_RERR_DESTINATION_SEQUENCE               = const(_RERR_DESTINATION_ADDR + _RERR_DESTINATION_ADDR_LEN)
_RERR_DESTINATION_SEQUENCE_LEN           = const(2)
_RERR_DESTINATION_LEN                    = const(_RERR_DESTINATION_SEQUENCE + _RERR_DESTINATION_SEQUENCE_LEN)

# This level maintains handles the routing protocol
# and will deliver non-routing messages to the inheriter.
#
class MeshNet(SX127x_driver):

    # A group of data with field referencing
    class Fields():
        def __init__(self, data);
            self._data = data

        # Set or get a field of bytes, bigendian
        def _field(self, field, length, value=None):
            if value != None:
                for item in range(length - 1, -1, -1):
                    self._data[field + item] = value % 256
                    value >>= 8
            else:
                value = 0
                for item in range(length):
                    value = (value << 8) + self._data[field + item]
            return value

        # Used to set/clear/test bits in a field
        def _field_bit(self, field, length, bitnum=None, value=None)
            current = self._field(field, length)

            if value == None:
                # Testing a value
                current &= (1 << bitnum)

            else:
                if value:
                    current |= (1 << bitnum)
                else:
                    current &= ~(1 << bitnum)

                self._field(field, length, current)

            return current

        # Add 'len' bytes to record
        def _extend(self, len):
            self._data.extend(bytearray(len))


    # A Packet is the basic wrapper for a set of data to be sent or received from the wireless device.
    # This class only identifies the basic units of the data:
    #  
    # source()   Source address of the packet
    # dest()     Destination address of the packet
    # id()       Protocol id of packet
    #
    # A Packet is constructed by
    #         Packet(data=<data>) for incoming packets
    #         Packet(src=<source>, dest=<dest>, len=<length>) for outgoing packets
    #
    def Packet(Fields):
        def __init__(self, data=None, rssi=None, src=None, dest=None, id=<packet type>, len = None):
            super().__init__(data)

            if data == None and (len != None or src != None or dest != None or id != None):
                # Construct data if needed
                if len != None:
                    self._data = bytearray(len)

                    # Set fields if present
                    self.rssi(src)
                    self.source(src)
                    self.dest(dest)
                    self.id(id)

        def rssi(self, value=None):
            if value == None:
                return self._rssi
            else:
                self._rssi = rssi

        def dest(self, value = None):
            return self._field(PACKET_DEST, PACKET_DEST_LEN, value) 

        def source(self, value = None):
            return self._field(PACKET_SOURCE, PACKET_SOURCE_LEN, value)

        def id(self, value = None):
            return self._field(PACKET_ID, PACKET_ID_LEN, value)

        def data(self):
            return self._data

        def process(self, parent):
            # Default process causes error
            raise MeshNetException("Cannot process basic packet")

    class PacketRANN(Packet):
        def __init__(self, data, rssi=None)
            super().__init__(data, rssi)

        def portal(self, value = None):
            return self._field_bit(_RRAN_PACKET_FLAGS, _RRAN_PACKET_FLAGS_LEN, _RRAN_PACKET_FLAGS_PORTAL_BIT, value)

        def hopcount(self, value=None):
            return self._field(_RRAN_PACKET_HOPCOUNT, _RRAN_PACKET_HOPCOUNT_LEN, value)

        def ttl(self, value=None):
            return self._field(_RRAN_PACKET_TTL, _RRAN_PACKET_TTL_LEN, value)

        def originator(self, value=None):
            return self._field(_RRAN_PACKET_ORIGINATOR, _RRAN_PACKET_ORIGINATOR_LEN, value)

        def dest_sequence(self, value=None):
            return self._field(_RRAN_PACKET_SEQUENCE, _RRAN_PACKET_SEQUENCE_LEN, value)

        def lifetime(self, value=None):
            return self._field(_RRAN_PACKET_LIFETIME, _RRAN_PACKET_LIFETIME_LEN, value)

        def metric(self, value=None):
            return self._field(_RRAN_PACKET_METRIC, _RRAN_PACKET_METRIC_LEN, value)

        def process(self, parent):
            pass

    class RREQDestination(Fields):
        def __init__(self, data):
            super().__init__(data)

        def metric(self, value=None):
            return self._field(_RREQ_DESTINATION_METRIC, _RREQ_DESTINATION_METRIC_LEN, value)

        def do(self, value=None):
            return self._field_bit(_RREQ_DESTINATION_FLAGS, _RREQ_DESTINATION_FLAGS_LEN, _RREQ_DESTINATION_FLAGS_DO_BIT, value)

        def rf(self, value=None):
            return self._field_bit(_RREQ_DESTINATION_FLAGS, _RREQ_DESTINATION_FLAGS_LEN, _RREQ_DESTINATION_FLAGS_RF_BIT, value)

        def address(self, value=None):
            return self._field(_RREQ_DESTINATION_ADDRESS, _RREQ_DESTINATION_ADDRESS_LEN, value)

        def sequence(self):
            return self._field(_RREQ_DESTINATION_SEQUENCE, _RREQ_DESTINATION_SEQUENCE_LEN, value)

        def process(self, parent):
            pass

    # Route request
    class PacketRREQ(Packet):
        def __init__(self, data)
            super().__init__(data)

        def portal(self, value = None):
            return self._field_bit(_RREQ_PACKET_FLAGS, _RREQ_PACKET_FLAGS_LEN, _RREQ_PACKET_FLAGS_PORTAL_BIT, value)

        def broadcast(self, value = None):
            return self._field_bit(_RREQ_PACKET_FLAGS, _RREQ_PACKET_FLAGS_LEN, _RREQ_PACKET_FLAGS_BROADCAST_BIT, value)

        def rrep(self, value = None):
            return self._field_bit(_RREQ_PACKET_FLAGS, _RREQ_PACKET_FLAGS_LEN, _RREQ_PACKET_FLAGS_RREP_BIT, value)

        def hopcount(self, value=None):
            return self._field(_RREQ_PACKET_HOPCOUNT, _RREQ_PACKET_HOPCOUNT_LEN, value)

        def ttl(self, value=None):
            return self._field(_RREQ_PACKET_TTL, _RREQ_PACKET_TTL_LEN, value)

        def rreq_id(self, value=None):
            return self._field(_RREQ_PACKET_RREQ_ID, _RREQ_PACKET_RREQ_ID_LEN, value)

        def originator(self, value=None):
            return self._field(_RREQ_PACKET_ORIGINATOR, _RREQ_PACKET_ORIGINIATOR_LEN, value)

        def sequence(self, value=None):
            return self._field(_RREQ_PACKET_SEQUENCE, _RREQ_PACKET_SEQUENCE_LEN, value)

        def lifetime(self, value=None):
            return self._field(_RREQ_PACKET_LIFETIME, _RREQ_PACKET_LIFETIME_LEN, value)

        def dest_count(self):
            return (len(self._data) - _RREQ_PACKET_LENGTH) / _RREQ_DESTINATION_VALUE_LENGTH

        def destination(self, index, value=None):
            if value == None and index > self.dest_count():
                raise MeshNetException("RREQ destination out of range")

            if value == None:
                return RREQDestination(self._data[dest_index:dest_index + _RREQ_PACKET_DESTINATION_LENGTH])

            else:
                dest_index = _RREQ_PACKET_DESTINATIONS + index * _RREQ_PACKET_DESTINATION_LENGTH

                if type(value) == RREQDestination:
                    # Copy info into this destination
                    self._data[dest_index:dest_index + _RREQ_PACKET_DESTINATION_LEN] = value.data()
                else:
                    # Copy as byte array
                    self._data[dest_index:dest_index + _RREQ_PACKET_DESTINATION_LEN] = data

                return (dest_index - _RREQ_PACKET_DESTINATIONS) / _RREQ_PACKET_DESTINATION_LENGTH

        # Return destination slot number
        def add_destination(self, dest):
            insert_at = len(self._data)
            self._extend(_RREQ_PACKET_DESTINATION_LEN)
            return self.destination(insert_at, dest)

        def process(self, parent):
            pass

    class RREPDependent(Fields):
        def __init__(self, data):
            super().__init__(data)

        def address(self, value=None):
            return self._field(_RREP_DESTINATION_ADDRESS, _RREP_DESTINATION_ADDRESS_LEN, value)

        def sequence(self):
            return self._field(_RREP_DESTINATION_SEQUENCE, _RREP_DESTINATION_SEQUENCE_LEN, value)

    # Route request
    class PacketRREP(Packet):
        def __init__(self, data)
            super().__init__(data)

        def hopcount(self, value=None):
            return self._field(_RREP_PACKET_HOPCOUNT, _RREP_PACKET_HOPCOUNT_LEN, value)

        def ttl(self, value=None):
            return self._field(_RREP_PACKET_TTL, _RREP_PACKET_TTL_LEN, value)

        def destination(self, value=None):
            return self._field(_RREP_PACKET_DESTINATION, _RREP_PACKET_DESTINATION_LEN, value)

        def destination_sequence(self, value=None):
            return self._field(_RREP_PACKET_DESTINATION_SEQUENCE, _RREP_PACKET_DESTINATION_SEQUENCE_LEN, value)

        def lifetime(self, value=None):
            return self._field(_RREP_PACKET_LIFETIME, _RREP_PACKET_LIFETIME_LEN, value)

        def metric(self, value=None):
            return self._field(_RREP_PACKET_METRIC, _RREP_PACKET_METRIC_LEN, value)

        def source(self, value=None):
            return self._field(_RREP_PACKET_SOURCE, _RREP_PACKET_SOURCE_LEN, value)

        def source_sequence(self, value=None):
            return self._field(_RREP_PACKET_SOURCE_SEQUENCE, _RREP_PACKET_SOURCE_SEQUENCELEN, value)

        def dep_count(self):
            return (len(self._data) - _RREP_PACKET_LENGTH) / _RREP_DESTINATION_VALUE_LENGTH

        def depencency(self, index, value=None):
            if value == None and index > self.dep_count():
                raise MeshNetException("RREP dependency out of range")

            if value == None:
                return RREPDependency(self._data[dest_index:dest_index + _RREP_DEPENDENCY_LEN])

            else:
                dep_index = _RREP_PACKET_DEPENDENCIES + index * _RREP_DEPENDENCY_LEN

                if type(value) == RREPDependency:
                    # Copy info into this destination
                    self._data[dest_index:dest_index + _RREP_DEPENDENCY_LEN] = value.data()

                else:
                    # Copy as byte array
                    self._data[dest_index:dest_index + _RREP_DEPENDENCY_LEN] = data

                return (dest_index - _RREP_PACKET_DEPENDENCIES) / _RREP_DEPENDENCY_LEN

        # Return destination slot number
        def add_dependency(self, dep):
            insert_at = len(self._data)
            self._extend(_RREP_DEPENDENC_LEN)
            return self.destination(insert_at, dest)

    class RERRDestination(Fields):
        def __init__(self, data):
            super().__init__(data)

        def address(self, value=None):
            return self._field(_RERR_DESTINATION_ADDRESS, _RERR_DESTINATION_ADDRESS_LEN, value)

        def sequence(self):
            return self._field(_RERR_DESTINATION_SEQUENCE, _RERR_DESTINATION_SEQUENCE_LEN, value)

    # Route request
    class PacketRERR(Packet):
        def __init__(self, data)
            super().__init__(data)

        def destination(self, index, value=None):
            if value == None and index > self.dep_count():
                raise MeshNetException("RERR destination index out of range")

            if value == None:
                return RERRDestination(self._data[dest_index:dest_index + _RERR_DESTINATION_LEN])

            else:
                dep_index = _RERR_PACKET_DESTINATIONS + index * _RERR_DESTINATION_LEN

                if type(value) == RERRDestination:
                    # Copy info into this destination
                    self._data[dest_index:dest_index + _RERR_DESTINATION_LEN] = value.data()

                else:
                    # Copy as byte array
                    self._data[dest_index:dest_index + _RERR_DESTINATION_LEN] = data

                return (dest_index - _RERR_PACKET_DESTINATIONS) / _RERR_DESTINATION_LEN

        # Return destination slot number
        def add_destination(self, dep):
            insert_at = len(self._data)
            self._extend(_RERR_DESTINATION_LEN)
            return self.destination(insert_at, dest)

        def process(self, parent):
            pass


    def __init__(self, domain, **kwargs):
        SX127x_driver.__init__(self, domain, **kwargs)

        self._meshlock = rlock()
        self._transmit_queue = queue()
        self._receive_queue = queue()

        self._PACKET_TYPES = {
                _PACKET_TYPE_RANN: PacketRANN,
                _PACKET_TYPE_RREQ: PacketRREQ,
                _PACKET_TYPE_RREP: PacketRREP,
                _PACKET_TYPE_RERR: PacketRERR,
        }

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

    # Enwrap the packet with a class object for the particular message type
    def create_packet(self, data, rssi):
        return self.PACKET_TYPES[data[_PACKET_ID]](data=data, rssi=rssi) if packet[_PACKET_ID] in self.PACKET_TYPES else self.Packet(data=packet, rssi=rssi)

    def onReceive(self, packet, crc_ok, rssi):
        packet = self.create_packet(packet, rssi)

        print("onReceive: crc_ok %s packet %s rssi %d" % (crc_ok, packet, rssi))
        if crc_ok:
            # Check addresses etc

            packet.process(self)

            # self._receive_queue.put({'rssi': rssi, 'data': packet })

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

