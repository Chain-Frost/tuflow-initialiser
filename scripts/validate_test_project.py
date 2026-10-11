"""Reproduce the shared real-DEM integration run using installed GRASS/TUFLOW."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import rasterio
from verify_project import verify_project

from tuflow_initialiser.workflow import BuildConfig, build


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grass-exe", required=True)
    parser.add_argument("--tuflow-exe", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    fixture = Path(__file__).resolve().parents[1] / "test_data"
    manifest = json.loads((fixture / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["sha256"].items():
        with (fixture / name).open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise ValueError(f"Shared fixture checksum mismatch: {name}")
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Existing output is protected: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Derive the projection from the tracked GeoTIFF; no local .prj is required.
    with rasterio.open(fixture / "dem_epsg28350.tif") as dem:
        if dem.crs is None or dem.crs.to_epsg() != 28350:
            raise ValueError("Shared DEM must declare EPSG:28350")
        wkt = dem.crs.to_wkt()
    projection = output.parent / f"{output.name}_projection.prj"
    with projection.open("x", encoding="utf-8") as stream:
        stream.write(wkt)
    started = time.perf_counter()
    build(
        BuildConfig(
            terrains=(fixture / "dem_epsg28350.tif",),
            aoi=fixture / "region.gpkg",
            output=output,
            name="RealDEM",
            scenario="EXG",
            prj=projection,
            tuflow_executable=args.tuflow_exe.resolve(),
            rainfall_name="RF01",
            grass_executable=args.grass_exe,
        )
    )
    report = verify_project(output)
    report["build_and_verification_seconds"] = time.perf_counter() - started
    report["fixture_sha256"] = manifest["sha256"]
    report["tools"] = {
        "grass_executable": args.grass_exe,
        "tuflow_executable": str(args.tuflow_exe.resolve()),
    }
    (output / "qa.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
