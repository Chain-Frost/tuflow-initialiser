# Shared integration inputs

These files are intentionally tracked so every checkout can run the same
base-workflow validation. Keep generated models, logs and GIS sidecars outside
this directory, under ignored `validation/`.

- `dem_epsg28350.tif`: supplied hydro-enforced DEM, 760 x 823 pixels at
  approximately 28.6 m resolution. This is a pixel-preserving GeoTIFF copy of the
  originally supplied ASCII DEM, with EPSG:28350 assigned from the user's stated
  CRS and accompanying projection. No vertical transformation was applied.
- `region.gpkg`: two supplied AOI polygons in EPSG:28350.
- `manifest.json`: SHA-256 hashes of the two authoritative test inputs.
- `data_loaded.qgz`: optional existing QGIS viewing project; not required by tests.

The upstream dataset source, redistribution licence and vertical datum have not
been recorded. This fixture establishes reproducible software inputs, not terrain
provenance or engineering suitability. Record those details when available.

Do not edit the inputs as part of an ordinary test run. A deliberate fixture
replacement must update the manifest and validation evidence together.

See [reproduction and results](../docs/base-workflow-validation.md). The runner
uses the tracked GeoTIFF directly and does not require the original ASCII DEM or
an untracked projection file. GRASS and TUFLOW must be installed separately.
