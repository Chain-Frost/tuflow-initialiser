"""Stage, process, validate and publish complete 2D ROG initial model GIS."""

import json
import math
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import fiona
import numpy as np
import rasterio
from numpy.typing import NDArray
from shapely.geometry import LineString, mapping
from shapely.ops import unary_union

from .d8 import headwater_extensions, stream_mask
from .geometry import Domain, check_dem, make_domain, read_aoi
from .gis_writer import write_analysis, write_tuflow_layers
from .grass_runner import process_terrain
from .model_terrain import set_model_terrain
from .profiles import equal_area_slope, stream_reaches
from .project_setup import TuflowProjectConfig, initialize_tuflow_project
from .terrain import compose_terrain


@dataclass(frozen=True, slots=True)
class BuildConfig:
    """Explicit requirements: no hydraulic cell-size or ryan-tools dependency."""

    terrains: tuple[Path, ...]
    aoi: Path
    output: Path
    name: str
    scenario: str
    prj: Path
    tuflow_executable: Path
    rainfall_name: str
    exclusions: tuple[Path, ...] = ()
    analysis_resolution_m: float | None = None
    max_analysis_cells: int = 100_000_000
    grass_executable: str = "grass"
    buffer_m: float = 500.0
    stream_threshold_m2: float = 100_000.0
    fill_depressions: bool = False
    max_fill_depth_m: float = 2.0
    utility_source_root: Path | None = None


def _consistent_grids(dem: rasterio.io.DatasetReader, other: rasterio.io.DatasetReader) -> None:
    if other.width != dem.width or other.height != dem.height or other.crs != dem.crs:
        raise ValueError("GRASS raster geometry or CRS differs from original DEM")
    if not np.allclose(tuple(other.transform), tuple(dem.transform), rtol=0, atol=1e-7):
        raise ValueError("GRASS output transform differs from original DEM")


def _line(path: list[tuple[int, int]], transform: rasterio.Affine) -> LineString:
    return LineString([transform * (col + 0.5, row + 0.5) for row, col in path])


def _write_streams(
    out: Path,
    *,
    directions: NDArray[np.integer],
    accumulation: NDArray[np.floating],
    contributing: NDArray[np.bool_],
    terrain: NDArray[np.floating],
    transform: rasterio.Affine,
    crs_wkt: str,
    min_area_m2: float,
) -> None:
    threshold = stream_mask(
        accumulation, cell_area_m2=abs(transform.a * transform.e),
        min_area_m2=min_area_m2,
    ) & contributing
    reaches = stream_reaches(directions, threshold)
    extensions = headwater_extensions(directions, threshold, accumulation)
    schema = {
        "geometry": "LineString",
        "properties": {
            "path_id": "int",
            "path_type": "str:32",
            "length_m": "float",
            "slope_ea": "float",
        },
    }
    with fiona.open(out, "w", driver="GPKG", layer="streams", crs_wkt=crs_wkt, schema=schema) as layer:
        for n, (path_type, group) in enumerate(
            [("channel", p) for p in reaches] + [("synthetic_headwater", p) for p in extensions],
            start=1,
        ):
            geom = _line(group, transform)
            if geom.length <= 0:
                raise ValueError("Degenerate stream path")
            # Stream paths are stored headwater->downstream; the profile is
            # reversed for equal-area calculations (outlet->headwater).
            downstream_first = group[::-1]
            centres = [_line(downstream_first[i : i + 2], transform).length for i in range(len(group) - 1)]
            distances = np.concatenate(([0.0], np.cumsum(centres)))
            elevations = np.array([float(terrain[row, col]) for row, col in downstream_first])
            slope = equal_area_slope(distances, elevations)
            if not math.isfinite(slope):
                raise ValueError("Nonfinite equal-area stream slope")
            layer.write({
                "geometry": mapping(geom),
                "properties": {
                    "path_id": n, "path_type": path_type,
                    "length_m": geom.length, "slope_ea": slope,
                },
            })


def build(config: BuildConfig) -> Path:
    """Run full hydrology, stage TUFLOW outputs, then publish atomically by directory.

    Existing target projects are never overwritten.
    """
    if config.output.exists():
        raise FileExistsError(f"Existing project directory is protected: {config.output}")
    if config.buffer_m <= 0 or config.stream_threshold_m2 <= 0:
        raise ValueError("Buffer and stream threshold must be positive")
    if not config.terrains or any(not p.is_file() for p in config.terrains):
        raise FileNotFoundError("At least one existing terrain raster is required")
    if not config.aoi.is_file() or not config.prj.is_file():
        raise FileNotFoundError("AOI and project projection file are required")
    if any(not p.is_file() for p in config.exclusions):
        raise FileNotFoundError("One or more exclusion polygon files do not exist")
    config.output.parent.mkdir(parents=True, exist_ok=True)
    target_crs = rasterio.crs.CRS.from_wkt(config.prj.read_text(encoding="utf-8-sig"))
    with tempfile.TemporaryDirectory(prefix="tuflow-init-", dir=config.output.parent) as temp:
        scratch = Path(temp)
        mosaic = compose_terrain(
            config.terrains, target_crs=target_crs,
            directory=scratch / "mosaic", resolution_m=config.analysis_resolution_m,
            max_cells=config.max_analysis_cells,
        )
        with rasterio.open(mosaic.dem) as terrain:
            check_dem(terrain)
            aoi = read_aoi(config.aoi, expected_crs=terrain.crs)
            exclusions = (
                unary_union([read_aoi(p, expected_crs=terrain.crs) for p in config.exclusions])
                if config.exclusions else None
            )
            grass = process_terrain(
                mosaic.dem, work_dir=scratch / "grass",
                grass_executable=config.grass_executable,
                fill_depressions=config.fill_depressions,
            )
            with rasterio.open(grass.flow_direction) as direction_ds, rasterio.open(grass.accumulation) as acc_ds, rasterio.open(grass.conditioned_dem) as hydro_ds:
                for ds in (direction_ds, acc_ds, hydro_ds):
                    _consistent_grids(terrain, ds)
                directions = direction_ds.read(1, masked=True).filled(0).astype(np.int16)
                accum = acc_ds.read(1, masked=True).filled(0).astype(np.float64)
                conditioned = hydro_ds.read(1, masked=True).filled(np.nan).astype(np.float64)
                original = terrain.read(1, masked=True).filled(np.nan).astype(np.float64)
                domain: Domain = make_domain(
                    directions, aoi=aoi, transform=terrain.transform,
                    raster_bounds=tuple(terrain.bounds), buffer_m=config.buffer_m,
                    exclusions=exclusions,
                )
                # No missing source/conditioned terrain anywhere used in the
                # computed model domain (not just within the AOI).
                from rasterio.features import rasterize

                model_pixels = rasterize(
                    [(domain.active, 1)], out_shape=directions.shape,
                    transform=terrain.transform, all_touched=True, fill=0,
                ).astype(bool)
                if not np.all(np.isfinite(original[model_pixels])) or not np.all(np.isfinite(conditioned[model_pixels])):
                    raise ValueError("NoData or nonfinite DEM elevations inside model area")
                diff = conditioned[model_pixels] - original[model_pixels]
                if config.max_fill_depth_m < 0 or np.max(diff) > config.max_fill_depth_m:
                    raise ValueError("Hydrology-only terrain fill exceeds max_fill_depth_m")
                stage_project = scratch / "project"
                initialize_tuflow_project(
                    TuflowProjectConfig(
                        output_dir=stage_project,
                        project_name=config.name,
                        scenario_name=config.scenario,
                        prj_file=config.prj,
                        tuflow_executable=config.tuflow_executable,
                        templates_dir=Path(__file__).resolve().parent / "resources" / "tuflow_templates",
                        copy_utilities=config.utility_source_root is not None,
                        utility_source_root=config.utility_source_root,
                    )
                )
                set_model_terrain(
                    project_dir=stage_project, sources=config.terrains, target_crs=target_crs,
                )
                write_tuflow_layers(
                    stage_project, scenario=config.scenario, domain=domain, rainfall_name=config.rainfall_name
                )
                analysis = stage_project / "model" / "gis" / "hydrology.gpkg"
                write_analysis(analysis, domain=domain, crs_wkt=terrain.crs.to_wkt())
                stream_gpkg = stage_project / "model" / "gis" / "streams.gpkg"
                _write_streams(
                    stream_gpkg, directions=directions, accumulation=accum,
                    contributing=domain.contributing_cells, terrain=original,
                    transform=terrain.transform, crs_wkt=terrain.crs.to_wkt(),
                    min_area_m2=config.stream_threshold_m2,
                )
                target_analysis = stage_project / "terrain" / "hydrology"
                target_analysis.mkdir(parents=True)
                for file in (grass.flow_direction, grass.accumulation, grass.conditioned_dem, mosaic.dem, mosaic.source_index):
                    shutil.copy2(file, target_analysis / file.name)
                (target_analysis / "terrain_sources.json").write_text(
                    json.dumps(
                        {"priority": "first_valid_wins",
                         "analysis_resolution_m": mosaic.resolution_m,
                         "sources": [{"priority": index, "path": str(path.resolve())}
                                     for index, path in enumerate(config.terrains, start=1)]},
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                if domain.excluded_area is not None:
                    (stage_project / "EXCLUSIONS_REQUIRE_REVIEW.txt").write_text(
                        "Upstream catchments have been excluded from 2D code and rainfall. "
                        "Their incoming flow has NOT been replaced with BCs. "
                        "The model is not hydraulically complete until a modeller handles these interfaces.\n",
                        encoding="utf-8",
                    )
            # Atomic rename when scratch and destination share a filesystem.
            if config.output.exists():
                raise FileExistsError(f"Output appeared during processing: {config.output}")
            stage_project.rename(config.output)
    return config.output
