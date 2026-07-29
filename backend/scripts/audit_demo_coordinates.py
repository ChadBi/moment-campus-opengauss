"""Read-only audit for the three-school GCJ-02 demo coordinate catalog."""
import argparse
import asyncio
import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select


backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.data.demo_coordinates import COORDINATE_SYSTEM, DEMO_SCHOOL_COORDINATES  # noqa: E402
from app.database import async_session_maker, engine  # noqa: E402
from app.models.location import Location  # noqa: E402
from app.models.school import School  # noqa: E402


def _close(actual: float | Decimal | None, expected: float) -> bool:
    return actual is not None and abs(float(actual) - expected) <= 0.0000001


async def audit(strict: bool) -> int:
    issues: list[str] = []
    warnings: list[str] = []
    async with async_session_maker() as session:
        schools = {
            school.code: school
            for school in (await session.execute(select(School))).scalars().all()
        }
        for code, expected in DEMO_SCHOOL_COORDINATES.items():
            school = schools.get(code)
            if not school:
                issues.append(f"{code}: school missing")
                continue
            if not _close(school.center_lat, expected["center_lat"]) or not _close(
                school.center_lng, expected["center_lng"]
            ):
                issues.append(
                    f"{code}: center mismatch actual=({school.center_lat},{school.center_lng}) "
                    f"expected=({expected['center_lat']},{expected['center_lng']})"
                )

            locations = (
                await session.execute(select(Location).where(Location.school_id == school.id))
            ).scalars().all()
            by_name = {location.name: location for location in locations}
            for item in expected["locations"]:
                location = by_name.get(item["name"])
                if not location:
                    issues.append(f"{code}/{item['name']}: location missing")
                    continue
                if not _close(location.latitude, item["latitude"]) or not _close(
                    location.longitude, item["longitude"]
                ):
                    issues.append(
                        f"{code}/{item['name']}: mismatch actual=({location.latitude},{location.longitude}) "
                        f"expected=({item['latitude']},{item['longitude']})"
                    )

            south, north, west, east = expected["bounds"]
            demo_names = {item["name"] for item in expected["locations"]}
            for location in locations:
                lat = float(location.latitude)
                lng = float(location.longitude)
                if location.name not in demo_names and not (south <= lat <= north and west <= lng <= east):
                    warnings.append(
                        f"{code}/{location.name}: non-demo location outside campus bounds ({lat},{lng})"
                    )

    print(f"Coordinate system: {COORDINATE_SYSTEM}")
    print(f"Catalog: {sum(len(v['locations']) for v in DEMO_SCHOOL_COORDINATES.values())} locations")
    for warning in warnings:
        print(f"WARNING: {warning}")
    for issue in issues:
        print(f"ERROR: {issue}")
    await engine.dispose()
    return 1 if issues or (strict and warnings) else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="Treat non-demo outliers as failures")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(audit(args.strict)))


if __name__ == "__main__":
    main()
