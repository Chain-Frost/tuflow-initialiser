"""Catchment-only workflow and resilient vector input checks."""

import sqlite3
from pathlib import Path

import fiona
from rasterio.crs import CRS
from shapely.geometry import LineString, mapping

from tuflow_initialiser.catchment_workflow import _fiona_features


def test_line_interest_with_stale_geopackage_count_is_read(tmp_path: Path) -> None:
    path = tmp_path / "road.gpkg"
    schema: fiona.Schema = {"geometry": "LineString", "properties": {}}
    with fiona.open(
        path,
        "w",
        driver="GPKG",
        layer="road",
        schema=schema,
        crs_wkt=CRS.from_epsg(28351).to_wkt(),
    ) as output:
        output.write({"geometry": mapping(LineString([(0, 0), (10, 10)])), "properties": {}})
    with sqlite3.connect(path) as database:
        database.execute("UPDATE gpkg_ogr_contents SET feature_count = 0 WHERE table_name = 'road'")
        database.commit()

    crs, geometries = _fiona_features(path)

    assert crs == CRS.from_epsg(28351)
    assert len(geometries) == 1
    assert geometries[0].equals(LineString([(0, 0), (10, 10)]))
