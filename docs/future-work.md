# Deferred features and ideas

Candidate **future** work (not in initial scope):

- Follow-flow downstream extension and floodplain-aware buffers rather than simple circular AOI buffering.
- `2d_bc` **outlet boundary only** generation.
- `2d_po` monitoring sections.
- Integration with separate `2d_mat` generation utilities, not duplicating material processing.
- QGIS Processing provider, interactive AOI editing and QGIS MCP interface.
- Caching hydrology rasters keyed by DEM, CRS, conditioning and processing engine versions.
- Additional hydrological terrain conditioning (breaching/burn-in, protected natural sinks) and fill QA.
- MFD/D-infinity comparisons for alluvial fans and distributary networks.
- Multiresolution/region-based processing for very large DEMs.
- More sophisticated stream-headwater main-path selection, and extended catchment metrics.
- Optional crossing analysis and model preflight checks.

**Explicitly excluded permanently:** model extent optimisation, automatic cell-size selection, ARR rainfall processing, automatic mapping/reports, `.trfc`, and `2d_sa`.
