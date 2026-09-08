# Maritime and Meteorological Lexicon for Shipping Disruption Extraction

CATEGORY_KEYWORDS = {
    'CYCLONE_MONSOON': {
        'cyclone': 0.85,
        'severe cyclonic storm': 0.95,
        'deep depression': 0.75,
        'low pressure area': 0.40,
        'typhoon': 0.90,
        'gale warning': 0.70,
        'squall': 0.60,
        'monsoon swell': 0.55,
        'rough sea': 0.50,
        'local cautionary signal': 0.65,
        'signal no. 4': 0.75,
        'signal no. 8': 0.95,
        'signal no. 10': 1.00,
        'pilotage suspended': 0.85,
        'berthing suspended': 0.90,
        'port closed': 1.00,
        'vessel movement halted': 0.85
    },
    'PORT_CONGESTION': {
        'congestion': 0.60,
        'berthing delay': 0.65,
        'anchorage queue': 0.60,
        'vessels waiting': 0.55,
        'draft restriction': 0.70,
        'siltation': 0.65,
        'dredging required': 0.50,
        'river draft drop': 0.75,
        'lighterage mandated': 0.70,
        'hopper suction dredge': 0.40,
        'berth occupancy': 0.50,
        'unplanned maintenance': 0.60,
        'derailment': 0.70,
        'rail bottlenecks': 0.65,
        'evacuation delays': 0.60
    },
    'LABOR_STRIKE': {
        'strike': 0.85,
        'dockworkers union': 0.75,
        'indefinite strike': 0.95,
        'stevedore stoppage': 0.85,
        'wage dispute': 0.50,
        'work-to-rule': 0.65,
        'protest': 0.45,
        'labor action': 0.70,
        'ground to a halt': 0.85,
        'walkout': 0.80
    },
    'CANAL_STRAIT_BOTTLENECK': {
        'canal closure': 0.95,
        'red sea': 0.80,
        'bab el-mandeb': 0.85,
        'houthi': 0.80,
        'cape of good hope detour': 0.85,
        'suez canal transit': 0.70,
        'panama canal draft': 0.75,
        'malacca strait': 0.70,
        'strait of malacca': 0.70,
        'sunda strait': 0.65,
        'lombok strait': 0.65,
        'strait bottleneck': 0.75,
        'rerouting': 0.70
    },
    'GEOPOLITICAL_REGULATORY': {
        'export ban': 0.90,
        'mineral ban': 0.85,
        'coal export quota': 0.75,
        'customs clearance halt': 0.80,
        'bunker fuel price surge': 0.70,
        'vlsfo price spike': 0.65,
        'opec production cut': 0.55,
        'sanctions': 0.75,
        'war risk premium': 0.85,
        'freight hike': 0.60
    }
}

RELIEF_KEYWORDS = {
    'normal operations resume': 0.80,
    'operations normalized': 0.85,
    'weather cleared': 0.75,
    'strike called off': 0.90,
    'strike withdrawn': 0.90,
    'draft restored': 0.75,
    'congestion cleared': 0.80,
    'queue normalized': 0.70,
    'full capacity': 0.65,
    'clearance given': 0.60,
    'smooth discharge': 0.60
}

SOURCE_CREDIBILITY = {
    'imd': 1.00,
    'india meteorological department': 1.00,
    'port authority': 0.98,
    'ministry of shipping': 0.98,
    'argus': 0.92,
    'platts': 0.92,
    'tradewinds': 0.90,
    'lloyds list': 0.90,
    'maritime gateway': 0.88,
    'the hindu businessline': 0.86,
    'economic times': 0.85,
    'reuters': 0.92,
    'general_media': 0.75
}

PORT_ALIASES = {
    'IN_PRT': ['paradip', 'paradeep'],
    'IN_VTZ_OUTER': ['vizag outer', 'visakhapatnam outer', 'vizag outer harbour'],
    'IN_VTZ_INNER': ['vizag inner', 'visakhapatnam inner', 'vizag inner harbour'],
    'IN_GNR': ['gangavaram'],
    'IN_DHM': ['dhamra', 'dhamara'],
    'IN_GOP': ['gopalpur'],
    'IN_HLD': ['haldia', 'kolkata port', 'syama prasad mookerjee', 'hooghly river', 'hooghly'],
    'IN_SGR_ANCH': ['sandheads', 'sagar roads', 'sagar anchorage', 'sandheads anchorage'],
    'AU_HPT': ['hay point', 'dalrymple bay', 'dbct'],
    'AU_GLT': ['gladstone', 'rg tanna', 'barney point'],
    'AU_NCL': ['newcastle', 'pwcs', 'ncig'],
    'US_ORF': ['norfolk', 'hampton roads', 'lamberts point', 'pier 6'],
    'MZ_MPM': ['maputo', 'matola'],
    'MZ_BEI': ['beira'],
    'ID_TBN': ['taboneo', 'south kalimantan'],
    'ID_SMD': ['samarinda', 'muara berau', 'east kalimantan'],
    'RU_TMN': ['taman', 'black sea'],
    'RU_VOS': ['vostochny', 'nakhodka']
}

STRAIT_ALIASES = {
    'Malacca Strait': ['strait of malacca', 'malacca strait', 'singapore strait'],
    'Sunda Strait': ['sunda strait'],
    'Lombok Strait': ['lombok strait'],
    'Bab el-Mandeb': ['bab el-mandeb', 'red sea'],
    'Cape of Good Hope': ['cape of good hope', 'cape route']
}

REGION_ALIASES = {
    'Bay of Bengal': ['bay of bengal', 'odisha coast', 'andhra coast', 'bengal coast'],
    'East Coast India': ['east coast', 'east coast india', 'coromandel coast'],
    'Australia': ['australia', 'queensland', 'new south wales'],
    'Indonesia': ['indonesia', 'kalimantan', 'borneo'],
    'Mozambique': ['mozambique', 'east africa'],
    'USA': ['united states', 'us east coast', 'chesapeake'],
    'Black Sea': ['black sea', 'bosphorus', 'russia']
}
