"""Decoding helpers for the Daikin dsiot (`/dsiot/multireq`) protocol.

Kept free of Home Assistant imports so it can be unit tested with plain pytest.

Values (`pv`) are little-endian, signed hex strings. The metadata field `md.st`
is a one-byte step multiplier: the high nibble is a signed 4-bit power of ten,
the low nibble is the mantissa (0xF5 -> 5 * 10^-1 = 0.5). `st == 0` marks a
non-numeric value (enum, bitmask, ASCII) that must not be scaled.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Tuple

_LOGGER = logging.getLogger(__name__)

INDOOR = "adr_0100.dgc_status"
OUTDOOR = "adr_0200.dgc_status"

# The unit itself treats this as roughly 100% load; it may briefly exceed it.
COMPRESSOR_NOMINAL_MAX_HZ = 100


def _split_st(st: Any) -> Optional[Tuple[int, int]]:
    """Return (mantissa, exponent) for a step byte, or None if not numeric."""
    if not isinstance(st, int) or isinstance(st, bool) or not 0 < st <= 0xFF:
        return None
    mantissa = st & 0x0F
    if mantissa == 0:
        return None
    exponent = st >> 4
    if exponent >= 8:
        exponent -= 16
    return mantissa, exponent


def step_from_st(st: Any) -> Optional[float]:
    """Return the multiplier encoded in `md.st` (None for non-numeric values)."""
    split = _split_st(st)
    if split is None:
        return None
    mantissa, exponent = split
    return mantissa * 10 ** exponent


def _scale(raw: int, st: Any) -> Optional[float]:
    split = _split_st(st)
    if split is None:
        return None
    mantissa, exponent = split
    if exponent >= 0:
        return raw * mantissa * 10 ** exponent
    # Divide instead of multiplying by 0.1 etc. to avoid 8.200000000000001.
    return round(raw * mantissa / 10 ** -exponent, -exponent)


def _le_signed(value: Any) -> Optional[int]:
    if not isinstance(value, str) or not value or len(value) % 2:
        return None
    try:
        return int.from_bytes(bytes.fromhex(value), "little", signed=True)
    except ValueError:
        return None


def _descend(children: Any, path: Tuple[str, ...]) -> Optional[dict]:
    # Entity names can repeat (e.g. e_2015 twice), so try every match.
    if not isinstance(children, list):
        return None
    name, rest = path[0], path[1:]
    for child in children:
        if not isinstance(child, dict) or child.get("pn") != name:
            continue
        if not rest:
            return child
        found = _descend(child.get("pch"), rest)
        if found is not None:
            return found
    return None


def find_param(data: Any, resource_suffix: str, *path: str) -> Optional[dict]:
    """Return the leaf node (`pv` + `md`) at `path` under the matching resource.

    `resource_suffix` is e.g. "adr_0200.dgc_status"; `path` starts below the
    resource's `dgc_status` node, e.g. ("e_1003", "e_2006", "p_04").
    """
    if not isinstance(data, dict) or not path:
        return None
    for response in data.get("responses") or []:
        if not isinstance(response, dict):
            continue
        fr = str(response.get("fr") or "").split("?", 1)[0]
        if fr != resource_suffix and not fr.endswith("/" + resource_suffix):
            continue
        pc = response.get("pc")
        if not isinstance(pc, dict):
            continue
        node = _descend(pc.get("pch"), path)
        if node is not None:
            return node
    return None


def _md(node: Optional[dict]) -> dict:
    md = node.get("md") if isinstance(node, dict) else None
    return md if isinstance(md, dict) else {}


def decode_number(node: Optional[dict]) -> Optional[float]:
    """Decode `pv` as a little-endian signed value scaled by `md.st`."""
    if not isinstance(node, dict):
        return None
    raw = _le_signed(node.get("pv"))
    if raw is None:
        return None
    return _scale(raw, _md(node).get("st"))


def decode_max(node: Optional[dict]) -> Optional[float]:
    """Decode `md.mx` (the model's supported maximum) the same way as `pv`."""
    md = _md(node)
    raw = _le_signed(md.get("mx"))
    if raw is None:
        return None
    return _scale(raw, md.get("st"))


def decode_flag(node: Optional[dict]) -> Optional[bool]:
    """Decode a 0/1 flag such as "01"."""
    if not isinstance(node, dict):
        return None
    raw = _le_signed(node.get("pv"))
    if raw is None:
        return None
    return raw != 0


# key -> (resource, path below dgc_status, decoder)
DIAGNOSTIC_PARAMS = {
    "compressor_frequency": (OUTDOOR, ("e_1003", "e_2006", "p_04"), decode_number),
    "compressor_running": (OUTDOOR, ("e_1003", "e_2006", "p_01"), decode_flag),
    "power": (OUTDOOR, ("e_1003", "e_A005", "p_01"), decode_number),
    "current": (OUTDOOR, ("e_1003", "e_A005", "p_02"), decode_number),
    "supply_voltage": (OUTDOOR, ("e_1003", "e_A005", "p_09"), decode_number),
    "indoor_fan_speed": (INDOOR, ("e_1002", "e_2028", "p_04"), decode_number),
    "indoor_fan_speed_max": (INDOOR, ("e_1002", "e_2028", "p_04"), decode_max),
    "outdoor_fan_speed": (OUTDOOR, ("e_1003", "e_2008", "p_01"), decode_number),
    "outdoor_fan_speed_max": (OUTDOOR, ("e_1003", "e_2008", "p_01"), decode_max),
    "indoor_coil_temp": (INDOOR, ("e_1002", "e_2029", "p_02"), decode_number),
    "outdoor_coil_temp": (OUTDOOR, ("e_1003", "e_2009", "p_02"), decode_number),
    "control_target_temp": (INDOOR, ("e_1002", "e_3003", "p_0C"), decode_number),
    "eev_position": (OUTDOOR, ("e_1003", "e_2005", "p_01"), decode_number),
    "powerful": (OUTDOOR, ("e_1003", "e_3002", "p_44"), decode_flag),
    "room_temp_precise": (INDOOR, ("e_1002", "e_A00B", "p_06"), decode_number),
    "outside_temp": (OUTDOOR, ("e_1003", "e_A00D", "p_01"), decode_number),
}


def extract_diagnostics(data: Any) -> dict:
    """Return every DIAGNOSTIC_PARAMS key; values missing on this model are None."""
    result = {}
    for key, (resource, path, decoder) in DIAGNOSTIC_PARAMS.items():
        value = decoder(find_param(data, resource, *path))
        if value is None:
            _LOGGER.debug("dsiot: no value for %s (%s %s)", key, resource, "/".join(path))
        result[key] = value
    return result


def compressor_load_percent(frequency: Optional[float]) -> Optional[float]:
    """Compressor frequency as % of COMPRESSOR_NOMINAL_MAX_HZ (not clamped)."""
    if frequency is None:
        return None
    return round(frequency / COMPRESSOR_NOMINAL_MAX_HZ * 100, 1)


def percent_of(value: Optional[float], maximum: Optional[float]) -> Optional[float]:
    if value is None or not maximum:
        return None
    return round(value / maximum * 100, 1)


@dataclass
class DaikinAttribute:
    name: str
    value: float
    path: list[str]
    to: str

    def format(self) -> str:
        return {"pn": self.name, "pv": self.value}


@dataclass
class DaikinRequest:
    attributes: list[DaikinAttribute] = field(default_factory=list)


    def serialize(self, payload=None) -> dict:
        if payload is None:
            payload = {
                'requests' : []
            }

        def get_existing_index(name: str, children: list[dict]) -> int:
            for index, child in enumerate(children):
                if child.get("pn") == name:
                    return index
            return -1
        
        def get_existing_to(to: str, requests: list[dict]) -> bool:
            for request in requests:
                this_to = request.get("to")
                if this_to == to:
                    return request
            return None

        for attribute in self.attributes:
            to = get_existing_to(attribute.to, payload['requests'])
            if to is None:
                payload['requests'].append({
                    'op': 3,
                    'pc' : {
                        "pn" : "dgc_status",
                        "pch" : []
                    },
                    "to": attribute.to
                })
                to = payload['requests'][-1]
            entry = to['pc']['pch']
            for pn in attribute.path:
                index = get_existing_index(pn, entry)
                if index == -1:
                    entry.append({"pn": pn, "pch": []})
                entry = entry[-1]['pch']
            entry.append(attribute.format())
        return payload


def powerful_request(enabled: bool) -> dict:
    """Payload toggling Powerful mode (outdoor e_3002/p_44)."""
    attribute = DaikinAttribute(
        "p_44", "01" if enabled else "00", ["e_1003", "e_3002"], "/dsiot/edge/" + OUTDOOR
    )
    return DaikinRequest([attribute]).serialize()
