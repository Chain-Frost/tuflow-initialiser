"""Reopen real-system outputs and retain machine-readable QA evidence."""

import math
from pathlib import Path

import fiona
import numpy as np
import rasterio
from rasterio.features import rasterize
from shapely.geometry import shape
from shapely.ops import unary_union

from tuflow_initialiser.project_setup import _read_fiona_schema


def verify_project(project: Path) -> dict:
    """Verify the fixed EXG/RF01 integration-test project after reopening outputs."""
    report = {"layers": {}}
    geometries = {}
    for name in ("2d_code", "2d_rf", "2d_loc"):
        path = project / "model/gis/EXG" / f"{name}_EXG_01_R.gpkg"
        with fiona.open(path) as src:
            features = list(src)
            assert src.crs.to_epsg() == 28350
            assert features
            assert all(shape(f.geometry).is_valid for f in features)
            geometries[name] = unary_union([shape(f.geometry) for f in features])
            canonical = _read_fiona_schema(
                source_path=project / "empty" / f"{name}_empty.gpkg",
                source_layer=f"{name}_empty_R",
            )
            assert src.schema == canonical
            report["layers"][name] = {
                "features": len(features),
                "area_km2": geometries[name].area / 1e6,
                "schema": src.schema,
            }
            if name == "2d_code":
                assert all(f.properties["Code"] == 1 for f in features)
            if name == "2d_rf":
                assert all(
                    f.properties["Name"] == "RF01" and f.properties["f1"] == 1
                    for f in features
                )
    assert geometries["2d_code"].equals(geometries["2d_rf"])
    assert geometries["2d_loc"].covers(geometries["2d_code"])
    with fiona.open(project / "model/gis/hydrology.gpkg", layer="aoi") as src:
        aoi = unary_union([shape(f.geometry) for f in src])
    assert geometries["2d_code"].covers(aoi)
    with fiona.open(
        project / "model/gis/hydrology.gpkg", layer="contributing_area"
    ) as src:
        contributing = unary_union([shape(f.geometry) for f in src])
    report["contributing_area_km2"] = contributing.area / 1e6
    with rasterio.open(project / "terrain/hydrology/analysis_dem.tif") as src:
        pixels = rasterize(
            [(geometries["2d_code"], 1)],
            out_shape=src.shape,
            transform=src.transform,
            all_touched=True,
        ).astype(bool)
        dem = src.read(1, masked=True)
        assert not np.any(np.ma.getmaskarray(dem)[pixels])
        assert np.all(np.isfinite(dem.data[pixels]))
        report["analysis_grid"] = {
            "shape": list(src.shape),
            "resolution_m": list(src.res),
            "active_elevation_range_m": [
                float(dem[pixels].min()),
                float(dem[pixels].max()),
            ],
        }
    with fiona.open(project / "model/gis/streams.gpkg") as src:
        rows = list(src)
        assert rows
        assert all(
            shape(f.geometry).is_valid
            and f.properties["length_m"] > 0
            and math.isfinite(f.properties["slope_ea"])
            for f in rows
        )
        report["streams"] = {
            "features": len(rows),
            "channels": sum(f.properties["path_type"] == "channel" for f in rows),
            "synthetic_headwaters": sum(
                f.properties["path_type"] == "synthetic_headwater" for f in rows
            ),
            "negative_slopes": sum(f.properties["slope_ea"] < 0 for f in rows),
        }
    return report
