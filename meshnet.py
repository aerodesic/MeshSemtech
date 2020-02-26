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
#   if the node address is same as header.destination, generate PathReply with:
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
#   if we receive PathReply matching route[header.source].sequence == payload.sequence and a improved metric:
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

# Default values for some entries
_BROADCAST_ADDRESS                = const(0xFFFF)
_ROUTE_LIFETIME                   = 15.0
_MAX_ROUTES                       = const(64)
_TTL_DEFAULT                      = const(64)

# Lengths of various fields in packets
_STREAM_NUMBER_LEN                = const(1)
_STREAM_SEQUENCE_LEN              = const(1)
_PROTOCOL_LEN                     = const(1)
_FLAGS_LEN                        = const(1)
_STREAM_NUMBER_LEN                = const(1)
_ADDRESS_LEN                      = const(2)   # May need to increase to 6 for 'MAC address' compatibility
_SEQUENCE_NUMBER_LEN              = const(2)
_METRIC_LEN                       = const(1)
_TTL_LEN                          = const(1)
_BEACON_NAME_LEN                  = const(16)
_REASON_LEN                       = const(1)

# Helper functions used to build packet field items
def create_field(len, origin=0):
    if type(origin) == int:
        return (origin, len)
    elif type(origin) == tuple:
        return (origin[0] + origin[1], len)
    else:`
        raise MeshNetException("Invalid type for 'origin'"

def end_field(field):
    return field[0] + field[1]


#########################################################################
# Supporting classes
#########################################################################
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
    def _field(self, field, value=None, return_type=int):
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
            if return_type == int:
                value = 0
                for item in range(field[1]):
                    value = (value << 8) + self._data[field[0] + item]
            else:
                return self._data[field[0]:field[0]+field[1]]

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
#         Packet(source=<source>, dest=<dest>, len=<length>) for outgoing packets
#
#
# All packets have a header containing:
#  to          - intended recipient or BROADCAST (may also be an address on the way to the destination - routing)
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

def Packet(FieldRef):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Set fields if present
        self.from       (kwargs['from']     if 'from'     in kwargs else None)           # From is filled in by send_packet if not defined at creation
        self.source     (kwargs['source']   if 'source'   in kwargs else self.address)   # Source is usually from this host
        self.destination(kwargs['dest']     if 'dest'     in kwargs else None)           # Destination is usually a specific node or broadcast.  Usually the final destination
        self.to         (kwargs['to']       if 'to'       in kwargs else None)           # To is usually a specific node or broadcast for things like beacons; if None, filled in by route
        self.ttl        (kwargs['ttl']      if 'ttl'      in kwargs else _TTL_DEFAULT)   # TTL is default for most packets; set to 1 for beacons or one-time notices
        self.protocol   (kwargs['protocol'] if 'protocol' in kwargs else None)           # Protocol is packet type - defined by Packet inheriter

        self.rssi(kwargs['rssi'] if 'rssi' in kwargs else None)

    def __str__(self):
        return "Packet S%d D%d F%d T%d TTL%d P%d" % (self.source(), self.destination(), self.from(), self.to(), self.ttl(), self.protocol())

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

    # Process the route information
    # Note - should not be called directly, called from derived classes; must hold parent._packet_lock first
    # Returns (route,improved) improved True if a newer or improved route found
    def process(self, parent):
        if not parent._packet_lock.locked():
            print("packet_lock not locked: %s" % str(self))

        # Get or create a route to the source of the packet
        route = parent._find_route(self.source())
        improved = True

        if route == None:
            route = parent._define_route(self)
        
        elif self.sequence() != route.sequence() or self.metric() < route.metric():
            route.update(self)

        else:
            improved = False


        return route, improved

#########################################################################
# Beacon packet
#########################################################################
_BEACON_PROTOCOL            = const(0)
_BEACON_NAME                = create_field(_BEACON_NAME_LEN)
_BEACON_ADDRESS             = create_field(_ADDRESS_LEN, _BEACON_NAME)
_BEACON_LENGTH              = end_field(_BEACON_ADDRESS)

class Beacon(Packet):
    def __init__(self, **kwargs):
        kwargs['len'] = _BEACON_LENGTH
        kwargs['protocol'] = _BEACON_PROTOCOL
        super(Beacon, self).__init__(**kwargs)

        self.name(kwargs['name'] if 'name' in kwargs else "Beacon")
        self.address(kwargs['address'] if 'address' in kwargs else None)

    def __str__(self):
        return "Beacon: [%s] N'%s' A%d" % (str(super(Beacon, self)), self.name(return_type=str), self.address())

    def name(self, value=None):
        return self._fields(_BEACON_NAME, value)

    def address(self, value=None):
        return self._fields(_BEACON_ADDRESS, value)

    def process(self, parent):
        print(str(self))

#########################################################################
# Path announce
#########################################################################
_PANN_PROTOCOL              = const(1)
_PANN_FLAGS                 = create_field(_FLAGS_LEN)
_PANN_FLAGS_GATEWAY             = const(0)
_PANN_SEQUENCE              = create_field(_INTERVAL_LEN, _PANN_FLAGS)
_PANN_INTERVAL              = create_field(_INTERVAL_LEN, _PANN_SEQUENCE)
_PANN_METRIC                = create_field(_METRIC_LEN, _PANN_INTERVAL)
_PANN_LENGTH                = end_field(_PANN_METRIC)

class PathAnnounce(Packet):
    def __init__(self, **kwargs):
        kwargs['len'] = _PANN_LENGTH
        kwargs['protocol'] = _PANN_PROTOCOL
        super(PathAnnounce, self).__init__(**kwargs)

        self.gateway_flag(kwargs['gw'] if 'gw' in kwargs else False)
        self.interval(kwargs['interval'] if 'interval' in kwargs else _INTERVAL_DEFAULT)
        self.metric(kwargs['metric'] if 'metric' in kwargs else 1)
        self.sequence(kwargs['sequence'] if 'sequence' in kwargs else 0)

    def __str__(self):
        return "PathAnnounce: [%s] Int %.1f M%d" % (str(super(PathAnnounce, self)), self.interval(), self.metric())

    def gateway_flag(self, value=None):
        return self._field_bit(_PANN_FLAGS, _PANN_FLAGS_GATEWAY, value)

    def sequence(self, value=None):
        return self._field(_PANN_SEQUENCE, value)

    def interval(self, value=None):
        return self._field(_PANN_INTERVAL, value)

    def metric(self, value=None):
        return self._field(_PANN_METRIC, value)

    #
    # Capture the path to the <source> and rebroadcast if TTL is non-zero
    # If we already have a route to this node, only capture updated metric if it gets better
    #
    def process(self, parent):
        with parent._packet_lock:
            route, improved = super().process(parent)
            
            if self.to() == _BROADCAST_ADDRESS:
                # If an improved / new announce, send it on the broascast chain
                if improved:
                    self.metric(self.metric() + 1)
                    parent.send_packet(self, ttl=True)

#########################################################################
# Path Request
#########################################################################
_PREQ_PROTOCOL              = const(2)
_PREQ_FLAGS                 = create_field(_FLAGS_LEN)
_PREQ_FLAGS_GATEWAY             = const(0)
_PREQ_SEQUENCE              = create_field(_SEQUENCE_NUMBER_LEN, _PREQ_FLAGS)
_PREQ_METRIC                = create_field(_METRIC_LEN, _PREQ_SEQUENCE)
_PREQ_LENGTH                = end_field(_PREQ_METRIC)

class PathRequest(Packet):
    def __init__(self, **kwargs):
        kwargs['len'] = _PREQ_LENGTH
        kwargs['protocol'] = _PREQ_PROTOCOL
        super(PathRequest, self).__init__(**kwargs)

        self.gateway_flag(kwargs['gw'] if 'gw' in kwargs else False)
        self.sequence(kwargs['sequence'] if 'sequence' in kwargs else None)
        self.metric(kwargs['metric'] if 'metric' in kwargs else 1)

    def __str__(self):
        return "PathRequest: [%s] Seq%d M%d" % (str(super(PathRequest, self)), self.sequence(), self.metric())

    def gateway_flag(self, value=None):
        return self._field_bit(_PREQ_FLAGS, _PREQ_FLAGS_GATEWAY, value)

    def sequence(self, value=None)):
        return self._field(_PREQ_SEQUENCE, value)

    def metric(self, value=None):
        return self._field(_PREQ_METRIC, value)

    # Process in incoming RREQ
    # TODO: Need brakes to avoid transmitting too many at once !! (Maybe ok now)
    def process(self, parent):
        with parent._packet_lock:
            # Return route if we created a new one
            route, improved = super().process(parent)

            # If to us, decide if to send PathReply
            if self.destination() == parent.address:
                # Only send pathreply if it's been long enough since last one
                if route.is_reply_delay():
                    route.set_reply_delay()
                    # This a a path request that arrived at destination - generate reply
                    parent.send_packet(PathReply(dest=self.source(), sequence=self.sequence(), metric=self.metric()))

            # Otherwise, if this is a broadcast packet, continue to flood the network
            elif self.to() == _BROADCAST_ADDRESS:
                # If route was improved, send it along the broadcast chain
                if improved:
                    # retransmit the packet if ttl is still non-zero
                    self.metric(self.metric() + 1)
                    self.send_packet(self, ttl=True)

            else:
                # Ignore directed PathRequests for now
                pass

#########################################################################
# Path Reply
#########################################################################
_PREP_PROTOCOL              = const(3)
_PREP_FLAGS                 = create_field(_FLAGS_LEN)
_PREP_FLAGS_GATEWAY             = const(0)
_PREP_SEQUENCE              = create_field(_SEQUENCE_NUMBER_LEN, _PREP_FLAGS)
_PREP_METRIC                = create_field(_METRIC_LEN, _PREP_SEQUENCE)
_PREP_LENGTH                = end_field(_PREP_METRIC)

class PathReply(Packet):
    def __init__(self, **kwargs):
        kwargs['len'] = _PREP_LENGTH
        kwargs['protocol'] = _PREP_PROTOCOL
        super(PathReply, self).__init__(**kwargs)

        self.sequence(kwargs['sequence'] if 'sequence' in kwargs else 0)
        self.metric(kwargs['metric'] if 'metric' in kwargs else 0)

    def __str__(self):
        return "PathReply: [%s] Seq%d M%d" % (str(super(PathReply, self)), self.sequence(), self.metric())

    def gateway_flag(self, value):
        return self._field_bit(_PREP_FLAGS, _PREP_FLAGS_GATEWAY, value)

    def sequence(self):
        return self._field(_PREP_SEQUENCE, value)

    def metric(self, value=None):
        return self._field(_PREP_METRIC, value)

    def process(self, parent):
        # Process the route information
        route, improved = super().process(parent)

        # If directly to us, move any route-pending packets to active queue, if we have a route to the source
        if self.destination() == self.address:
            # Move all pending packets to the transmit queue
            packet = True
            while packet != None:
                packet = route.get_pending_packet()
                if packet:
                    parent.send_packet(packet)

#########################################################################
# Path Error
#########################################################################
_PERR_PROTOCOL              = const(4)
_PERR_ADDRESS               = create_field(_ADDRESS_LEN)
_PERR_SEQUENCE              = create_field(_SEQUENCE_NUMBER_LEN, _PERR_ADDRESS)
_PERR_REASON                = create_field(_REASON_LEN, _PERR_SEQUENCE)
_PERR_LENGTH                = end_field(_PERR_REASON)

class PathError(Packet):
    def __init__(self, **kwargs):
        kwargs['len'] = _PERR_LENGTH
        super(PathError, self).__init__(**kwargs)

        self.address(kwargs['address'] if 'address' in kwargs else 0)
        self.sequence(kwargs['sequence'] if 'sequence' in kwargs else 0)
        self.reason(kwargs['reason'] if 'reason' in kwargs else 0)

    def __str__(self):
        return "PathError: [%s] Seq%d R%d" % (str(super(PathError, self)), self.ttl(), self.sequence(), self.readon())

    def address(self, value=None):
        return self._field(_PERR_ADDRESS, value)

    def sequence(self, value=None):
        return self._field(_PERR_SEQUENCE, value)

    def reason(self, value=None):
        return self._field(_PERR_REASON, value)

    def process(self, parent):
        print(str(self))


#########################################################################
# Data packet.
#########################################################################
_DATA_PROTOCOL              = const(5)
_DATA_STREAM                = create_field(_STREAM_NUMBER_LEN)
_DATA_SEQUENCE              = create_field(_STREAM_SEQUENCE_LEN, _DATA_STREAM)
_DATA_WINDOW                = create_field(_STREAM_SEQUENCE_LEN, _DATA_SEQUENCE)
_DATA_LENGTH                = end_field(_DATA_WINDOW)

class DataPacket(Packet):
    def __init__(self, **kwargs):
        kwargs['len'] = _DATA_LENGTH
        kwargs['protocol'] = _DATA_PROTOCOL
        super(DataPacket, self).__init__(**kwargs)

        self.stream(kwargs['stream'] if 'stream' in kwargs else 0)
        self.sequence(kwargs['sequence'] if 'sequence' in kwargs else 0)
        self.window(kwargs['window'] if 'window' in kwargs else 0)

        if 'payload' in kwargs:
            self._data[_DATA_LENGTH:] = kwargs['payload']

    def __str__(self):
        return "Data: [%s] Str%d Seq%d W%d Len%d" % (str(super(DataPacket, self)), self.stream(), self.sequence(), self.window())

    def stream(self, value=None):
        return self._field(_DATA_STREAM, value)

    def sequence(self, value=None):
        return self._field(_DATA_SEQUENCE, value)

    def window(self, value=None):
        return self._field(_DATA_WINDOW, value)

    # Return the payload portion of the data
    def payload(self):
        return self._data[_DATA_LENGTH:]

    def process(self, parent):
        # If this packet has found it's recipient, put in queue
        if self.destination() == parent.address:
            parent.put_receive_packet(self)

        else:
            self.to(None)    # to will be filled in by route
            self.from(None)  # from filled in by self.address

            # Route the packet onward if ttl not expired
            parent.send_packet(self, ttl=True)

class Route():
    def __init__(self, packet=None, lifetime=_ROUTE_LIFETIME, **kwargs):
        self._lifetime = lifetime
        self._expires = time() + self._lifetime
        self._transmit_queue = queue()
        self._sequence = 0
        self._metric = 0
        self._to = None
        self._gateway = False
        self._announce = 0
        self._reply_timeout = 0

        if type(packet) = PathReply or type(packet) == PathAnnounce or type(packet) == PathRequest:
            self.update(reply)

        else:
            self.update(**kwargs)

    # Set reply delay period
    def set_reply_delay(self, reply_delay=_REPLY_DELAY):
        self._reply_delay = time() + reply_delay

    # Return true if in delay period
    def is_reply_delay(self):
        return time() <= self._reply_delay

    def put_pending_packet(self, packet):
        self._transmit_queue.put(packet)

    def get_pending_packet(self):
        return self._transmit_queue.get(wait=0)

    def update(self, packet=None, **kwargs):
        self._expires = time() + self._lifetime

        if packet != None:
            self._sequence = packet.sequence()
            self._metric   = packet.metric()
            self._to       = packet.source() if type(packet) == PathAnnouce else packet.source()
            if type(packet) == PathAnnounce:
                self._gateway  = packet.gateway_flags()
                self._announce = packet.interval()

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
        return time() >= self._expires

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

#########################################################################
# This level maintains handles the routing protocol
# and will deliver non-routing messages to the inheriter.
#########################################################################
class MeshNet(RadioDriver):

    def __init__(self, domain, address, **kwargs):
        SX127x_driver.__init__(self, domain, **kwargs)

        self.address = address
        self._meshlock = rlock()
        self._transmit_queue = queue()
        self._receive_queue = queue()
        self._hwmp_sequence_number = 0
        self._hwmp_sequence_lock = lock()

        # Defines routes to nodes
        self._routes = {}
        # Defines root announced nodes
        self._packets_errors_crc = 0
        self._packets_processed = 0
        self._packets_ignored = 0

        self._announce_interval = float(kwargs['interval']) if 'interval' in kwargs else 0

        self._PROTOCOLS = {
                _PANN_PROTOCOL: PathAnnounce,
                _PREQ_PROTOCOL: PathRequest,
                _PREP_PROTOCOL: PathReply,
                _PERR_PROTOCOL: PathError,
                _DATA_PROTOCOL: DataPacket,
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

        # Start announce if requested
        if self._announce_interval != 0:
            self.announce_start(self._announce_interval)

    def announce_start(self, interval):
        self._announce_thread = thread(run=self._announce)
        self._announce_thread.start(interval=self._announce)

    def announce_stop(self):
        rc = None

        if self._announce_thread:
            self._announce_thread.stop()
            rc = self._announce_thread.wait()
            self._announce_thread = None

        return rc

    def _announce(self, t, interval):
        countdown = interval

        # Only sleep a second at a time so we can be killed fairly quickly
        while t.running:
            sleep(1)
            countdown -= 1
            if countdown <= 0:
                countdown += interval
                packet = PathAnnounce(dest=_BROADCAST_ADDRESS, gw=True, address=self.address, interval=interval, sequence=self._create_sequence_number())
                self.send_packet(packet)

        return 0

    def get_protocol_wrapper(self, protocol):
        if protocol in self._PROTOCOLS:
            return self._PROTOCOLS[protocol]
        else
            return None

    # Default to search routes table
    def _define_route(self, packet):
        address = packet.source()

        if address in self._routes:
            route = self._routes[address]
            # If root has expired, just renew it
            if route.is_expired():
                route.update(packet)
        else:
            # If we are at max  routes, try to delete all expired routes
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

    # Default to search routes table
    def _find_route(address):
        return self._routes[address] if address in self._routes else None

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


    def get_receive_packet(self):
        return self._receive_queue.get()

    def put_receive_packet(self, packet):
        self._receive_queue.put(packet)

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

    def _create_sequence_number(self):
        with self._hwmp_sequence_lock:
            self._hwmp_sequence_number += 1
            return self._hwmp_sequence_number

    # A packet with a source and destination is ready to transmit.
    # Label the from address and if no to address, attempt to route
    # If ttl is true, decrease ttl and discard packet if 0
    def send_packet(self, packet, ttl=False):
        if ttl and packet.ttl(packet.ttl() - 1) == 0:
            # Packet has expired
            print("Expired: %s" str(packet))
        else:
            # Label packets as coming from us if it doesn't have an address
            if packet.from() == None:
                packet.from(self.address)

            # If no direct recipient has been defined, we go through routing table
            if packet.to() == None:
                # Look up the path to the destination
                route = self._find_route(packet.destination())

                # If no path, create a dummy path and queue the results
                if route == None:
                    # Unknown route.  Create a NULL route awaiting PathReply
                    route = self._define_route(packet.destination())
                    request = PathRequest(dest=route.desination(), sequence=self._create_sequence_number())
                    route.put_pending_packet(packet)

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
                #
                # TODO: we may need another method to restart transmit queue other than looking
                # and transmit queue length.  A 'transmitting' flag (protected by meshlock) that
                # is True if transmitting of packet is in progress.  Cleared on onTransmit when
                # queue has become empty.
                #
                # This may need to be implemented to allow stalling transmission for windows of
                # reception.  A timer will then restart the queue if items remain within it.
                #
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

        # Stop announce if running
        self.announce_stop()

        # Close SPI channel if opened
        if self._spi:
            self._spi.deinit()
            self._spi = None

        # Shut down power
        self.set_power(False)

    def set_power(self, power=True):
        # print("set_power %s" % power)

        if power != self._power:
            self._power = power

            # Call base class
            super().set_power(power)

    def __del__(self):
        self.close()

