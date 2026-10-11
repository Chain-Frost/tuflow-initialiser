# Architecture: initial scope

- All rainfall is 2D rainfall-on-grid; no `2d_sa` or other upstream inflow types.
- Inputs: projected metre-based DEM, AOI polygon(s), configurable **circular AOI buffer** (default 500 m, 1000 m practical option), stream accumulation-area threshold.
- GRASS CLI `r.watershed -s` D8 flow direction/accumulation; optional controlled hydrology-only depression filling.
- AOI upstream area is *all cells* whose D8 flow reaches **any** AOI cell. Multiple independent networks are supported, not reduced to one selected outlet.
- Model area is contributing area union Euclidean buffer around AOI. Simplicity is intentional for first implementation, but boundary-effects judgement remains with the modeller.
- Stream area threshold is distinct from delineation: threshold only changes stream density, never contributing extent. Headwater extensions will follow upstream D8 cells from stream threshold starts toward divides. Explicitly flag them as synthetic flow paths rather than natural mapped channels.
- Equal-area stream slope: for upstream distance x from outlet, `S_ea = 2/L² ∫_0^L (z(x)-z_out) dx`. Sample profile along original DEM and apply trapezoidal integration; this is not endpoint gradient or mean of pixel slopes.
- Geometry: active `2d_code` and `2d_rf` footprints identical; `2d_loc` cardinal bounding rectangle SW-SE-NE-NW. TUFLOW GIS schema inherited from authoritative empty GeoPackages. Geometry independent from hydraulic cell size.
- No runtime ryan-tools dependency. Optional utility copying requires user to provide a scripts directory. QGIS GUI/MCP are deferred; standalone CLI orchestrates GRASS without interactive GUI.
- Stage files; validate all mandatory conditions before publishing.

## Scope exclusions
No `2d_bc` initially (future outlet only), `2d_po`, `2d_mat`, `2d_sa`, ARR rainfall creation, model extent optimisation, automated maps, .trfc, crossings, material mapping or cell-size selection.

## Key references
- https://grass.osgeo.org/grass-stable/manuals/r.watershed.html
- https://grass.osgeo.org/grass-stable/manuals/r.fill.dir.html
- https://grass.osgeo.org/grass-stable/manuals/grass.html
- https://docs.tuflow.com/classic-hpc/manual/2026.0/
