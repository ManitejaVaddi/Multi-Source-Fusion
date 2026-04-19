# Strategic Fusion Dashboard

A web-based intelligence fusion platform that ingests OSINT, HUMINT, and IMINT from multiple sources and visualizes them on a unified fixed-terrain geospatial dashboard.

The app supports two modes:

- `sample mode`: runs instantly with local sample data
- `live mode`: connects to real `MongoDB` and `AWS S3` when configured

## Features

- Unified ingestion for `MongoDB`, `AWS S3`, `CSV`, `JSON`, `XLSX`, and imagery
- Python backend APIs for ingestion, normalization, and retrieval
- `Leaflet`-based fixed terrain map with interactive intelligence markers
- Hover-based popups for metadata and image preview
- Drag-and-drop upload zones for field reports and imagery
- Source and intelligence-type filters for operational analysis
- Fallback sample datasets for offline demos and interviews

## Tech Stack

- `Python 3`
- `http.server`
- `pymongo`
- `boto3`
- `Leaflet.js`
- `HTML`
- `CSS`
- `JavaScript`


## Screenshots

Add screenshots here after you run the project.

- Suggested shot 1: full dashboard view with markers visible
- Suggested shot 2: hover popup showing IMINT preview
- Suggested shot 3: dataset upload section with sample ingestion

You can save them in a folder like:

```text
screenshots/
```

And reference them here later:

```md
![Dashboard](screenshots/dashboard.png)
![Hover Popup](screenshots/hover-popup.png)
```

## Setup

### 1. Install dependencies for live cloud/database mode

If you want real `MongoDB` and `S3` support, install:

powershell
pip install -r requirements.txt


If you only want the demo version, you can skip that step.

### 2. Configure environment variables for live mode

Use [.env.example](c:/Users/Maniteja/Desktop/New%20folder/.env.example) as reference.

Set these in PowerShell before running:

```powershell
$env:MONGO_URI="mongodb://localhost:27017"
$env:MONGO_DB_NAME="intelligence"
$env:MONGO_COLLECTION="osint_records"
$env:AWS_DEFAULT_REGION="ap-south-1"
$env:AWS_S3_BUCKET="your-osint-bucket"
$env:AWS_S3_PREFIX="osint/"

### 3. Optional: seed live sources with sample data

To seed MongoDB with example OSINT records:

```powershell
python seed_mongo.py
```

To upload example OSINT JSON into your S3 bucket:

```powershell
python upload_s3_sample.py
```

Files used:

- [cloud_samples/mongo_seed.json](c:/Users/Maniteja/Desktop/New%20folder/cloud_samples/mongo_seed.json)
- [cloud_samples/s3_osint_batch.json](c:/Users/Maniteja/Desktop/New%20folder/cloud_samples/s3_osint_batch.json)



### Upload dataset files

Use the **Dataset Ingestion** form on the left side.

You can:

- drag and drop a file into the dataset drop zone
- click the drop zone to browse manually

Supported columns for `CSV`, `JSON`, or `XLSX`:

- `title`
- `description`
- `lat`
- `lon`
- `confidence`
- `intelType`
- `sourceName`

You can test quickly with:

```text
sample_upload.csv
```

### Upload imagery

Use the **IMINT Upload** form.

You can:

- drag and drop an image into the imagery drop zone
- click the drop zone to browse manually

Required:

- image file
- latitude
- longitude

Optional:

- title
- source name
- description

After upload, the image becomes a new IMINT marker on the map.

### Filter intelligence records

Use the filter panel to:

- show or hide `OSINT`, `HUMINT`, and `IMINT`
- filter markers by source name

This makes it easier to inspect one intelligence stream at a time.

## API Endpoints

- `GET /api/intelligence`
- `GET /api/source-status`
- `POST /api/upload/dataset`
- `POST /api/upload/image`

## Live source format expectations

### MongoDB documents

Each document should roughly follow:

```json
{
  "id": "mongo-101",
  "intelType": "OSINT",
  "sourceName": "MongoDB OSINT",
  "title": "Activity report",
  "description": "Observed pattern",
  "lat": 34.5,
  "lon": 72.1,
  "timestamp": "2026-04-18T10:10:00Z",
  "confidence": 80,
  "imagePath": "",
  "metadata": {
    "channel": "social"
  }
}
```

### S3 objects

Each S3 JSON file may contain:

- a single object
- an array of objects
- an object with a top-level `records` array
