"""Regression tests for the three-school GCJ-02 coordinate catalog."""
import importlib.util
from pathlib import Path

from app.data.demo_coordinates import COORDINATE_SYSTEM, DEMO_SCHOOL_COORDINATES


EXPECTED_COUNTS = {"jiangnan": 15, "fudan": 12, "zju": 12}


def test_coordinate_catalog_is_complete_and_gcj02():
    assert COORDINATE_SYSTEM == "GCJ-02"
    assert set(DEMO_SCHOOL_COORDINATES) == set(EXPECTED_COUNTS)
    assert {
        code: len(data["locations"])
        for code, data in DEMO_SCHOOL_COORDINATES.items()
    } == EXPECTED_COUNTS


def test_coordinates_are_unique_valid_and_inside_each_campus():
    for code, school in DEMO_SCHOOL_COORDINATES.items():
        south, north, west, east = school["bounds"]
        assert south <= school["center_lat"] <= north, code
        assert west <= school["center_lng"] <= east, code

        names = [item["name"] for item in school["locations"]]
        assert len(names) == len(set(names)), code
        for item in school["locations"]:
            assert -90 <= item["latitude"] <= 90
            assert -180 <= item["longitude"] <= 180
            assert south <= item["latitude"] <= north, f"{code}/{item['name']} latitude"
            assert west <= item["longitude"] <= east, f"{code}/{item['name']} longitude"
            assert item["quality"] in {"amap_poi", "demo_approximate"}
            assert item["source"]
            if item["quality"] == "amap_poi":
                assert item["source"].startswith("https://ditu.amap.com/place/")


def test_migration_snapshot_matches_catalog():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "c8d9e0f1a2b3_gcj02_demo_coordinates.py"
    )
    spec = importlib.util.spec_from_file_location("gcj02_demo_coordinates_migration", migration_path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert len(migration.SCHOOL_COORDINATES) == 3
    assert len(migration.LOCATION_COORDINATES) == 39

    migrated = {
        (code, name): (new_lat, new_lng)
        for code, name, _old_lat, _old_lng, new_lat, new_lng in migration.LOCATION_COORDINATES
    }
    expected = {
        (code, item["name"]): (item["latitude"], item["longitude"])
        for code, school in DEMO_SCHOOL_COORDINATES.items()
        for item in school["locations"]
    }
    assert migrated == expected
