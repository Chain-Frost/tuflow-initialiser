# Fail-closed integrity and preflight checks

- Each supplied terrain source must be readable, single-band with declared CRS, and carry valid NoData handling. Source list is ordered, unique and nonempty; output analysis grid uses a projected metre-based CRS and is capped at a configurable maximum cell count.
- A GDAL-backed provenance raster records source priority for every hydrology analysis DEM pixel. First valid source wins. Input terrain grids can differ in extent/resolution/CRS; reprojection is explicit. Vertical datum **cannot** be inferred from CRS alone; conflicting vertical datums and seams remain a required engineering review.
- AOI geometry must be valid, nonempty, and lie inside DEM coverage and use project CRS. All upstream contributing cells must be determinable, and unknown NoData/edge-truncated basin paths must stop the build.
- Exclusions require valid polygon geometry in project CRS. Delineate full AOI contribution first, then clip applied exclusions to contributing area. Reject exclusions with no overlap or any intersection with AOI circular buffer. Original catchment is retained in analysis GeoPackage; active TUFLOW polygons exclude it. **Detailed excluded-catchment analysis defaults to off** (opt in with `--analyse-exclusions`). Verify that default stream/headwater and future subcatchment products omit excluded cells. Connectivity/flow direction and accumulation still use the full hydrology DEM so downstream catchment boundaries are valid; this option is not a GRASS runtime shortcut.
- Preserve original DEM; any hydrology filling/breaching is separate and subject to configured max terrain change. Synthetic stream heads are not mapped channels; longitudinal slope uses original analysis DEM, not modified fill heights.
- Final `2d_code` and `2d_rf` **identical footprints**; `2d_loc` unrotated rectangular envelope. Reopen generated canonical TUFLOW schema GeoPackages to verify field list, geometry types, CRS and coverage.
- Stage the project and publish only after validations pass; do not overwrite an existing project.
- Warn in output if upstream catchments were excluded: resulting model may be hydraulically incomplete until external inflows / upstream interfaces are resolved by engineering design.

## Real-system checks required before merge

Run end-to-end tests on Windows with installed GRASS and current TUFLOW, confirm canonical empty GPKG fields, source-order terrain precedence, raster reprojection, vertical data consistency and stream/catchment delineation. Large regional performance remains unverified. Unit tests alone are insufficient to approve engineering output.
