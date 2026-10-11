import pytest

from custom_components.local_daikin.dsiot import (
    INDOOR,
    OUTDOOR,
    compressor_load_percent,
    decode_max,
    decode_number,
    extract_diagnostics,
    find_param,
    step_from_st,
)


@pytest.mark.parametrize(
    "st, expected",
    [(245, 0.5), (241, 0.1), (225, 0.01), (17, 10), (2, 2), (1, 1), (0, None)],
)
def test_step_from_st(st, expected):
    if expected is None:
        assert step_from_st(st) is None
    else:
        assert step_from_st(st) == pytest.approx(expected)


EXPECTED = {
    "dump_cool.json": {
        "compressor_frequency": 112,
        "compressor_running": True,
        "power": 2500,
        "current": 10.0,
        "supply_voltage": 236,
        "indoor_fan_speed": 1060,
        "indoor_fan_speed_max": 1350,
        "outdoor_fan_speed": 970,
        "outdoor_fan_speed_max": 1500,
        "indoor_coil_temp": 7.0,
        "outdoor_coil_temp": 47.0,
        "control_target_temp": 22.0,
        "eev_position": 372,
        "powerful": False,
        "room_temp_precise": 25.5,
        "outside_temp": 32.5,
    },
    "dump_powerful.json": {
        "compressor_frequency": 92,
        "compressor_running": True,
        "power": 2010,
        "current": 8.2,
        "supply_voltage": 238,
        "indoor_fan_speed": 1290,
        "indoor_fan_speed_max": 1350,
        "outdoor_fan_speed": 970,
        "outdoor_fan_speed_max": 1500,
        "indoor_coil_temp": 10.0,
        "outdoor_coil_temp": 45.0,
        "control_target_temp": 16.0,
        "eev_position": 340,
        "powerful": True,
        "room_temp_precise": 26.0,
        "outside_temp": 32.0,
    },
}


@pytest.mark.parametrize("dump", sorted(EXPECTED))
def test_extract_diagnostics(load_dump, dump):
    assert extract_diagnostics(load_dump(dump)) == EXPECTED[dump]


def test_missing_path_returns_none(load_dump):
    data = load_dump("dump_cool.json")
    assert find_param(data, OUTDOOR, "e_1003", "e_9999", "p_01") is None
    assert find_param(data, "adr_0300.dgc_status", "e_1003") is None
    assert decode_number(None) is None
    assert decode_max(None) is None


def test_null_pv_returns_none(load_dump):
    node = find_param(load_dump("dump_cool.json"), OUTDOOR, "e_1003", "e_A001", "p_01")
    assert node is not None and node["pv"] is None
    assert decode_number(node) is None


def test_garbage_input_returns_all_none():
    for data in ({}, {"responses": None}, {"responses": [{"fr": None}]}, None, []):
        assert set(extract_diagnostics(data).values()) == {None}


def test_negative_little_endian():
    node = {"pv": "C0FF", "md": {"st": 245}}
    assert decode_number(node) == -32.0


def test_non_numeric_st_is_not_scaled():
    assert decode_number({"pv": "0200", "md": {"st": 0}}) is None


def test_duplicate_entity_names_are_all_searched():
    data = {
        "responses": [
            {
                "fr": "/dsiot/edge/" + INDOOR,
                "pc": {
                    "pn": "dgc_status",
                    "pch": [
                        {
                            "pn": "e_1002",
                            "pch": [
                                {"pn": "e_2015", "pch": [{"pn": "p_02", "pv": "01", "md": {"st": 1}}]},
                                {"pn": "e_2015", "pch": [{"pn": "p_09", "pv": "0500", "md": {"st": 1}}]},
                            ],
                        }
                    ],
                },
            }
        ]
    }
    assert decode_number(find_param(data, INDOOR, "e_1002", "e_2015", "p_09")) == 5


def test_compressor_load_is_not_clamped():
    assert compressor_load_percent(112) == 112.0
    assert compressor_load_percent(None) is None
