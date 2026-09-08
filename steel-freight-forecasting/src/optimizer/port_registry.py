import json
from pathlib import Path
from typing import Dict, List, Optional
from src.schemas.port_models import PortInfrastructure, PortType, VesselClass, VesselSpecification

# Standard Bulk Carrier Specs
VESSEL_SPECS: Dict[VesselClass, VesselSpecification] = {
    VesselClass.HANDYSIZE: VesselSpecification(
        class_name=VesselClass.HANDYSIZE,
        min_dwt=28000,
        max_dwt=39000,
        nominal_cargo_intake_mt=35000,
        laden_draft_meters=10.0,
        ballast_draft_meters=6.2,
        length_overall_loa_meters=180.0,
        beam_meters=28.5,
        geared=True,
        fuel_consumption_sea_mt_day=18.0,
        fuel_consumption_port_mt_day=3.0,
        standard_charter_hire_baseline_usd_day=13500.0
    ),
    VesselClass.SUPRAMAX: VesselSpecification(
        class_name=VesselClass.SUPRAMAX,
        min_dwt=50000,
        max_dwt=64000,
        nominal_cargo_intake_mt=58000,
        laden_draft_meters=12.8,
        ballast_draft_meters=7.1,
        length_overall_loa_meters=190.0,
        beam_meters=32.26,
        geared=True,
        fuel_consumption_sea_mt_day=24.0,
        fuel_consumption_port_mt_day=4.0,
        standard_charter_hire_baseline_usd_day=17000.0
    ),
    VesselClass.PANAMAX: VesselSpecification(
        class_name=VesselClass.PANAMAX,
        min_dwt=70000,
        max_dwt=85000,
        nominal_cargo_intake_mt=78000,
        laden_draft_meters=14.5,
        ballast_draft_meters=7.8,
        length_overall_loa_meters=229.0,
        beam_meters=32.26,
        geared=False,
        fuel_consumption_sea_mt_day=28.0,
        fuel_consumption_port_mt_day=4.5,
        standard_charter_hire_baseline_usd_day=20500.0
    ),
    VesselClass.CAPESIZE: VesselSpecification(
        class_name=VesselClass.CAPESIZE,
        min_dwt=150000,
        max_dwt=210000,
        nominal_cargo_intake_mt=175000,
        laden_draft_meters=18.2,
        ballast_draft_meters=8.8,
        length_overall_loa_meters=292.0,
        beam_meters=45.0,
        geared=False,
        fuel_consumption_sea_mt_day=42.0,
        fuel_consumption_port_mt_day=6.0,
        standard_charter_hire_baseline_usd_day=24500.0
    )
}

class PortRegistry:
    def __init__(self, data_path: Optional[str] = None):
        if data_path is None:
            # Default to data/port_specifications.json relative to project root
            base_dir = Path(__file__).resolve().parent.parent.parent
            data_path = str(base_dir / 'data' / 'port_specifications.json')
            
        with open(data_path, 'r') as f:
            data = json.load(f)
            
        self.ports: Dict[str, PortInfrastructure] = {}
        for p in data['indian_discharge_ports']:
            port = PortInfrastructure(**p)
            self.ports[port.port_id] = port
            
        for p in data['global_loading_ports']:
            port = PortInfrastructure(**p)
            self.ports[port.port_id] = port

    def get_port(self, port_id: str) -> Optional[PortInfrastructure]:
        return self.ports.get(port_id)

    def get_indian_discharge_ports(self) -> List[PortInfrastructure]:
        return [p for p in self.ports.values() if p.port_type == PortType.DISCHARGE]

    def get_loading_ports(self) -> List[PortInfrastructure]:
        return [p for p in self.ports.values() if p.port_type == PortType.LOADING]

    def get_vessel_spec(self, v_class: VesselClass) -> VesselSpecification:
        return VESSEL_SPECS[v_class]
