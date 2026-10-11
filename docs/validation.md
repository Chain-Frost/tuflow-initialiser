# Fail-closed validation

Stop when: DEM CRS is missing, nonprojected or nonmetre; AOI invalid, empty or outside DEM; source terrain NoData within relevant domain; D8 invalid, cyclic or truncated at DEM edges; fill operations exceed documented limits; model polygons empty/invalid; rainfall coverage differs from active code; cardinal location polygon not containing model; output TUFLOW schema does not match canonical empty-layer schema.

Preserve hydraulic DEM unchanged. Use separate hydrology-conditioned DEM. Stage output then inspect geometry/CRS/field schema/counts before final write, protecting existing files unless explicitly overridden.

Data integrity is not proof of hydraulic adequacy. A circular buffer cannot by itself guarantee downstream boundary independence.

**Outstanding mandatory system checks:** actual GRASS Windows invocation and raster export; actual TUFLOW-generated empties; multi-million cell performance; TUFLOW dry/preflight run with chosen model settings.
