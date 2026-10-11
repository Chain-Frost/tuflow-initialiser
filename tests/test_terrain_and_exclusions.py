"""Regression tests for priority mosaics and exclusions.

Small synthetic rasters run without the GRASS or TUFLOW executables.
"""

from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_origin
from shapely.geometry import box

from tuflow_initialiser.geometry import make_domain
from tuflow_initialiser.terrain import compose_terrain


def _raster(path: Path, pixels: np.ndarray, *, west: float, north: float) -> None:
    with rasterio.open(
        path, mode="w", driver="GTiff", count=1,
        width=pixels.shape[1], height=pixels.shape[0],
        crs="EPSG:28350", transform=from_origin(west, north, 1, 1),
        dtype="float32", nodata=-9999,
    ) as output:
        output.write(pixels.astype("float32"), 1)


def test_lidar_overrides_srtm_and_srtm_fills_void(tmp_path: Path) -> None:
    coarse = tmp_path / "srtm.tif"
    lidar = tmp_path / "lidar.tif"
    _raster(coarse, np.full((10, 10), 100), west=0, north=10)
    pixels = np.full((2, 2), 200.0)
    pixels[0, 0] = -9999
    _raster(lidar, pixels, west=4, north=6)
    merged = compose_terrain(
        [lidar, coarse], target_crs=CRS.from_epsg(28350),
        directory=tmp_path / "outputs", resolution_m=1,
    )
    with rasterio.open(merged.dem) as dataset, rasterio.open(merged.source_index) as source_index:
        elev = dataset.read(1)
        source = source_index.read(1)
    assert elev[4, 4] == 100.0
    assert np.all(elev[4:6, 4:6][pixels != -9999] == 200)
    assert source[4, 4] == 2
    assert np.all(source[4:6, 4:6][pixels != -9999] == 1)


def test_reverse_terrain_priority(tmp_path: Path) -> None:
    a, b = tmp_path / "a.tif", tmp_path / "b.tif"
    _raster(a, np.full((5, 5), 1), west=0, north=5)
    _raster(b, np.full((5, 5), 2), west=0, north=5)
    first = compose_terrain([a, b], target_crs=CRS.from_epsg(28350), directory=tmp_path / "first")
    last = compose_terrain([b, a], target_crs=CRS.from_epsg(28350), directory=tmp_path / "last")
    with rasterio.open(first.dem) as f, rasterio.open(last.dem) as l:
        assert np.all(f.read(1) == 1)
        assert np.all(l.read(1) == 2)


def test_reject_unbounded_fine_grid(tmp_path: Path) -> None:
    a = tmp_path / "a.tif"
    _raster(a, np.ones((5, 5)), west=0, north=5)
    with pytest.raises(ValueError, match="Unsafe"):
        compose_terrain([a], target_crs=CRS.from_epsg(28350), directory=tmp_path / "out", max_cells=5)


def _domain(exclusion=None):
    directions = np.zeros((12, 12), dtype=np.int16)
    directions[3:8, 6] = 6  # downstream to the AOI, entirely within source DEM
    return make_domain(
        directions, aoi=box(6.2, 3.2, 6.8, 3.8),
        transform=from_origin(0, 12, 1, 1), raster_bounds=(0, 0, 12, 12),
        buffer_m=0.25, exclusions=exclusion,
    )


def test_exclusions_remove_only_upstream_area_without_changing_full_catchment() -> None:
    complete = _domain()
    cropped = _domain(box(6.1, 6.1, 6.9, 6.9))
    assert cropped.contributing.equals(complete.contributing)
    assert cropped.excluded_area is not None
    assert cropped.excluded_area.area > 0
    assert cropped.active.area == pytest.approx(complete.active.area - cropped.excluded_area.area)
    assert cropped.active.intersection(cropped.excluded_area).area == pytest.approx(0)
    assert cropped.location.covers(cropped.active)


def test_exclusions_must_not_remove_aoi_buffer() -> None:
    with pytest.raises(ValueError, match="buffer"):
        _domain(box(6.1, 3.1, 6.9, 3.9))


def test_exclusions_outside_upstream_area_rejected() -> None:
    with pytest.raises(ValueError, match="do not intersect"):
        _domain(box(1.2, 1.2, 1.8, 1.8))
