"""What we ask the LLM to find, and the JSON shape it must answer in."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Field:
    name: str
    kind: str  # "pct", "margin", "count", "direction"
    ask: str  # plain-English instruction for the LLM


CORE_FIELDS = [
    Field("comp_sales_pct", "pct",
          "Comparable (same-store / same-restaurant) sales growth % for the quarter, for the segment named above."),
    Field("comp_traffic_pct", "pct",
          "Comparable traffic / transactions / guest count growth % for the quarter (the customer-count part of comps)."),
    Field("comp_ticket_pct", "pct",
          "Average check / average ticket / basket growth % for the quarter, OR the combined price+mix % if that is how it is reported."),
    Field("ending_units", "count",
          "Number of stores or restaurants open at the end of the quarter, for the segment named above."),
    Field("margin_pct", "margin",
          "Restaurants: restaurant-level margin as a % of restaurant sales. Retailers: gross margin (gross profit rate) as a % of sales. For the quarter."),
]

WATCH_FIELDS = [
    Field("comp_sales_pct", "pct", "Comparable (same-store) sales growth % for the quarter."),
    Field("traffic_direction", "direction",
          "Did comparable traffic / transactions go up, down or stay flat? Answer only if the text says so in words or numbers."),
    Field("ticket_direction", "direction",
          "Did average ticket / check / price+mix go up, down or stay flat? Answer only if the text says so in words or numbers."),
]

SOURCES = ["press_release", "periodic"]
DIRECTIONS = ["up", "down", "flat"]


def fields_for(tier: str) -> list[Field]:
    return CORE_FIELDS if tier == "core" else WATCH_FIELDS


def json_schema(fields: list[Field]) -> dict:
    """Strict JSON schema: every field present; unknown = all nulls."""
    props = {}
    for f in fields:
        # Enums are checked in Python (verify.py); some providers reject enum + null.
        value = (
            {"type": ["string", "null"], "description": "one of: up, down, flat"}
            if f.kind == "direction"
            else {"type": ["number", "null"]}
        )
        props[f.name] = {
            "type": "object",
            "properties": {
                "value": value,
                "quote": {"type": ["string", "null"]},
                "source": {"type": ["string", "null"], "description": "press_release or periodic"},
            },
            "required": ["value", "quote", "source"],
            "additionalProperties": False,
        }
    return {
        "type": "object",
        "properties": props,
        "required": [f.name for f in fields],
        "additionalProperties": False,
    }
