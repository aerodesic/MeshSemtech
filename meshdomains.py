# 
# LoRa regulatory domain list
#
# Need to flesh this out
#

US902_EMNET = {
    'freq_range':
        (902000000, 928000000),

    # 'type' <'up' or 'down' link type>,
    # 'chan': ( <low inclusive channel>, <high inclusive channel>),
    # 'dr': (<low inclusive datarate>, <high inclusive datarate>),
    # 'freq': (<starting freq>, <step>),
    'channels': (
        { 'type': 'wide',   'chan': (0, 15), 'dr': (0, 5), 'freq': (90230000, 1600000) }
        { 'type': 'narrow', 'chan': (0, 64), 'dr': (0, 5), 'freq': (90230000, 200000) }
    ),

    # <rate>: {
    #    'sf': <spreading factor>,
    #    'bw': <bandwidth>,
    #    'tx': <tx power limit>,
    #    'n': <max user payload>,
    #    'm': <max total bytes>,
    # }
    'data_rates': {
        # Most to least reliable order
        0: { 'sf': 12, 'bw': 500e6, 'tx': 14, 'n': 33,  'm': 41  },
        1: { 'sf': 11, 'bw': 500e6, 'tx': 12, 'n': 109, 'm': 117 },
        2: { 'sf': 10, 'bw': 500e6, 'tx': 10, 'n': 220, 'm': 230 },
        3: { 'sf': 9,  'bw': 500e6, 'tx': 8,  'n': 220, 'm': 230 },
        4: { 'sf': 8,  'bw': 500e6, 'tx': 6,  'n': 220, 'm': 230 },
        5: { 'sf': 7,  'bw': 500e6, 'tx': 4,  'n': 220, 'm': 230 },
    },
}

US902_928 = {
    'freq_range':
        (902000000, 928000000),

    # 'type' <'up' or 'down' link type>,
    # 'chan': ( <low inclusive channel>, <high inclusive channel>),
    # 'dr': (<low inclusive datarate>, <high inclusive datarate>),
    # 'freq': (<starting freq>, <step>),
    'channels': (
        { 'type': 'up',      'chan': (0, 63),  'dr': (0, 3), 'freq': (902300000,  200000), },
        { 'type': 'up',      'chan': (64, 71), 'dr': (4, 4), 'freq': (903000000, 1600000), },
        # { 'type': 'down',  'chan': (0, 7),   'dr': (4, 4), 'freq': (923300000,  600000), },
        { 'type': 'down',    'chan': (0, 7),   'dr': (8, 13), 'freq': (923300000,  600000), },
    ),

    # <rate>: {
    #    'sf': <spreading factor>,
    #    'bw': <bandwidth>,
    #    'tx': <tx power limit>,
    #    'n': <max user payload>,
    #    'm': <max total bytes>,
    # }
    'data_rates': {
        # For narrow-band uplink channels (higher number is less reliable, larger packet)
        0:  { 'sf': 10, 'bw': 125e6, 'tx': 30, 'n': 11,  'm': 19  },
        1:  { 'sf': 9,  'bw': 125e6, 'tx': 28, 'n': 53,  'm': 61  },
        2:  { 'sf': 8,  'bw': 125e6, 'tx': 26, 'n': 124, 'm': 133 },
        3:  { 'sf': 7,  'bw': 125e6, 'tx': 24, 'n': 242, 'm': 250 },

        # For wide-band  uplink channels
        4:  { 'sf': 8,  'bw': 500e6, 'tx': 22, 'n': 242, 'm': 250 },

        # 5: {}, # RFU
        # 6: {}, # RFU
        # 7: {}, # RFU

        # For wide-band downlink channels (higher number is less reliable, larger packet)
        8:  { 'sf': 12, 'bw': 500e6, 'tx': 14, 'n': 33,  'm': 41  },
        9:  { 'sf': 11, 'bw': 500e6, 'tx': 12, 'n': 109, 'm': 117 },
        10: { 'sf': 10, 'bw': 500e6, 'tx': 10, 'n': 220, 'm': 230 },
        11: { 'sf': 9,  'bw': 500e6, 'tx': 8,  'n': 220, 'm': 230 },
        12: { 'sf': 8,  'bw': 500e6, 'tx': 6,  'n': 220, 'm': 230 },
        13: { 'sf': 7,  'bw': 500e6, 'tx': 4,  'n': 220, 'm': 230 },
        # 14: {} # RFU
        # 15: {} # Defined in LoRaWAN
    },
}

