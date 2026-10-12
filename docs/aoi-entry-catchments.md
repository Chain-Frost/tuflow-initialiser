# AOI-entry catchment outputs (in progress)

The project builder preserves each input AOI feature as a deterministic 1-based
`aoi_id` in its original GeoPackage feature order, while still unioning AOIs
for the TUFLOW hydraulic model extent. Reordering AOI input records can change
IDs; external IDs and per-reach relationships are future work.

## New output

`model/gis/inflow_catchments.gpkg` contains three layers:

- `aoi_inputs`: source AOI feature polygons and `aoi_id`.
- `aoi_inflow_catchments`: **incremental exterior D8 upstream cells** assigned
  to the first edge at which each route crosses into that AOI, with a stable
  `catch_id`, inlet/outlet raster cells, local exterior area, AOI total
  cumulative area, elevation statistics and analysis status.
- `longest_flow_paths`: longest continuous inferred D8 path to each crossing,
  including the final crossing step into the AOI, with computed length (m),
  whole-path signed equal-area slope, endpoint elevations and a signed-slope
  QA flag. The farthest branch is selected by cumulative 2D geometric distance,
  **not** highest flow accumulation, stream threshold, or source elevation.

`terrain/hydrology/aoi_inflows.json` records the same IDs, areas, end cells,
statuses, lengths and slopes for scripted QA. The original `streams.gpkg`
remains independent and retains the historical stream/headwater segmentation.

Each upstream exterior cell is attributed once **within a given AOI**.
Where there are nested or serial AOIs, the same cell may contribute to several
AOIs' *cumulative* areas. Therefore do **not** sum cumulative values across
AOIs. The entry polygons exclude their own AOI cells, while the AOI cumulative
area includes them.

A catchment intersecting a disabled excluded-analysis area remains listed
for hydrological audit but has `excluded_from_detailed_analysis` status and
**no incomplete longest-path feature**. Re-enable detailed analysis with
`--analyse-exclusions` when those paths are needed. The TUFLOW active
`2d_code` / rainfall exclusions remain unchanged in either mode.

## Limitations / merge gates

- An entry crossing is a **single D8 cell edge**. Multiple neighbouring
  sheet-flow entries may need to be grouped into a hydrologically meaningful
  drainage system. Do not mistake the number of entries for the number of
  independent watercourses.
- The current entry polygons are **not per-stream-reach subcatchments**.
  Downstream reach topology, complete local/per-reach area partitioning,
  terrain-derived mean reach-catchment slopes and consistent downstream
  subcatchment IDs remain necessary under issue #3.
- D8 paths derived from DEM cells are **inferred**, not surveyed streams.
  Negative signed slopes are retained as QA, not clamped to zero.
- The AOI-entry and LFP results are covered by synthetic tests only so far.
  Validate against the tracked SRTM/two-AOI fixture on real Windows GRASS/
  TUFLOW, then inspect and compare representative multiple-inflow and nested-
  AOI examples. Preserve the original 805 path baseline unless an intentional
  engineering change is approved.
- Complex vertical datum/terrain seams and excluded upstream flow interfaces
  require independent modeller review. This initialiser does not generate
  a `2d_bc` or replacement hydrograph.
