#
# MeshNet driver
#


#
# Mesh driver for network.
#
# The meshing driver for the network utilizes several packets for delivery of data through the ad-hoc network.
#   PathRequest  - Request a path from node A to node B resolving path through network
#   PathReply    - Reply to a path request with a specific route from A to B
#   PathError    - Report an unsuccessful route from path A to B
#   PathAnnounce - Announce a root-based path to node A
#   DataPacket   - A data packet that will be routed from node A to B via intermediate nodes.
#
# All packets contain a header with the following information:
#   from              - address of node sending the packet
#   source            - address of node that created the initial packet
#   to                - address of node that should receive the packet
#   dest              - address of destination node for the packet
#   ttl               - time to live.  A counter that decrements upon every retransmission
#   protocol          - identifies protocol of payload (Data, PathRequest, etc.)
#
# When a node creates a new packet, the node will be labeled:
#   from              - address of node sending the packet
#   source            - address of node sending the packet
#   to                - address of destination (or BROADCAST)
#   dest              - address of target recipient
#   ttl               - default max value
#
# When a node rebroadcasts a packet:
#   from              - address of node sending packet
#   source            - original source
#   to                - address of next node in hop or broadcast
#   dest              - original destination
#   ttl               - original ttl decreased by one
#    
# When a node desires to send a packet to a node for which it does not have a route,
# it creates a PathRequest with the following information
#   from              - address of node sending packet
#   source            - address of node sending packet
#   to                - broadcast
#   dest              - address of unknown destination node
#   ttl               - default max value
#   metric            - set to 1
#   sequence          - number created by source (defines this specific route request)
#
# When a node receives a PathRequest:
#   If the node does not have a route to the source then
#     Create a route to <source> with the following information
#        route[header.source] =
#           sequence = payload.sequence
#           to       = header.from
#           metric   = payload.metric
#
#   else if the payload.metric is less than than route.metric or payload.sequence != route.sequence:
#       route.sequence = payload.sequence
#       route.metric   = payload.metric
#       route.to       = header.from
#
#   if address of node is same as header.destination, generate PathReply with:
#       header.from         - our node address
#       header.source       - our node address
#       header.to           - route.to
#       header.destination  - header.source
#       payload.sequence    - generated new sequence number
#       payload.metric      - route.metric
#   else if header.ttl != 0:
#       header.from      - current address
#       payload.sequence - from pathrequest payload
#       payload.metric   - from payload metric + 1
#       header.ttl       - header.ttl - 1
#       <rebroadcast node>
#
#   if we receive PathReply matching route[header.source].sequence == payload.sequence and a better metric:
#       route[header.source] =
#           metric = payload.metric
#           to     = header.from
#

from time import sleep
from ulock import *
from uqueue import *
from sx127x import SX127x_driver as RadioDriver
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


_STREAM_NUMBER_LEN                = const(1)
_STREAM_SEQUENCE_LEN              = const(1)
_TTL_DEFAULT                      = const(64)
_BROADCAST_ADDRESS                = const(0xFFFF)
_MAX_HOPCOUNT                     = const(64)
_PROTOCOL_LEN                     = const(1)
_MAX_ROUTES                       = const(64)
_FLAGS_LEN                        = const(1)
_STREAM_NUMBER_LEN                = const(1)
_ADDRESS_LEN                      = const(2)
_SEQUENCE_NUMBER_LEN              = const(2)
_DISCOVERY_ID_LEN                 = const(2)
_TIMESTAMP_LEN                    = const(2)
_METRIC_LEN                       = const(1)
_HOPCOUNT_LEN                     = const(1)
_TTL_LEN                          = const(1)
_BEACON_NAME_LEN                  = const(16)
_REASON_LEN                       = const(1)

def create_field(len, origin=0):
    if type(origin) == int:
        return (origin, len)
    elif type(origin) == tuple:
        return (origin[0] + origin[1], len)
    else:`
        raise MeshNetException("Invalid type for 'origin'"

def end_field(field):
    return field[0] + field[1]

#
# All packets have a header containing:
#  to          - intended recipient or BROADCAST
#  destination - final recipient of packet
#  from        - sender of the packet
#  source      - originator of packet
#  protocol    - protocol id of this packet
#  ttl         - total hops before it expires
#  
_HEADER_TO                  = create_field(_ADDRESS_LEN)
_HEADER_DESTINATION         = create_field(_ADDRESS_LEN, _HEADER_TO)
_HEADER_FROM                = create_field(_ADDRESS_LEN, _HEADER_DESTINATION)
_HEADER_SOURCE              = create_field(_ADDRESS_LEN, _HEADER_FROM)
_HEADER_PROTOCOL            = create_field(_PROTOCOL_LEN, _HEADER_SOURCE)
_HEADER_TTL                 = create_field(_TTL_LEN, _HEADER_PROTOCOL)
_HEADER_LENGTH              = end_field(_HEADER_TTL)
_HEADER_PAYLOAD             = const(_HEADER_LENGTH)


#########################################################################
# Beacon packet
#########################################################################
_BEACON_PROTOCOL            = const(0)
_BEACON_NAME                = create_field(_BEACON_NAME_LEN)
_BEACON_ADDRESS             = create_field(_ADDRESS_LEN, _BEACON_NAME)
_BEACON_LENGTH              = end_field(_BEACON_ADDRESS)

#########################################################################
# Data packet.
#########################################################################
_DATA_PROTOCOL              = const(1)
_DATA_STREAM                = create_field(_STREAM_NUMBER_LEN)
_DATA_SEQUENCE              = create_field(_STREAM_SEQUENCE_LEN, _DATA_STREAM)
_DATA_WINDOW                = create_field(_STREAM_SEQUENCE_LEN, _DATA_SEQUENCE)
_DATA_LENGTH                = end_field(_DATA_WINDOW)

#########################################################################
# Path announce
#########################################################################
_PANN_PROTOCOL              = const(2)
_PANN_FLAGS                 = create_field(_FLAGS_LEN)
_PANN_FLAGS_GATEWAY             = const(0)
_PANN_INTERVAL              = create_field(_INTERVAL_LEN, _PANN_FLAGS)
_PANN_ADDRESS               = create_field(_ADDRESS_LEN, _PANN_ADDRESS)
_PANN_METRIC                = create_field(_METRIC_LEN, _PANN_ADDRESS)
_PANN_LENGTH                = end_field(_PANN_METRIC)

#########################################################################
# Path Request
#########################################################################
_PREQ_PROTOCOL              = const(3)
_PREQ_FLAGS                 = create_field(_FLAGS_LEN)
_PREQ_FLAGS_GATEWAY             = const(0)
_PREQ_SEQUENCE              = create_field(_SEQUENCE_NUMBER_LEN, _PREQ_FLAGS)
_PREQ_METRIC                = create_field(_METRIC_LEN, _PREQ_SEQUENCE)
_PREQ_LENGTH                = end_field(_PREQ_METRIC)

#########################################################################
# Path Report
#########################################################################
_PREP_PROTOCOL              = const(4)
_PREP_FLAGS                 = create_field(_FLAGS_LEN)
_PREP_FLAGS_GATEWAY             = const(0)
_PREP_SEQUENCE              = create_field(_SEQUENCE_NUMBER_LEN, _PREP_FLAGS)
_PREP_METRIC                = create_field(_METRIC_LEN, _PREP_SEQUENCE)
_PREP_LENGTH                = end_field(_PREP_METRIC)

#########################################################################
# Path Error
#########################################################################
_PERR_PROTOCOL              = const(5)
_PERR_ADDRESS               = create_field(_ADDRESS_LEN)
_PERR_SEQUENCE              = create_field(_SEQUENCE_NUMBER_LEN, _PERR_ADDRESS)
_PERR_REASON                = create_field(_REASON_LEN, _PERR_SEQUENCE)
_PERR_LENGTH                = end_field(_PERR_REASON)

#########################################################################
# This level maintains handles the routing protocol
# and will deliver non-routing messages to the inheriter.
#########################################################################
class MeshNet(RadioDriver):

    # A group of data with field referencing
    class FieldRef(object):
        def __init__(self, **kwargs);
            self._data = kwargs['data'] if 'data' in kwargs else None

            # Create empty field if undefined and there is a 'len' member
            if self._data == None and 'len' in kwargs:
                self._data = bytearray(kwargs['len'])

        def data(self):
            return self._data

        def __len__(self):
            return len(self._data)

        def __str__(self):
            return "FieldRef(%d)" % len(self))

        # Set or get a field of bytes, bigendian
        # <field> is ( <origin>, <length> )
        def _field(self, field, value=None):
            if type(value) == int:
                v = value
                for item in range(field[1] - 1, -1, -1):
                    self._data[field[0] + item] = v % 256
                    v >>= 8

            elif type(value) == str or type(value) == bytearray:
                # Convert string to bytes
                v = bytearray(value)

                # Extend to width of destination field
                if len(v) < field[1]:
                    v.extend((0,) * (field[1] - len(value)))

                # Move string to limited field
                self._data[field[0]:field[0]+field[1]] = v[:field[1]]

            # Value is None, so fetch value from table
            elif value == None:
                value = 0
                for item in range(field[1]):
                    value = (value << 8) + self._data[field[0] + item]

            return value

        # Used to set/clear/test bits in a field
        def _field_bit(self, field, bitnum=None, value=None)
            current = self._field(field)

            if value == None:
                # Testing a value
                current &= (1 << bitnum)

            else:
                if value:
                    current |= (1 << bitnum)
                else:
                    current &= ~(1 << bitnum)

                self._field(field, current)

            return current

        # Add 'len' bytes to record
        def _extend(self, len):
            self._data.extend(bytearray(len))


    # A Packet is the basic wrapper for a set of data to be sent or received from the wireless device.
    # This class only identifies the basic units of the data:
    #  
    # source()   Source address of the packet
    # dest()     Destination address of the packet
    # protocol() Protocol id of packet (Route Request, Route Announce, Data, etc.)
    #
    # A Packet is constructed by
    #         Packet(data=<data>) for incoming packets
    #         Packet(src=<source>, dest=<dest>, len=<length>) for outgoing packets
    #
    def Packet(FieldRef):

        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            # Set fields if present
            self.to         (kwargs['to']       if 'to'       in kwargs else _BROADCAST_ADDRESS)
            self.from       (kwargs['from']     if 'from'     in kwargs else self.address)
            self.source     (kwargs['source']   if 'source'   in kwargs else self.from())
            self.destination(kwargs['dest']     if 'dest'     in kwargs else None)
            self.ttl        (kwargs['ttl']      if 'ttl'      in kwargs else _TTL_DEFAULT)
            self.protocol   (kwargs['protocol'] if 'protocol' in kwargs else None)

            self.rssi(kwargs['rssi'] if 'rssi' in kwargs else None)

        def __str__(self):
            return "Packet: S%d D%d F%d T%d TTL%d P%d" % (self.source(), self.destination(), self.from(), self.to(), self.ttl(), self.protocol())

        def rssi(self, value=None):
            if value == None:
                return self._rssi
            else:
                self._rssi = rssi

        def to(self, value=None):
            return self._field(_HEADER_TO, value) 

        def from(self, value=None):
            return self._field(_HEADER_FROM, value)

        def dest(self, value=None):
            return self._field(_HEADER_DESTINATION, value) 

        def source(self, value=None):
            return self._field(_HEADER_SOURCE, value)

        def ttl(self, value=None):
            return self._field(_HEADER_TTL, value)

        def protocol(self, value=None):
            return self._field(_HEADER_PROTOCOL, value)

        def process(self, parent):
            # Default process causes error
            raise MeshNetException("Cannot process basic packet")

    class PathAnnounce(Packet):
        def __init__(self, **kwargs):
            kwargs['len'] = _PANN_LENGTH
            kwargs['protocol'] = _PAAN_PROTOCOL
            super(PathAnnounce, self).__init__(**kwargs)

            self.gateway_flag(kwargs['gw'] if 'gw' in kwargs else False)
            self.address(kwargs['address'] if 'address' in kwargs else self.address)
            self.interval(kwargs['interval'] if 'interval' in kwargs else _INTERVAL_DEFAULT)
            self.metric(kwargs['metric'] if 'metric' in kwargs else 1)

        def __str__(self):
            return "PathAnnounce: S%d D%d F%d T%d TTL%d P%d" % (self.source(), self.destination(), self.from(), self.to(), self.ttl(), self.protocol())

        def gateway_flag(self, value=None):
            return self._field_bit(_PANN_FLAGS, _PANN_FLAGS_GATEWAY, value)

        def address(self, value=None):
            return self._field(_PANN_MAC_ADDRESS, value)

        def interval(self, value=None):
            return self._field(_PANN_INTERVAL, value)

        def metric(self, value=None):
            return self._field(_PANN_METRIC, value)

        #
        # Processing a PathAnnounce:
        #   1) Create a route as usual with gw flag set
        def process(self, parent):
            route = parent._define_route(self)
            # PathAnnounce will create a route to the specific node.


    # Route request
    class PathRequest(Packet):
        def __init__(self, **kwargs):
            kwargs['len'] = _PREQ_LENGTH
            kwargs['protocol'] = _PREQ_PROTOCOL
            super(PathRequest, self).__init__(**kwargs)

            self.gateway_flag(kwargs['gw'] if 'gw' in kwargs else False)
            self.sequence(kwargs['sequence'] if 'sequence' in kwargs else None)
            self.metric(kwargs['metric'] if 'metric' in kwargs else 1)

        def __str__(self):
            return "PathRequest: S%d D%d F%d T%d TTL%d Seq%d M%d" % (self.source(), self.destination(), self.from(), self.to(), self.ttl(), self.sequence(), self.metric())

        def gateway_flag(self, value=None):
            return self._field_bit(_PREQ_FLAGS, _PREQ_FLAGS_GATEWAY, value)

        def sequence(self, value=None)):
            return self._field(_PREQ_SEQUENCE, value)

        def metric(self, value=None):
            return self._field(_PREQ_METRIC, value)

        # Process in incoming RREQ
        # TODO: Need brakes to avoid transmitting too many at once !!
        def process(self, parent):
            with self._packet_lock:
                source = self.source()

                # Ignore packets that we created
                if source != self.address:
                    # Get or create a route to the source of the packet
                    route = self._define_route(self)
                    if self.sequence() != route.sequence() or self.metric() < route.metric():
                        route.update(packet)

                    if self.destination() == self.address:
                        # For us - generate a reply
                        parent.send_packet(PathReply(source=self.address, dest=packet.source(), sequence=route.sequence, metric=route.metric))

                    elif packet.ttl() != 0:
                        # retransmit the packet if ttl is still non-zero
                        packet.metric(packet.metric() + 1)
                        packet.ttl(packet.ttl() - 1)
                        self.send_packet(packet)

    # Route request
    class PathReply(Packet):
        def __init__(self, **kwargs):
            kwargs['len'] = _PREP_LENGTH
            kwargs['protocol'] = _PREP_PROTOCOL
            super(PathReply, self).__init__(**kwargs)

            self.sequence(kwargs['sequence'] if 'sequence' in kwargs else 0)
            self.metric(kwargs['metric'] if 'metric' in kwargs else 0)

        def __str__(self):
            return "PathReply: S%d D%d F%d T%d TTL%d Seq%d M%d" % (self.source(), self.destination(), self.from(), self.to(), self.ttl(), self.sequence(), self.metric())

        def gateway_flag(self, value):
            return self._field_bit(_PREP_FLAGS, _PREP_FLAGS_GATEWAY, value)

        def sequence(self):
            return self._field(_PREP_SEQUENCE, value)

        def metric(self, value=None):
            return self._field(_PREP_METRIC, value)

        def process(self, parent):
            # Only process if directly to us
            if self.destination() == self.address:
                route = self._define_route(self)

                # Move all pending packets to the transmit queue
                working = True
                while working:
                    packet = route.get_pending_packet()
                    if packet:
                        self.send_packet(packet)
                    else:
                        working = False

    # Path error
    class PathError(Packet):
        def __init__(self, **kwargs):
            kwargs['len'] = _PERR_LENGTH
            super(PathError, self).__init__(**kwargs)

            self.address(kwargs['address'] if 'address' in kwargs else 0)
            self.sequence(kwargs['sequence'] if 'sequence' in kwargs else 0)
            self.reason(kwargs['reason'] if 'reason' in kwargs else 0)

        def __str__(self):
            return "PathError: S%d D%d F%d T%d TTL%d A%d Seq%d R%d" % (self.source(), self.destination(), self.from(), self.to(), self.ttl(), self.address(), self.sequence(), self.readon())

        def address(self, value=None):
            return self._field(_PERR_ADDRESS, value)

        def sequence(self, value=None):
            return self._field(_PERR_SEQUENCE, value)

        def reason(self, value=None):
            return self._field(_PERR_REASON, value)

        def process(self, parent):
            pass


    class DataPacket(Packet):
        def __init__(self, **kwargs):
            kwargs['deflen'] = _DATA_LENGTH
            kwargs['protocol'] = _DATA_PROTOCOL
            super(DataPacket, self).__init__(**kwargs)

            self.stream(kwargs['stream'] if 'stream' in kwargs else 0)
            self.sequence(kwargs['sequence'] if 'sequence' in kwargs else 0)
            self.window(kwargs['window'] if 'window' in kwargs else 0)

            if 'payload' in kwargs:
                self._data[_DATA_LENGTH:] = kwargs['payload']

        def __str__(self):
            return "Data: S%d D%d F%d T%d TTL%d Str%d Seq%d W%d Len%d" % (self.source(), self.destination(), self.from(), self.to(), self.ttl(), self.stream(), self.sequence(), self.window())

        def stream(self, value=None):
            return self._field(_DATA_STREAM, value)

        def sequence(self, value=None):
            return self._field(_DATA_SEQUENCE, value)

        def window(self, value=None):
            return self._field(_DATA_WINDOW, value)

        # Return the payload portion of the data
        def payload(self):
            return self._data[_DATA_LENGTH:]

    class Route():
        def __init__(self, packet=None, **kwargs):
            self.lifetime = time() + _ROUTE_LIFETIME
            self._transmit_queue = queue()

            if type(packet) = PathReply or type(packet) == PathAnnounce:
                self.update(reply)

            else:
                self.update(**kwargs)

        def put_pending_packet(self, packet):
            self._transmit_queue.put(packet)

        def get_pending_packet(self):
            return self._transmit_queue.get(wait=0)

        def update(self, packet=None, **kwargs):
            self._lifetime = time() + _ROUTE_LIFETIME

            if type(packet) == PathReply or type(packet) == PathAnnounce:
                self._sequence = packet.sequence()
                self._metric   = packet.metric()
                self._to       = packet.from()
                self._gateway  = packet.gateway_flags()
                self._announce = packet.interval() if type(packet) == PathAnnounce else None

            else:
                if 'sequence' in kwargs:
                    self._sequence = kwargs['sequence']
                if 'metric' in kwargs:
                    self._metric = kwargs['metric']
                if 'to' in kwargs:
                    self._to = kwargs['to']
                if 'gw' in kwargs:
                    self._gateway = kwargs['gw']
                if 'announce' in kwargs:
                    self._announce = kwargs['announce']

            else:
                raise MeshNetException("Route update failed")

        def is_expired(self):
            return time() >= self._lifetime

        def sequence(self, value=None):
            if value == None:
                return self._sequence
            else:
                self._sequence = value

        def metric(self, value=None):
            if value == None:
                return self._metric
            else:
                self._metric = Value

        def to(self, value=None):
            if value == None:
                return self._to
            else:
                self._to = value

        def is_gateway(self, value=None):
            if value == None:
                return self._gateway
            else:
                self._gateway = value

    def __init__(self, domain, address, **kwargs):
        SX127x_driver.__init__(self, domain, **kwargs)

        self.address = address
        self._meshlock = rlock()
        self._transmit_queue = queue()
        self._receive_queue = queue()
        self._routes = {}
        self._packets_errors_crc = 0
        self._packets_processed = 0
        self._packets_ignored = 0

        self._PROTOCOLS = {
                _PANN_PROTOCOL: PathAnnounce,
                _PREQ_PROTOCOL: PathRequest,
                _PREP_PROTOCOL: PathReply,
                _PERR_PROTOCOL: PathError,
                _DATA_PROTOCOL: DataPacket,
        }

    def announce_path_start(self, interval):
        self._announce_thread = thread(run=self._announce)
        self._announce_thread.start()

    def announce_path_stop(self):
        rc = None

        if self._announce_thread:
            self._announce_thread.stop()
            rc = self._announce_thread.wait()
            self._announce_thread = None

        return rc

    def _announce(self, t, interval):
        while t.running:
            sleep(interval)
            packet = PathAnnounce(gw=True, address=self.address, interval=interval)
            self.send_packet(packet)
        return 0

    def get_protocol_wrapper(self, protocol):
        if protocol in self._PROTOCOLS:
            return self._PROTOCOLS[protocol]
        else
            return None

    def _define_route(self, packet):
        address = packet.source()

        if address in self._routes:
            route = self._routes[address]
            # If root has expired, just renew it
            if route.is_expired():
                route.update(packet)
        else:
            # If we are at max  routes, try to delete all expired roots
            if len(self._routes) >= _MAX_ROUTES:
                # Sort routes in lifetime order
                routes = sorted(self._routes.item(), key=lambda(key, val): val.lifetime())

                # Delete all expired routes
                while routes[0].is_expired():
                    del(self.routes[routes[0]])
                    del(routes[0])

                # If this didn't make any room, just delete the oldest route
                if len(self._routes) >= _MAX_ROUTES:
                    del(self.routes[routes[0]])

                del(routes)

            route = Route(packet)
            self._routes[address] = route

        return route

    def _find_route(address):
        return self._routes[address] if address in self._routes else None

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

    def _spi_transfer(self, address, value=0):
        response = bytearray(1)
        self._ss.value(0)
        self._spi.write(bytes([address]))
        self._spi.write_readinto(bytes([value]), response)
        self._ss.value(1)
        return response

    # Read block of data from SPI port
    def read_buffer(self, address, length):
        try:
            response = bytearray(length)
            self._ss.value(0)
            self._spi.write(bytes([address & 0x7F]))
            self._spi.readinto(response)
            self._ss.value(1)

        except:
            # No room.  gc now
            gc.collect()
            response = None

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
    def wrap_packet(self, data, rssi=None):
        wrapper = self.get_protocol_wrapper(data[_HEADER_PROTOCOL])
        if wrapper:
            # Wrap it with the protocol structure specific to the type
            return wrapper(data=data, rssi=rssi)
        else:
            # Wrap it with generic data wrapper
            return self.Packet(data=data, rssi=rssi)
        
    # Duplicate packet with new private data
    def dup_packet(self, packet):
        return wrap_packet(bytearray(packet.data()), packet.rssi)

    def create_packet(self, source, dest, protocol, data):
        data = bytearray(_HEADER_LENGTH) + bytearray(data)
        data[_HEADER_PROTOCOL] = protocol
        packet = self.wrap_packet(data)
        packet.source(source)
        packet.dest(dest)
        return packet

    def onReceive(self, packet, crc_ok, rssi):
        if crc_ok:
            packet = self.wrap_packet(packet, rssi)

            to = packet.to()

            print("onReceive: packet %s" % (str(packet)))
            if to == _BROADCAST_ADDRESS or to == self.address:
                self._packets_processed += 1
                # To us or broadcasted
                packet.process(self):

            else:
                self._packets_ignored += 1
        else:
            self._packets_error_crc += 1


    def receive_packet(self):
        return self._receive_queue.get()

    # Finished transmitting - see if we can transmit another
    # If we have another packet, return it to caller.
    def onTransmit(self):
        # Delete top packet in queue
        packet = self._transmit_queue.get(wait=0)
        del packet

        # Return head of queue if one exists
        packet = self._transmit_queue.head()

        gc.collect()

        return head.data() if head else None

    # A packet with a source and destination is ready to transmit.
    # Label the from address and if no to address, attempt to route
    def send_packet(self, packet):
        # Label packets as coming from us
        packet.from(self.address)

        # If no direct recipient has been defined, we go through routing table
        if packet.to() == None:
            # Look up the path to the destination
            route = self._find_route(packet.destination())

            # If no path, create a dummy path and queue the results
            if route == None:
                # Unknown route.  Create a NULL route awaiting PathReply
                route = self._define_route(packet.destination())
                request = PathRequest(dest=route.desination())

            elif route.to() == None:
                # We have a pending route, so append packet to queue only.
                request = None
                route.put_pending_packet(packet)

            else:
                # Label the destination for the packet
                packet.to(route.to())
                request = packet

            # Transmit the request if we created one or else the actual packet
            packet = request

        if packet:
            with self._meshlock:
                # print("Appending to queue: %s" % packet.decode())
                self._transmit_queue.put(packet)
                if len(self._transmit_queue) == 1:
                    self.transmit_packet(packet.data())

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

