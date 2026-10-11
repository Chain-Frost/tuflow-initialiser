"""Terrain/AOI checks and deterministic domain generation."""

from dataclasses import dataclass
from pathlib import Path

import fiona
import numpy as np
import rasterio
from numpy.typing import NDArray
from rasterio.features import rasterize, shapes
from shapely.geometry import Polygon, box, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from .d8 import contributing_cells


@dataclass(frozen=True, slots=True)
class Domain:
    """Analysis geometry in DEM horizontal coordinates (metres)."""

    aoi: BaseGeometry
    contributing: BaseGeometry
    buffer: BaseGeometry
    active: BaseGeometry
    location: Polygon
    contributing_cells: NDArray[np.bool_]
    exclusions: BaseGeometry | None = None
    excluded_area: BaseGeometry | None = None


def read_aoi(path: Path, *, expected_crs: rasterio.crs.CRS) -> BaseGeometry:
    """Read polygon AOI without implicit coordinate transformation."""
    with fiona.open(path) as src:
        if not src.crs_wkt or rasterio.crs.CRS.from_wkt(src.crs_wkt) != expected_crs:
            raise ValueError("AOI CRS must match the DEM CRS; reproject explicitly")
        polygons = []
        for feature in src:
            if feature.geometry is None:
                continue
            geom = shape(feature.geometry)
            if geom.geom_type not in {"Polygon", "MultiPolygon"} or not geom.is_valid:
                raise ValueError("AOI must contain valid polygon geometries")
            if not geom.is_empty:
                polygons.append(geom)
    if not polygons:
        raise ValueError("AOI has no polygon features")
    result = unary_union(polygons)
    if not result.is_valid or result.is_empty:
        raise ValueError("Invalid AOI union")
    return result


def check_dem(dem: rasterio.io.DatasetReader) -> None:
    """Reject incompatible DEMs rather than silently warp input."""
    if dem.count != 1 or dem.crs is None or not dem.crs.is_projected:
        raise ValueError("DEM must have one band and projected coordinate system")
    units, factor = dem.crs.linear_units_factor
    if not np.isclose(factor, 1.0):
        raise ValueError(f"DEM horizontal units must be metres; found {units}")
    if dem.width < 3 or dem.height < 3:
        raise ValueError("DEM too small for watershed delineation")
    if dem.transform.b != 0 or dem.transform.d != 0:
        raise ValueError("Rotated/skewed DEM not supported")
    if not (dem.res[0] > 0 and dem.res[1] > 0):
        raise ValueError("Invalid DEM resolution")


def mask_to_polygon(mask: NDArray[np.bool_], transform: rasterio.Affine) -> BaseGeometry:
    if not np.any(mask):
        raise ValueError("Cannot polygonise an empty raster mask")
    parts = [shape(g) for g, value in shapes(mask.astype(np.uint8), mask=mask, transform=transform) if value == 1]
    geom = unary_union(parts)
    if geom.is_empty or not geom.is_valid:
        raise ValueError("Invalid polygonised raster mask")
    return geom


def make_domain(
    directions: NDArray[np.integer],
    *,
    aoi: BaseGeometry,
    transform: rasterio.Affine,
    raster_bounds: tuple[float, float, float, float],
    buffer_m: float = 500.0,
    exclusions: BaseGeometry | None = None,
) -> Domain:
    """Delineate all AOI contributing cells and union with circular AOI buffer."""
    if buffer_m <= 0 or not np.isfinite(buffer_m):
        raise ValueError("AOI buffer must be finite and positive")
    if not box(*raster_bounds).covers(aoi):
        raise ValueError("AOI must lie entirely inside DEM")
    seed = rasterize([(aoi, 1)], out_shape=directions.shape, transform=transform, fill=0, all_touched=True).astype(bool)
    upstream = contributing_cells(directions, seed)
    contributing = mask_to_polygon(upstream, transform)
    expanded = aoi.buffer(buffer_m)
    if not box(*raster_bounds).covers(expanded):
        raise ValueError("AOI downstream buffer reaches DEM edge; supply larger terrain")
    full_active = unary_union([contributing, expanded])
    excluded_area: BaseGeometry | None = None
    if exclusions is not None:
        if exclusions.is_empty or not exclusions.is_valid:
            raise ValueError("Exclusion polygons must be nonempty and valid")
        if exclusions.intersection(expanded).area > 1e-6:
            raise ValueError("Upstream exclusions may not overlap AOI or its required circular buffer")
        excluded_area = exclusions.intersection(contributing)
        if excluded_area.is_empty or excluded_area.area <= 0:
            raise ValueError("Exclusions do not intersect the contributing catchment")
    active = full_active.difference(excluded_area) if excluded_area is not None else full_active
    if not active.is_valid or active.is_empty or not active.covers(aoi):
        raise ValueError("Invalid or incomplete active model polygon")
    xmin, ymin, xmax, ymax = active.bounds
    loc = Polygon([(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)])
    if not loc.is_valid or not loc.covers(active):
        raise ValueError("Cardinal 2d_loc rectangle does not cover active area")
    if excluded_area is not None and active.intersection(excluded_area).area > 1e-6:
        raise ValueError("Excluded upstream areas remain active")
    return Domain(aoi, contributing, expanded, active, loc, upstream, exclusions, excluded_area)



def detailed_analysis_cells(
    domain: Domain,
    *,
    transform: rasterio.Affine,
    analyse_exclusions: bool = False,
) -> NDArray[np.bool_]:
    """Select the stream/subcatchment analysis cells, independently of model code.

    Excluded terrain always remains in the *full* AOI contributing-area
    delineation. Unless explicitly requested, it is omitted from the detailed
    stream and stream-headwater analysis. Rasterise conservatively with
    all_touched=True so even partially excluded cells are not analysed.
    """
    cells = domain.contributing_cells.copy()
    if domain.excluded_area is None or analyse_exclusions:
        return cells
    excluded_cells = rasterize(
        [(domain.excluded_area, 1)],
        out_shape=cells.shape,
        transform=transform,
        fill=0,
        all_touched=True,
    )
    return cells & (excluded_cells == 0)
