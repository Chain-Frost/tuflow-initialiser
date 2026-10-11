"""Build an ordered GDAL-backed DEM mosaic for watershed analysis.

First terrain source has highest priority. Lower-priority datasets fill only
missing/invalid cells; a provenance raster records which source was used.
The analysis DEM resolution is distinct from TUFLOW's hydraulic cell size.
"""

import math
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds
from rasterio.windows import Window


@dataclass(frozen=True, slots=True)
class TerrainMosaic:
    """Hydrological DEM, per-pixel source index, and analysis resolution."""

    dem: Path
    source_index: Path
    resolution_m: float


def compose_terrain(
    terrain_sources: Sequence[Path],
    *,
    target_crs: CRS,
    directory: Path,
    resolution_m: float | None = None,
    max_cells: int = 100_000_000,
) -> TerrainMosaic:
    """Build a priority mosaic from multiple resolutions and coordinate systems.

    Inputs are high-to-low priority. The first non-NoData source wins.
    WarpedVRT delegates on-the-fly raster reprojection to GDAL. An explicit
    alpha band is critical for sources with no declared NoData value.
    """
    paths = tuple(Path(item).resolve() for item in terrain_sources)
    if not paths or len(paths) != len(set(paths)):
        raise ValueError("Terrain sources must be nonempty and unique, in priority order")
    if len(paths) > np.iinfo(np.uint16).max:
        raise ValueError("At most 65535 terrain sources are supported")
    if not target_crs.is_projected or not math.isclose(target_crs.linear_units_factor[1], 1.0):
        raise ValueError("Target CRS must be projected in metres")
    if max_cells <= 0:
        raise ValueError("max_cells must be positive")
    for source in paths:
        if not source.is_file():
            raise FileNotFoundError(source)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "analysis_dem.tif"
    provenance = directory / "terrain_source_index.tif"
    if target.exists() or provenance.exists():
        raise FileExistsError("Terrain output already exists")

    with ExitStack() as stack:
        sources = [stack.enter_context(rasterio.open(path)) for path in paths]
        for source in sources:
            if source.count != 1 or source.crs is None:
                raise ValueError(f"Terrain must be single-band with CRS: {source.name}")
            if source.transform.b or source.transform.d:
                raise ValueError(f"Rotated terrain is unsupported: {source.name}")
        if resolution_m is None:
            first = sources[0]
            if first.crs != target_crs or not first.crs.is_projected:
                raise ValueError("Specify --analysis-resolution-m if top-priority DEM requires reprojection")
            resolution_m = max(abs(first.res[0]), abs(first.res[1]))
        if not math.isfinite(resolution_m) or resolution_m <= 0:
            raise ValueError("Analysis resolution must be finite and positive")

        bounds = [transform_bounds(src.crs, target_crs, *src.bounds, densify_pts=21) for src in sources]
        west = math.floor(min(b[0] for b in bounds) / resolution_m) * resolution_m
        south = math.floor(min(b[1] for b in bounds) / resolution_m) * resolution_m
        east = math.ceil(max(b[2] for b in bounds) / resolution_m) * resolution_m
        north = math.ceil(max(b[3] for b in bounds) / resolution_m) * resolution_m
        width = round((east - west) / resolution_m)
        height = round((north - south) / resolution_m)
        if width < 3 or height < 3 or width * height > max_cells:
            raise ValueError(f"Unsafe analysis raster size {width}x{height}; change analysis resolution")
        transform = from_origin(west, north, resolution_m, resolution_m)
        vrts = [
            stack.enter_context(
                WarpedVRT(
                    src, crs=target_crs, transform=transform, width=width, height=height,
                    resampling=Resampling.bilinear, add_alpha=True,
                )
            )
            for src in sources
        ]
        profile = {
            "driver": "GTiff", "dtype": "float32", "count": 1,
            "height": height, "width": width, "crs": target_crs,
            "transform": transform, "nodata": -3.4028234663852886e38,
            "compress": "deflate", "BIGTIFF": "IF_SAFER",
        }
        with (
            rasterio.open(target, "w", **profile) as dem_output,
            rasterio.open(provenance, "w", **(profile | {"dtype": "uint16", "nodata": 0})) as provenance_output,
        ):
            for row in range(0, height, 512):
                for col in range(0, width, 512):
                    window = Window(col, row, min(512, width - col), min(512, height - row))
                    tile_shape = (int(window.height), int(window.width))
                    values = np.full(tile_shape, profile["nodata"], dtype=np.float32)
                    selected = np.zeros(tile_shape, dtype=np.uint16)
                    for rank, vrt in enumerate(vrts, start=1):
                        pixels = vrt.read(1, window=window)
                        # WarpedVRT(add_alpha=True) exposes source coverage in its
                        # final alpha band; read_masks(1) can report all-valid.
                        alpha = vrt.read(vrt.count, window=window)
                        valid = (selected == 0) & (alpha > 0) & np.isfinite(pixels)
                        values[valid] = pixels[valid]
                        selected[valid] = rank
                    dem_output.write(values, 1, window=window)
                    provenance_output.write(selected, 1, window=window)
    return TerrainMosaic(target, provenance, float(resolution_m))
