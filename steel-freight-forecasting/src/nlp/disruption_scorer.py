import re
import math
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timezone
from src.schemas.disruption_models import (
    DisruptionCategory, DisruptionSeverity, DisruptionEvent,
    PortDisruptionStatus, DailyDisruptionReport
)
from .maritime_lexicon import (
    CATEGORY_KEYWORDS, RELIEF_KEYWORDS, PORT_ALIASES, REGION_ALIASES,
    SOURCE_CREDIBILITY, STRAIT_ALIASES
)

class MaritimeDisruptionScorer:
    """
    Extracts maritime disruption signals from news feeds, weather circulars,
    and port circulars, scoring severity and mapping operational delays.
    Features temporal exponential decay and source credibility weighting.
    """
    def __init__(self):
        self.category_keywords = CATEGORY_KEYWORDS
        self.relief_keywords = RELIEF_KEYWORDS
        self.port_aliases = PORT_ALIASES
        self.region_aliases = REGION_ALIASES
        self.source_credibility = SOURCE_CREDIBILITY
        self.strait_aliases = STRAIT_ALIASES
        self.decay_half_life_days = 3.5
        self.decay_lambda = math.log(2.0) / self.decay_half_life_days

    def _match_entities(self, text: str) -> Tuple[List[str], List[str]]:
        lower_text = text.lower()
        matched_ports = []
        for port_id, aliases in self.port_aliases.items():
            for alias in aliases:
                pattern = rf'(?i)\b{re.escape(alias)}\b'
                if re.search(pattern, lower_text):
                    if port_id not in matched_ports:
                        matched_ports.append(port_id)
                    break
        
        matched_regions = []
        for region, aliases in self.region_aliases.items():
            for alias in aliases:
                pattern = rf'(?i)\b{re.escape(alias)}\b'
                if re.search(pattern, lower_text):
                    if region not in matched_regions:
                        matched_regions.append(region)
                    break

        # Check straits
        for strait, aliases in self.strait_aliases.items():
            for alias in aliases:
                pattern = rf'(?i)\b{re.escape(alias)}\b'
                if re.search(pattern, lower_text):
                    if strait not in matched_regions:
                        matched_regions.append(strait)
                    break

        if re.search(r'(?i)\b(vizag|visakhapatnam)\b', lower_text):
            if 'IN_VTZ_OUTER' not in matched_ports:
                matched_ports.append('IN_VTZ_OUTER')
            if 'IN_VTZ_INNER' not in matched_ports:
                matched_ports.append('IN_VTZ_INNER')

        return matched_ports, matched_regions

    def _get_source_weight(self, source: str) -> float:
        s_lower = source.lower()
        for src_key, weight in self.source_credibility.items():
            if src_key in s_lower:
                return weight
        return 0.80

    def score_news_item(
        self,
        news_id: str,
        headline: str,
        raw_text: str,
        source: str = 'Maritime Wire',
        timestamp: Optional[str] = None,
        as_of_reference_dt: Optional[datetime] = None
    ) -> DisruptionEvent:
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
            
        full_text = f'{headline} {raw_text}'.lower()
        matched_ports, matched_regions = self._match_entities(full_text)

        # 1. Score each category
        category_scores: Dict[DisruptionCategory, float] = {}
        category_matched_terms: Dict[DisruptionCategory, List[str]] = {}

        for cat_name, kw_dict in self.category_keywords.items():
            cat_enum = DisruptionCategory(cat_name)
            current_score = 0.0
            terms_found = []
            for term, weight in kw_dict.items():
                if term in full_text:
                    terms_found.append(term)
                    current_score += weight / (1.0 + 0.35 * len(terms_found))
            category_scores[cat_enum] = min(current_score, 1.0)
            category_matched_terms[cat_enum] = terms_found

        # 2. Check relief keywords
        relief_score = 0.0
        relief_terms = []
        for term, weight in self.relief_keywords.items():
            if term in full_text:
                relief_terms.append(term)
                relief_score += weight

        # 3. Dominant category
        max_cat = DisruptionCategory.OPERATIONAL_NORMAL
        max_cat_score = 0.0
        for cat, score in category_scores.items():
            if score > max_cat_score:
                max_cat_score = score
                max_cat = cat

        # Net severity
        if relief_score > 0.5 and max_cat_score < 0.6:
            dominant_category = DisruptionCategory.OPERATIONAL_NORMAL
            base_score = max(0.0, 0.12 - relief_score * 0.08)
            matched_terms = relief_terms
        else:
            dominant_category = max_cat
            base_score = max(0.0, min(1.0, max_cat_score - (relief_score * 0.4)))
            matched_terms = category_matched_terms.get(max_cat, [])

        # 4. Source Credibility & Temporal Decay
        src_weight = self._get_source_weight(source)
        decay_multiplier = 1.0

        if as_of_reference_dt and timestamp:
            try:
                # Clean timestamp string
                clean_ts = timestamp.replace('Z', '+00:00')
                event_dt = datetime.fromisoformat(clean_ts)
                if event_dt.tzinfo is not None and as_of_reference_dt.tzinfo is None:
                    as_of_reference_dt = as_of_reference_dt.replace(tzinfo=timezone.utc)
                age_days = max(0.0, (as_of_reference_dt - event_dt).total_seconds() / 86400.0)
                decay_multiplier = math.exp(-self.decay_lambda * age_days)
            except Exception:
                decay_multiplier = 1.0

        net_score = base_score * src_weight * decay_multiplier

        # Map to DisruptionSeverity
        if net_score >= 0.80:
            severity = DisruptionSeverity.CRITICAL
        elif net_score >= 0.65:
            severity = DisruptionSeverity.SEVERE
        elif net_score >= 0.45:
            severity = DisruptionSeverity.ELEVATED
        elif net_score >= 0.20:
            severity = DisruptionSeverity.MODERATE
        else:
            severity = DisruptionSeverity.LOW

        confidence = round(min(0.95, 0.75 + (src_weight * 0.15) + (len(matched_terms) * 0.03)), 2)

        return DisruptionEvent(
            news_id=news_id,
            timestamp=timestamp,
            headline=headline,
            source=source,
            raw_text=raw_text,
            category=dominant_category,
            severity=severity,
            severity_score=round(net_score, 4),
            affected_ports=matched_ports,
            affected_regions=matched_regions,
            matched_keywords=matched_terms,
            confidence=confidence
        )

    def generate_daily_report(
        self,
        news_items: List[Dict],
        as_of_date: str = '2026-09-02',
        known_east_coast_ports: Optional[List[str]] = None
    ) -> DailyDisruptionReport:
        if known_east_coast_ports is None:
            known_east_coast_ports = [
                'IN_PRT', 'IN_VTZ_OUTER', 'IN_VTZ_INNER', 'IN_GNR',
                'IN_DHM', 'IN_GOP', 'IN_HLD', 'IN_SGR_ANCH'
            ]

        try:
            ref_dt = datetime.strptime(as_of_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        except Exception:
            ref_dt = datetime.now(timezone.utc)

        port_name_map = {
            'IN_PRT': 'Paradip',
            'IN_VTZ_OUTER': 'Vizag Outer Harbour',
            'IN_VTZ_INNER': 'Vizag Inner Harbour',
            'IN_GNR': 'Gangavaram',
            'IN_DHM': 'Dhamra',
            'IN_GOP': 'Gopalpur',
            'IN_HLD': 'Haldia Dock Complex',
            'IN_SGR_ANCH': 'Sagar / Sandheads Anchorage'
        }

        events: List[DisruptionEvent] = []
        for item in news_items:
            event = self.score_news_item(
                news_id=item.get('news_id', 'NEWS_GEN'),
                headline=item.get('headline', ''),
                raw_text=item.get('raw_text', ''),
                source=item.get('source', 'Maritime Feed'),
                timestamp=item.get('timestamp'),
                as_of_reference_dt=ref_dt
            )
            if item.get('target_ports'):
                for tp in item['target_ports']:
                    if tp not in event.affected_ports:
                        event.affected_ports.append(tp)
            if item.get('regions'):
                for rg in item['regions']:
                    if rg not in event.affected_regions:
                        event.affected_regions.append(rg)
            events.append(event)

        port_events: Dict[str, List[DisruptionEvent]] = {p: [] for p in known_east_coast_ports}
        for ev in events:
            if ev.affected_ports:
                for p in ev.affected_ports:
                    if p in port_events:
                        port_events[p].append(ev)
            elif any(r in ['Bay of Bengal', 'East Coast India'] for r in ev.affected_regions):
                for p in known_east_coast_ports:
                    port_events[p].append(ev)

        port_statuses: Dict[str, PortDisruptionStatus] = {}
        for port_id in known_east_coast_ports:
            assigned = port_events[port_id]
            if not assigned:
                port_score = 0.08
                dom_cat = DisruptionCategory.OPERATIONAL_NORMAL
                sev = DisruptionSeverity.LOW
                summary = 'Normal maritime traffic and pilotage conditions.'
            else:
                scores = [e.severity_score for e in assigned]
                max_s = max(scores)
                mean_s = sum(scores) / len(scores)
                port_score = min(1.0, max_s * 0.7 + mean_s * 0.3)
                highest_event = max(assigned, key=lambda x: x.severity_score)
                dom_cat = highest_event.category
                sev = highest_event.severity
                summary = f'{highest_event.headline} ({len(assigned)} active alerts)'

            waiting_mult = round(1.0 + (port_score * 2.5), 2)
            demurrage_prem = round((port_score * 4.0 * 22000.0) / 75000.0, 2)

            port_statuses[port_id] = PortDisruptionStatus(
                port_id=port_id,
                port_name=port_name_map.get(port_id, port_id),
                disruption_score=round(port_score, 4),
                severity_level=sev,
                dominant_category=dom_cat,
                active_event_count=len(assigned),
                waiting_time_multiplier=waiting_mult,
                demurrage_risk_premium_usd_mt=demurrage_prem,
                summary=summary
            )

        composite_score = sum(ps.disruption_score for ps in port_statuses.values()) / len(port_statuses)
        if composite_score >= 0.70:
            comp_sev = DisruptionSeverity.CRITICAL
        elif composite_score >= 0.50:
            comp_sev = DisruptionSeverity.SEVERE
        elif composite_score >= 0.35:
            comp_sev = DisruptionSeverity.ELEVATED
        elif composite_score >= 0.20:
            comp_sev = DisruptionSeverity.MODERATE
        else:
            comp_sev = DisruptionSeverity.LOW

        critical_events = [e for e in events if e.severity in [DisruptionSeverity.CRITICAL, DisruptionSeverity.SEVERE, DisruptionSeverity.ELEVATED]]

        feature_vector = {
            'feat_disruption_east_coast_composite': round(composite_score, 4),
            'feat_disruption_paradip': port_statuses['IN_PRT'].disruption_score,
            'feat_disruption_vizag_outer': port_statuses['IN_VTZ_OUTER'].disruption_score,
            'feat_disruption_haldia': port_statuses['IN_HLD'].disruption_score,
            'feat_disruption_dhamra': port_statuses['IN_DHM'].disruption_score,
            'feat_cyclone_active_flag': 1.0 if any(e.category == DisruptionCategory.CYCLONE_MONSOON and e.severity_score >= 0.45 for e in events) else 0.0,
            'feat_strike_active_flag': 1.0 if any(e.category == DisruptionCategory.LABOR_STRIKE and e.severity_score >= 0.45 for e in events) else 0.0,
            'feat_bunker_spike_flag': 1.0 if any(e.category == DisruptionCategory.GEOPOLITICAL_REGULATORY and e.severity_score >= 0.45 for e in events) else 0.0,
            'feat_waiting_time_multiplier_paradip': port_statuses['IN_PRT'].waiting_time_multiplier,
            'feat_demurrage_risk_usd_mt_paradip': port_statuses['IN_PRT'].demurrage_risk_premium_usd_mt
        }

        return DailyDisruptionReport(
            as_of_date=as_of_date,
            composite_east_coast_score=round(composite_score, 4),
            composite_severity=comp_sev,
            port_statuses=port_statuses,
            critical_events=critical_events,
            feature_vector=feature_vector
        )
