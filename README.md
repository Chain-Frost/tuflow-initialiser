# TUFLOW Initialiser

Standalone **2D rainfall-on-grid (ROG)** TUFLOW project and terrain hydrology initialiser.

Input: a projected terrain DEM and AOI polygon(s). The planned workflow delineates every upstream contributing flow path to the AOI, adds a configurable circular AOI buffer, generates stream paths with equal-area slope, and populates `2d_code`, `2d_loc` and `2d_rf` using TUFLOW-generated schemas.

The TUFLOW project setup and templates have moved from `ryan-tools`. The runtime has **no dependency on ryan-tools**. Optionally, project utility scripts can be copied from an explicitly provided external directory.

**Development status:** feature branch, not yet validated end-to-end on Windows with installed GRASS GIS and TUFLOW. Do not treat the generated geometries as production-verified.

Documentation: [architecture](docs/architecture.md), [validation](docs/validation.md), [migration](docs/migration.md) and [future work](docs/future-work.md).

License: [Sustainable Use License 1.0](LICENSE).
