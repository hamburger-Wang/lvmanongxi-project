# QGIS Desktop Variant

This directory preserves the complete desktop/QGIS version received from the team as an independent source snapshot. It intentionally remains separate from the root Web application so the two implementations can be compared, run, and evolved without overwriting each other.

The root project already integrates the shared QGIS interfaces required by the current application:

- `core/qgis_pipeline/`: QGIS preprocessing and HDF5 packaging scripts.
- `ui_modules/gis_preprocess_widget.py`: Qt preprocessing view.
- `ui_modules/gis_worker.py`: isolated QGIS subprocess worker.
- `config.py` and `ui_modules/ui_main.py`: QGIS configuration and menu entry.

This variant retains its own model, Qt, and preprocessing files for traceability. Do not copy its virtual environment, IDE metadata, generated GIS data, or downloaded datasets into Git.

For the current Web integration, use the root `backend/`, `web/`, and `docs/` directories. For the desktop QGIS workflow, see `../../docs/qgis-preprocessing-guide.md`.
