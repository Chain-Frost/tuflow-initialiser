# Project-scoped GIS API typing

Fiona 1.10.1, Rasterio 1.5.2 and Affine 2.4.0 expose the APIs used here without
complete type information. These narrow stubs describe only the calls exercised
by the initialiser, its tests and the real-system validation runner. They are
static-checking inputs, not runtime replacements or general-purpose library stubs.
Shapely uses the pinned `types-shapely` development dependency instead.

The contracts preserve nullable CRS/geometry, numeric raster arrays without
assuming their dtype, and nullable scalar feature fields. The masked raster read
result exposes only the `filled` operation used by the workflow. Writers and
readers have separate return types; schemas and profiles use typed dictionaries.
GeoTIFF creation options remain driver-specific keyword arguments.

These declarations were checked against the installed APIs and exercised through
the synthetic GIS tests and the tracked DEM/AOI GRASS/TUFLOW build. New library
calls need a reviewed declaration and runtime evidence; do not replace unknown
APIs with `Any` or suppress strict checks globally. Fiona's `Schema`/`FeatureRecord`
names and Rasterio's `MaskedBand` are stub-only type definitions. Runtime code
uses the concrete dictionaries in `gis_types.py`.

The inline Ruff exceptions for `open` preserve the third-party API names.
Runtime subprocess exceptions are restricted to the two explicit argv calls
that launch selected GRASS/TUFLOW tools without a shell.
