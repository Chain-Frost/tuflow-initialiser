# TUFLOW Initialiser

Standalone Python/GRASS initialisation of **2D rainfall-on-grid (ROG)** TUFLOW projects.

The `build` workflow takes ordered terrain rasters, AOI polygon(s) and optional upstream exclusion polygons. It delineates full D8 contributing areas, adds a configurable circular AOI buffer (default 500 m), extracts stream paths and their equal-area slopes, and produces `2d_code`, `2d_loc`, `2d_rf` from canonical TUFLOW empty layers.

## Installation

Python 3.14 on Windows; separately installed GRASS GIS and TUFLOW executable.

Install binary GIS wheels using the same wheel index as `ryan-tools`:

```powershell
python -m pip install --upgrade --extra-index-url https://gisidx.github.io/gwi --only-binary=:all: fiona rasterio gdal
python -m pip install --prefer-binary --extra-index-url https://gisidx.github.io/gwi --only-binary=fiona --only-binary=rasterio --only-binary=gdal -e ".[dev]"
```

## Local data and test runs

Place downloaded SRTM/LiDAR data in `data/` or `datasets/`, and generated test projects in `outputs/` (all ignored by Git). Use `tests/fixtures/` for small, deliberately committed test inputs and reference files. Raster/GIS extensions are **not** globally ignored because reproducible fixtures and maintained TUFLOW templates are valid source assets.

The ignore rules do not remove files that Git is already tracking. Check pending files with `git status --short` before committing.

## Code quality

The repo adopts the Ruff and strict Pyright baseline from
[`ryan-culverts`](https://github.com/Chain-Frost/ryan-culverts):
Python 3.14, Ruff 0.16.6, Google-style docstrings, consistent imports and
formatting, and strict typing across `src/`, `tests/` and `scripts/`.
Run locally after installing the `dev` extra:

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pyright
python -m pytest -q
```

These checks are included in CI. Initial Ruff/Pyright failures indicate
**outstanding source remediation**, not an installation failure or a
reason to disable strict checking. See [code-quality issue #7](https://github.com/Chain-Frost/tuflow-initialiser/issues/7).

## Example

```powershell
tuflow-initialiser build `
  --terrain "D:\\terrain\\lidar_1m.tif" `
  --terrain "D:\\terrain\\srtm_30m.tif" `
  --aoi "D:\\gis\\aoi.gpkg" `
  --exclude "D:\\gis\\already_modelled_upstream.gpkg" `
  --analysis-resolution-m 10 `
  --buffer-m 500 `
  --stream-area-m2 100000 `
  --name Example --scenario EXG `
  --prj "D:\\gis\\project.prj" `
  --tuflow-exe "C:\\TUFLOW\\TUFLOW_iSP_w64.exe" `
  --rainfall-name RF01 `
  --output "D:\\models\\Example"
```

**Terrain priority:** first `--terrain` has highest priority and takes precedence wherever it contains valid elevations. Lower-priority sources fill its gaps. Hydrology uses a separately resampled analysis DEM; the TUFLOW geometry control file reads the original/source-resolution DEMs in reverse order so high-priority topography prevails.

**Exclusions:** the full upstream catchment is preserved in analysis outputs, but exclusions are removed from `2d_code` and identically from `2d_rf`. Detailed stream/headwater analysis of these excluded areas is **off by default**, since existing catchment information may already be available. Add `--analyse-exclusions` when detailed analysis is required. GRASS terrain processing and D8 connectivity still run over the entire analysis DEM to establish contributing drainage accurately. Inflow replacement and outlet BC design are **not** generated: excluded catchments may require manual boundary treatment before simulation.

**Development status:** Draft PR, not production validated. The tool requires Windows GRASS/TUFLOW live testing and engineering review. No runtime dependency on `ryan-tools`; copying extra `ryan-tools` project utilities remains optional.

See [architecture](docs/architecture.md), [validation](docs/validation.md), [migration](docs/migration.md), and [future work](docs/future-work.md).

License: [Sustainable Use License 1.0](LICENSE).
