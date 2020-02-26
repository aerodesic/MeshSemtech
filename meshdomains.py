# 
# Channel domain list
#
# Defines the channels and data rates available for communication
#

US902_MESHNET = {
    'freq_range':
        (902000000, 928000000),

    # 'type' <'up' or 'down' link type>,
    # 'chan': ( <low inclusive channel>, <high inclusive channel>),
    # 'dr': (<low inclusive datarate>, <high inclusive datarate>),
    # 'freq': (<starting freq>, <step>),
    'channels': (
        { 'type': 'narrow', 'chan': (0, 64), 'dr': (8, 13), 'freq': (90230000, 200000)  },
        { 'type': 'wide',   'chan': (0, 15), 'dr': (0, 3),  'freq': (90300000, 1600000) },
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
        # Narrow band
        0:  { 'sf': 10, 'bw': 125e6, 'tx': 30, 'n': 11,  'm': 19  },
        1:  { 'sf': 9,  'bw': 125e6, 'tx': 28, 'n': 53,  'm': 61  },
        2:  { 'sf': 8,  'bw': 125e6, 'tx': 26, 'n': 124, 'm': 133 },
        3:  { 'sf': 7,  'bw': 125e6, 'tx': 24, 'n': 242, 'm': 250 },

        # Wide band
        8:  { 'sf': 12, 'bw': 500e6, 'tx': 14, 'n': 33,  'm': 41  },
        9:  { 'sf': 11, 'bw': 500e6, 'tx': 12, 'n': 109, 'm': 117 },
        10: { 'sf': 10, 'bw': 500e6, 'tx': 10, 'n': 220, 'm': 230 },
        11: { 'sf': 9,  'bw': 500e6, 'tx': 8,  'n': 220, 'm': 230 },
        12: { 'sf': 8,  'bw': 500e6, 'tx': 6,  'n': 220, 'm': 230 },
        13: { 'sf': 7,  'bw': 500e6, 'tx': 4,  'n': 220, 'm': 230 },
    },
}

