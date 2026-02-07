import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ui.parsers import estimated_runtime_seconds, parse_zones_text, zones_to_text


def test_parse_zones_text_parses_valid_lines():
    raw = "area_a,10,20,200,300\narea_b,300,400,500,600"

    zones, warnings = parse_zones_text(raw)

    assert len(zones) == 2
    assert warnings == []
    assert zones[0]["name"] == "area_a"
    assert zones[1]["x2"] == 500


def test_parse_zones_text_normalizes_inverted_coordinates():
    raw = "gate,300,400,100,80"

    zones, warnings = parse_zones_text(raw)

    assert len(zones) == 1
    assert zones[0]["x1"] == 100
    assert zones[0]["x2"] == 300
    assert zones[0]["y1"] == 80
    assert zones[0]["y2"] == 400
    assert len(warnings) >= 2


def test_parse_zones_text_handles_invalid_lines():
    raw = "bad-line\nzone,10,10,10,50\n,1,2,3,4"

    zones, warnings = parse_zones_text(raw)

    assert zones == []
    assert len(warnings) == 3


def test_zones_to_text_round_trip():
    zones = [{"name": "alpha", "x1": 1, "y1": 2, "x2": 3, "y2": 4}]

    text = zones_to_text(zones)

    assert text == "alpha,1,2,3,4"


def test_estimated_runtime_seconds():
    assert estimated_runtime_seconds(300, 30) == 10.0
    assert estimated_runtime_seconds(100, 0) == 0.0
