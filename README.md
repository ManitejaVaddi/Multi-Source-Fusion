# Strategic Fusion Dashboard

A web-based intelligence fusion dashboard that unifies OSINT, HUMINT, and IMINT into a single, interactive geospatial interface.

The project solves the problem of fragmented intelligence data by ingesting information from:
- local samples
- MongoDB
- AWS S3
- CSV / JSON / XLSX
- image uploads

It then visualizes everything as map markers on a fixed terrain map, with hover popups for metadata and imagery inspection.

---

## Demo status

- **Demo mode**: runs immediately with local sample data
- **Live mode**: supports MongoDB + AWS S3 when environment variables are configured
- **Production readiness**: backend and frontend are separated, and the repo is organized for clarity

---

## Features

- Multi-source ingestion: `MongoDB`, `AWS S3`, `CSV`, `JSON`, `XLSX`, image uploads
- Unified data normalization into one schema
- Fixed terrain map using `Leaflet.js`
- Interactive markers with hover popups
- Drag-and-drop dataset and imagery upload
- Filters by intelligence type and source
- Status and export controls
- Optional auto-refresh and live feed simulation

---

## Tech Stack

- Python 3
- `http.server` backend
- `pymongo` for MongoDB
- `boto3` for AWS S3
- `PyJWT` for token support
- `Leaflet.js` for mapping
- HTML, CSS, JavaScript for frontend

---

## Run the project

### 1. Install dependencies
```powershell
pip install -r requirements.txt
```

### 2. Run the backend
```powershell
python backend/server.py
```


### Ingestion

The backend loads intelligence records from several sources:
- `data/osint_mongo.json` and `data/osint_s3.json` for demo-mode samples
- `data/manual_reports.json` for manual uploads
- `data/simulated_feed.json` for simulated live data
- MongoDB documents when configured
- JSON files in S3 when configured

Incoming records are normalized into a common schema with fields like:
- `intelType`
- `sourceName`
- `title`
- `description`
- `lat`, `lon`
- `confidence`
- `imagePath`
- `metadata`

### Processing

The backend normalizes raw data and enriches it with default values, inferred tags, and marker shape metadata.
It also supports manual dataset ingestion, image upload ingestion, and optional MongoDB/S3 persistence.

### Visualization

The frontend loads `/api/intelligence` and renders every record as a marker on a fixed terrain map.
Markers are colored and shaped by intelligence type:
- OSINT = circle
- HUMINT = square
- IMINT = diamond

Hovering a marker opens a popup with full metadata and image preview if available.

---

## Local demo usage

### Upload a dataset
Use the **Dataset Ingestion** form and upload `sample_upload.csv` or any supported file.
Supported fields: `title`, `description`, `lat`, `lon`, `confidence`, `intelType`, `sourceName`.

### Upload an image
Use the **IMINT Upload** form and provide latitude, longitude, and imagery.
That upload creates a new IMINT marker on the map.

### Filters
Use the sidebar checkboxes and dropdowns to filter intelligence by type and source.



