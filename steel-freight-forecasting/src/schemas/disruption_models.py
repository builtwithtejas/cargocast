from enum import Enum
from typing import List, Optional, Dict
from .base import BaseModel, Field

class DisruptionCategory(str, Enum):
    CYCLONE_MONSOON = 'CYCLONE_MONSOON'
    PORT_CONGESTION = 'PORT_CONGESTION'
    LABOR_STRIKE = 'LABOR_STRIKE'
    CANAL_STRAIT_BOTTLENECK = 'CANAL_STRAIT_BOTTLENECK'
    GEOPOLITICAL_REGULATORY = 'GEOPOLITICAL_REGULATORY'
    OPERATIONAL_NORMAL = 'OPERATIONAL_NORMAL'

class DisruptionSeverity(str, Enum):
    LOW = 'LOW'
    MODERATE = 'MODERATE'
    ELEVATED = 'ELEVATED'
    SEVERE = 'SEVERE'
    CRITICAL = 'CRITICAL'

class DisruptionEvent(BaseModel):
    news_id: str
    timestamp: str
    headline: str
    source: str
    raw_text: str
    category: DisruptionCategory
    severity: DisruptionSeverity
    severity_score: float = Field(..., ge=0.0, le=1.0, description='Normalized disruption score 0.0-1.0')
    affected_ports: List[str] = Field(default_factory=list)
    affected_regions: List[str] = Field(default_factory=list)
    matched_keywords: List[str] = Field(default_factory=list)
    confidence: float = 0.85

class PortDisruptionStatus(BaseModel):
    port_id: str
    port_name: str
    disruption_score: float = Field(..., ge=0.0, le=1.0)
    severity_level: DisruptionSeverity
    dominant_category: DisruptionCategory
    active_event_count: int
    waiting_time_multiplier: float
    demurrage_risk_premium_usd_mt: float
    summary: str

class DailyDisruptionReport(BaseModel):
    as_of_date: str
    composite_east_coast_score: float = Field(..., ge=0.0, le=1.0)
    composite_severity: DisruptionSeverity
    port_statuses: Dict[str, PortDisruptionStatus]
    critical_events: List[DisruptionEvent]
    feature_vector: Dict[str, float] = Field(
        default_factory=dict,
        description='Flat dictionary of numeric feature values for Feature Engineer master table'
    )
