"""Mock grid-operations tools.

These are PLACEHOLDER implementations that return synthetic data so the harness
is complete and runnable end-to-end. Each one represents a real integration
that would be backed by an MCP server or API in production (see mcp_config.json
for where those servers plug in). Swap the body of each function — or replace it
with a real MCP client call — without changing the agent wiring.

Every tool returns a `source` and `timestamp` so the model can cite provenance,
per the grid-ops system prompt.
"""

from datetime import datetime, timezone
from typing import Any, Dict

from strands import tool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@tool
def get_scada_telemetry(substation_id: str) -> Dict[str, Any]:
    """Return latest SCADA/EMS telemetry for a substation.

    Args:
        substation_id: Substation identifier, e.g. "SUB-4471".

    MOCK: replace with a real SCADA/EMS MCP server or historian query.
    """
    return {
        "source": "MOCK:scada-ems",
        "timestamp": _now(),
        "substation_id": substation_id,
        "bus_voltage_kv": 138.2,
        "frequency_hz": 59.98,
        "real_power_mw": 812.4,
        "reactive_power_mvar": 143.7,
        "breaker_status": "CLOSED",
        "note": "Synthetic data — not from a real historian.",
    }


@tool
def get_active_outages(region: str) -> Dict[str, Any]:
    """List active outages and affected customer counts for a region.

    Args:
        region: Operating region or feeder group, e.g. "NORTH-3".

    MOCK: replace with a real Outage Management System (OMS) MCP server.
    """
    return {
        "source": "MOCK:oms",
        "timestamp": _now(),
        "region": region,
        "outages": [
            {
                "outage_id": "OMS-20260922-0012",
                "feeder": "FDR-2231",
                "customers_affected": 1840,
                "cause": "SUSPECTED_LINE_FAULT",
                "crew_dispatched": True,
                "eta_restore_min": 95,
            }
        ],
        "note": "Synthetic data.",
    }


@tool
def get_iso_market_snapshot(iso: str, node: str) -> Dict[str, Any]:
    """Return an ISO/RTO market snapshot (LMP, load, reserves) for a node.

    Args:
        iso: ISO/RTO, e.g. "CAISO", "PJM", "ERCOT".
        node: Pricing node / hub identifier.

    MOCK: replace with a real ISO/RTO market-data MCP server.
    """
    return {
        "source": f"MOCK:{iso.lower()}-market",
        "timestamp": _now(),
        "iso": iso,
        "node": node,
        "lmp_usd_mwh": 41.63,
        "system_load_mw": 32450,
        "operating_reserves_mw": 2810,
        "note": "Synthetic data.",
    }


@tool
def get_load_forecast(region: str, hours_ahead: int = 24) -> Dict[str, Any]:
    """Return an hourly load forecast for a region.

    Args:
        region: Operating region.
        hours_ahead: Forecast horizon in hours (default 24).

    MOCK: replace with a real forecasting service / weather-driven model.
    """
    base = 900.0
    forecast = [
        {"hour": h, "forecast_mw": round(base + 120 * (h % 12) / 12.0, 1)}
        for h in range(1, hours_ahead + 1)
    ]
    return {
        "source": "MOCK:load-forecast",
        "timestamp": _now(),
        "region": region,
        "hours_ahead": hours_ahead,
        "forecast": forecast,
        "note": "Synthetic data.",
    }


@tool
def get_weather(latitude: float, longitude: float) -> Dict[str, Any]:
    """Return current weather relevant to demand and grid stress.

    Args:
        latitude: Decimal degrees.
        longitude: Decimal degrees.

    MOCK: replace with a real weather MCP server / NWS API.
    """
    return {
        "source": "MOCK:weather",
        "timestamp": _now(),
        "latitude": latitude,
        "longitude": longitude,
        "temp_c": 34.5,
        "wind_kph": 22.0,
        "conditions": "HOT_CLEAR",
        "heat_advisory": True,
        "note": "Synthetic data.",
    }


@tool
def create_work_order(feeder: str, description: str, priority: str) -> Dict[str, Any]:
    """Draft a work order for human review (does NOT auto-execute).

    Args:
        feeder: Affected feeder / asset identifier.
        description: What needs to be done.
        priority: One of LOW, MEDIUM, HIGH, EMERGENCY.

    MOCK: replace with a real work-order / asset-management MCP server.
    Returns a DRAFT only; a qualified operator must approve and submit.
    """
    return {
        "source": "MOCK:work-order",
        "timestamp": _now(),
        "status": "DRAFT_PENDING_OPERATOR_APPROVAL",
        "work_order": {
            "feeder": feeder,
            "description": description,
            "priority": priority,
        },
        "note": "Draft only — not submitted. Requires operator approval.",
    }


# Registry consumed by agent.py.
GRID_TOOLS = [
    get_scada_telemetry,
    get_active_outages,
    get_iso_market_snapshot,
    get_load_forecast,
    get_weather,
    create_work_order,
]
