"""Mock plant-operations tools.

These are PLACEHOLDER implementations that return synthetic data so the harness
is complete and runnable end-to-end. Each one represents a real integration
that would be backed by an MCP server or API in production (see mcp_config.json
for where those servers plug in). Swap the body of each function — or replace it
with a real MCP client call — without changing the agent wiring.

Every tool returns a `source` and `timestamp` so the model can cite provenance,
per the plant-ops system prompt.
"""

from datetime import datetime, timezone
from typing import Any, Dict

from strands import tool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@tool
def get_line_oee(line_id: str, shift: str = "current") -> Dict[str, Any]:
    """Return OEE metrics (availability, performance, quality) for a line.

    Args:
        line_id: Production line identifier, e.g. "BODY-2".
        shift: "current", "A", "B", or "C".

    MOCK: replace with a real MES / OEE-platform MCP server.
    """
    return {
        "source": "MOCK:mes-oee",
        "timestamp": _now(),
        "line_id": line_id,
        "shift": shift,
        "availability_pct": 92.1,
        "performance_pct": 88.4,
        "quality_pct": 99.3,
        "oee_pct": 80.8,
        "target_oee_pct": 85.0,
        "units_produced": 412,
        "target_units": 460,
        "note": "Synthetic data — not from a real MES.",
    }


@tool
def get_station_telemetry(station_id: str) -> Dict[str, Any]:
    """Return PLC/SCADA telemetry for a single assembly station.

    Args:
        station_id: Station identifier, e.g. "ST-BODY-14".

    MOCK: replace with a real PLC/SCADA/historian MCP server (OPC UA, Ignition).
    """
    return {
        "source": "MOCK:plc-historian",
        "timestamp": _now(),
        "station_id": station_id,
        "cycle_time_sec": 58.4,
        "target_cycle_time_sec": 55.0,
        "robot_status": "RUNNING",
        "torque_last_nm": 42.7,
        "torque_spec_nm": [41.0, 44.0],
        "andon_state": "GREEN",
        "note": "Synthetic data.",
    }


@tool
def get_defects(line_id: str, hours: int = 8) -> Dict[str, Any]:
    """List recent defects / non-conformances on a line.

    Args:
        line_id: Production line identifier.
        hours: Look-back window in hours (default 8, one shift).

    MOCK: replace with a real quality-management MCP server.
    """
    return {
        "source": "MOCK:quality-mgmt",
        "timestamp": _now(),
        "line_id": line_id,
        "hours": hours,
        "defects": [
            {
                "defect_id": "QN-20260924-0037",
                "vin": "1HGCM82633A123456",
                "station_id": "ST-BODY-14",
                "code": "WELD-UNDERFLOW",
                "severity": "MAJOR",
                "containment": "HOLD",
            },
            {
                "defect_id": "QN-20260924-0041",
                "vin": "1HGCM82633A123457",
                "station_id": "ST-PAINT-6",
                "code": "ORANGE-PEEL",
                "severity": "MINOR",
                "containment": "REWORK",
            },
        ],
        "defect_ppm": 340,
        "note": "Synthetic data.",
    }


@tool
def get_maintenance_signals(asset_id: str) -> Dict[str, Any]:
    """Return predictive-maintenance signals for an asset.

    Args:
        asset_id: Asset identifier, e.g. "ROBOT-BODY-14A" or "PRESS-4".

    MOCK: replace with a real predictive-maintenance MCP server (AWS Monitron,
    IoT SiteWise, vendor platform).
    """
    return {
        "source": "MOCK:predictive-maint",
        "timestamp": _now(),
        "asset_id": asset_id,
        "vibration_mm_s": 4.7,
        "vibration_baseline_mm_s": 2.1,
        "temp_c": 71.4,
        "temp_baseline_c": 58.0,
        "health_score": 62,
        "risk_level": "ELEVATED",
        "recommended_action": "SCHEDULE_INSPECTION_WITHIN_72H",
        "note": "Synthetic data.",
    }


@tool
def get_parts_supply(part_number: str) -> Dict[str, Any]:
    """Return JIT parts supply status and line-side inventory.

    Args:
        part_number: Part number / SKU.

    MOCK: replace with a real ERP / supplier-portal MCP server (SAP, Oracle).
    """
    return {
        "source": "MOCK:erp-jit",
        "timestamp": _now(),
        "part_number": part_number,
        "line_side_qty": 84,
        "hours_of_cover": 1.6,
        "reorder_point": 120,
        "in_transit_qty": 240,
        "next_delivery_eta": "2026-09-24T18:30:00Z",
        "supplier": "SUPPLIER-A17",
        "risk_level": "AT_RISK",
        "note": "Synthetic data.",
    }


@tool
def get_build_record(vin: str) -> Dict[str, Any]:
    """Return the build record and genealogy for a single VIN.

    Args:
        vin: 17-character Vehicle Identification Number.

    MOCK: replace with a real MES / traceability MCP server.
    """
    return {
        "source": "MOCK:mes-traceability",
        "timestamp": _now(),
        "vin": vin,
        "model": "MDL-X",
        "line_id": "BODY-2",
        "build_start": "2026-09-24T06:12:00Z",
        "stations_completed": ["ST-BODY-1", "ST-BODY-14", "ST-PAINT-6"],
        "torque_events": 47,
        "open_defects": ["QN-20260924-0037"],
        "note": "Synthetic data.",
    }


@tool
def create_work_order(
    asset_id: str, description: str, priority: str
) -> Dict[str, Any]:
    """Draft a maintenance work order for human review (does NOT auto-execute).

    Args:
        asset_id: Affected asset / station identifier.
        description: What needs to be done.
        priority: One of LOW, MEDIUM, HIGH, EMERGENCY.

    MOCK: replace with a real CMMS / EAM MCP server (SAP PM, Maximo).
    Returns a DRAFT only; a qualified planner must approve and submit.
    """
    return {
        "source": "MOCK:cmms",
        "timestamp": _now(),
        "status": "DRAFT_PENDING_PLANNER_APPROVAL",
        "work_order": {
            "asset_id": asset_id,
            "description": description,
            "priority": priority,
        },
        "note": "Draft only — not submitted. Requires planner approval.",
    }


# Registry consumed by agent.py.
PLANT_TOOLS = [
    get_line_oee,
    get_station_telemetry,
    get_defects,
    get_maintenance_signals,
    get_parts_supply,
    get_build_record,
    create_work_order,
]
