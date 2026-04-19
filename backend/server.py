import csv
import json
import mimetypes
import os
import shutil
import urllib.parse
import uuid
import zipfile
from io import StringIO
from datetime import datetime, timezone, timedelta
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from xml.etree import ElementTree as ET
import hmac
import hashlib
import base64

try:
    import boto3
except ImportError:
    boto3 = None

try:
    from pymongo import MongoClient
except ImportError:
    MongoClient = None

try:
    import jwt
except ImportError:
    jwt = None

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent

STATIC_DIR = REPO_ROOT / "frontend" / "static"
DATA_DIR = REPO_ROOT / "data"
UPLOADS_DIR = REPO_ROOT / "uploads" / "images"
MANUAL_REPORTS_FILE = DATA_DIR / "manual_reports.json"

# ========== SERVER CONFIGURATION ==========
HOST = os.getenv("FUSION_HOST", "127.0.0.1")
PORT = int(os.getenv("FUSION_PORT", "8000"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# ========== MONGODB CONFIGURATION ==========
MONGO_URI = os.getenv("MONGO_URI", "").strip()
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "").strip()
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "").strip()

# ========== AWS S3 CONFIGURATION ==========
S3_BUCKET = os.getenv("AWS_S3_BUCKET", "").strip()
S3_PREFIX = os.getenv("AWS_S3_PREFIX", "").strip()
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "").strip()
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()

# ========== JWT AUTHENTICATION CONFIGURATION ==========
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "").strip()
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

# ========== IMAGE UPLOAD SETTINGS ==========
IMAGE_UPLOAD_BACKEND = os.getenv("IMAGE_UPLOAD_BACKEND", "local").lower()
MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", "50"))

# ========== DATA STORAGE SETTINGS ==========
MANUAL_REPORTS_BACKEND = os.getenv("MANUAL_REPORTS_BACKEND", "json").lower()

SIMULATED_FEED_FILE = DATA_DIR / "simulated_feed.json"


def validate_configuration():
    """Validate environment configuration and log warnings/errors."""
    issues = []
    
    # Check MongoDB configuration
    mongo_enabled = all([MongoClient is not None, MONGO_URI, MONGO_DB_NAME, MONGO_COLLECTION])
    if not mongo_enabled:
        if MongoClient is None:
            issues.append("[WARNING] pymongo not installed. MongoDB features disabled.")
        elif not MONGO_URI:
            issues.append("[INFO] MONGO_URI not configured. Running in sample mode.")
    else:
        print(f"[OK] MongoDB enabled: {MONGO_URI}")
    
    # Check S3 configuration
    s3_enabled = all([boto3 is not None, S3_BUCKET, AWS_REGION])
    if not s3_enabled:
        if boto3 is None:
            issues.append("[WARNING] boto3 not installed. AWS S3 features disabled.")
        elif not S3_BUCKET:
            issues.append("[INFO] AWS_S3_BUCKET not configured. Running in sample mode.")
    else:
        print(f"[OK] AWS S3 enabled: s3://{S3_BUCKET}/{S3_PREFIX}")
    
    # Check JWT configuration for authentication
    if not JWT_SECRET_KEY:
        issues.append("[WARNING] JWT_SECRET_KEY not configured. Authentication will use default key (insecure).")
    else:
        print("[OK] JWT authentication enabled.")
    
    # Check image upload backend
    if IMAGE_UPLOAD_BACKEND not in ["local", "s3"]:
        issues.append(f"[ERROR] Invalid IMAGE_UPLOAD_BACKEND: {IMAGE_UPLOAD_BACKEND}. Must be 'local' or 's3'.")
    elif IMAGE_UPLOAD_BACKEND == "s3" and not s3_enabled:
        issues.append("[ERROR] IMAGE_UPLOAD_BACKEND set to 's3' but S3 not configured.")
    else:
        print(f"[OK] Image upload backend: {IMAGE_UPLOAD_BACKEND}")
    
    # Check data storage backend
    if MANUAL_REPORTS_BACKEND not in ["json", "mongodb"]:
        issues.append(f"[ERROR] Invalid MANUAL_REPORTS_BACKEND: {MANUAL_REPORTS_BACKEND}. Must be 'json' or 'mongodb'.")
    elif MANUAL_REPORTS_BACKEND == "mongodb" and not mongo_enabled:
        issues.append("[ERROR] MANUAL_REPORTS_BACKEND set to 'mongodb' but MongoDB not configured.")
    else:
        print(f"[OK] Data storage backend: {MANUAL_REPORTS_BACKEND}")
    
    # Print all issues
    for issue in issues:
        print(issue)
    
    # Return status
    return not any("ERROR" in issue for issue in issues)


def ensure_directories():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    if not MANUAL_REPORTS_FILE.exists():
        MANUAL_REPORTS_FILE.write_text("[]", encoding="utf-8")
    if not SIMULATED_FEED_FILE.exists():
        SIMULATED_FEED_FILE.write_text("[]", encoding="utf-8")


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ========== JWT AUTHENTICATION FUNCTIONS ==========

def get_jwt_secret():
    """Get JWT secret key, use default if not configured."""
    return JWT_SECRET_KEY or "default-insecure-key-change-in-production"


def generate_jwt_token(user_id="analyst", username="demo"):
    """Generate a JWT token for authentication."""
    if jwt is None:
        return None
    
    payload = {
        "user_id": user_id,
        "username": username,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    
    try:
        token = jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)
        return token
    except Exception as e:
        print(f"[ERROR] Failed to generate JWT token: {e}")
        return None


def verify_jwt_token(token):
    """Verify a JWT token and return payload if valid."""
    if jwt is None or not token:
        return None
    
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    except Exception:
        return None


# ========== S3 IMAGE UPLOAD FUNCTIONS ==========

def upload_image_to_s3(image_bytes, filename):
    """Upload image to S3 and return the URL."""
    if IMAGE_UPLOAD_BACKEND != "s3" or not boto3:
        return None
    
    try:
        client = boto3.client(
            "s3",
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )
        key = f"{S3_PREFIX}{uuid.uuid4().hex}_{filename}"
        client.put_object(Bucket=S3_BUCKET, Key=key, Body=image_bytes)
        url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"
        return url
    except Exception as e:
        print(f"[ERROR] S3 upload failed: {e}")
        return None


KEYWORD_TAGS = {
    "threat": ["threat", "attack", "hostile", "weapon", "risk"],
    "movement": ["movement", "convoy", "vehicle", "transit", "route", "staging"],
    "communications": ["radio", "signal", "broadcast", "comms", "communication"],
    "logistics": ["fuel", "supply", "logistics", "stockpile", "shipment"],
    "surveillance": ["imagery", "satellite", "drone", "thermal", "surveillance"],
}


def infer_tags(record):
    searchable = " ".join(
        str(record.get(field, ""))
        for field in ["title", "description", "summary", "sourceName", "intelType"]
    ).lower()
    existing_tags = record.get("metadata", {}).get("tags", [])
    tags = {str(tag).lower() for tag in existing_tags}
    for label, keywords in KEYWORD_TAGS.items():
        if any(keyword in searchable for keyword in keywords):
            tags.add(label)
    if record.get("intelType", "").upper() == "IMINT":
        tags.add("imagery")
    return sorted(tags)


def classify_priority(confidence):
    if confidence >= 80:
        return "HIGH"
    if confidence >= 60:
        return "MEDIUM"
    return "LOW"


def determine_marker_shape(intel_type):
    shapes = {
        "OSINT": "circle",
        "HUMINT": "square",
        "IMINT": "diamond",
    }
    return shapes.get(intel_type.upper(), "circle")


def normalize_record(record, source_name):
    lat = safe_float(record.get("lat") or record.get("latitude"))
    lon = safe_float(record.get("lon") or record.get("longitude"))
    confidence = safe_int(record.get("confidence") or 50, 50)
    metadata = record.get("metadata") or {}
    normalized = {
        "id": str(record.get("id") or uuid.uuid4()),
        "intelType": str(record.get("intelType") or record.get("intel_type") or "UNKNOWN").upper(),
        "sourceName": record.get("sourceName") or source_name,
        "title": record.get("title") or "Untitled Node",
        "description": record.get("description") or record.get("summary") or "",
        "lat": lat,
        "lon": lon,
        "timestamp": record.get("timestamp") or iso_now(),
        "confidence": confidence,
        "imagePath": record.get("imagePath") or record.get("image_path") or "",
        "metadata": metadata,
        "priority": str(record.get("priority") or classify_priority(confidence)).upper(),
        "markerShape": record.get("markerShape") or determine_marker_shape(str(record.get("intelType") or "")),
    }
    normalized["tags"] = record.get("tags") or infer_tags(normalized)
    return normalized


def read_json_records(path, source_name):
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("records", [])
    return [normalize_record(item, source_name) for item in payload]


def get_source_status():
    mongo_enabled = all([MongoClient is not None, MONGO_URI, MONGO_DB_NAME, MONGO_COLLECTION])
    s3_enabled = all([boto3 is not None, S3_BUCKET])
    return {
        "mongo": {
            "enabled": mongo_enabled,
            "libraryInstalled": MongoClient is not None,
            "configured": all([MONGO_URI, MONGO_DB_NAME, MONGO_COLLECTION]),
            "mode": "live" if mongo_enabled else "sample",
        },
        "s3": {
            "enabled": s3_enabled,
            "libraryInstalled": boto3 is not None,
            "configured": bool(S3_BUCKET),
            "mode": "live" if s3_enabled else "sample",
        },
    }


def fetch_mongo_records():
    if not all([MongoClient is not None, MONGO_URI, MONGO_DB_NAME, MONGO_COLLECTION]):
        return read_json_records(DATA_DIR / "osint_mongo.json", "MongoDB OSINT")

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    try:
        collection = client[MONGO_DB_NAME][MONGO_COLLECTION]
        documents = list(collection.find({}, {"_id": 0}))
        return [normalize_record(item, "MongoDB OSINT") for item in documents]
    finally:
        client.close()


def parse_s3_object_records(content, key):
    try:
        payload = json.loads(content.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError(f"S3 object {key} is not valid UTF-8 JSON.") from exc

    if isinstance(payload, dict):
        payload = payload.get("records", [payload])
    if not isinstance(payload, list):
        raise ValueError(f"S3 object {key} must contain a JSON array or a records object.")
    return [normalize_record(item, "AWS S3 OSINT") for item in payload]


def fetch_s3_records():
    if not all([boto3 is not None, S3_BUCKET]):
        return read_json_records(DATA_DIR / "osint_s3.json", "AWS S3 OSINT")

    client = boto3.client("s3", region_name=AWS_REGION or None)
    kwargs = {"Bucket": S3_BUCKET}
    if S3_PREFIX:
        kwargs["Prefix"] = S3_PREFIX

    records = []
    continuation_token = None
    while True:
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token
        response = client.list_objects_v2(**kwargs)
        for item in response.get("Contents", []):
            key = item["Key"]
            if not key.lower().endswith(".json"):
                continue
            obj = client.get_object(Bucket=S3_BUCKET, Key=key)
            records.extend(parse_s3_object_records(obj["Body"].read(), key))
        if not response.get("IsTruncated"):
            break
        continuation_token = response.get("NextContinuationToken")
    return records


def load_all_records():
    records = []
    records.extend(fetch_mongo_records())
    records.extend(fetch_s3_records())
    records.extend(read_json_records(DATA_DIR / "manual_reports.json", "Manual Ingestion"))
    records.extend(read_json_records(SIMULATED_FEED_FILE, "Simulated Live Feed"))
    return records


def save_manual_records(records):
    """Save manual records to configured backend (JSON or MongoDB)."""
    if MANUAL_REPORTS_BACKEND == "mongodb" and MongoClient is not None and MONGO_URI:
        try:
            client = MongoClient(MONGO_URI)
            db = client[MONGO_DB_NAME]
            collection = db["manual_reports"]
            collection.delete_many({})  # Clear old records
            if records:
                collection.insert_many(records)
            client.close()
            print(f"[OK] Saved {len(records)} records to MongoDB")
            return
        except Exception as e:
            print(f"[WARNING] Failed to save to MongoDB: {e}. Falling back to JSON.")
    
    # Fallback to JSON
    MANUAL_REPORTS_FILE.write_text(json.dumps(records, indent=2), encoding="utf-8")


def append_manual_records(new_records):
    """Append new records to manual reports storage."""
    if MANUAL_REPORTS_BACKEND == "mongodb" and MongoClient is not None and MONGO_URI:
        try:
            client = MongoClient(MONGO_URI)
            db = client[MONGO_DB_NAME]
            collection = db["manual_reports"]
            if new_records:
                collection.insert_many(new_records)
            client.close()
            print(f"[OK] Appended {len(new_records)} records to MongoDB")
            return
        except Exception as e:
            print(f"[WARNING] Failed to append to MongoDB: {e}. Falling back to JSON.")
    
    # Fallback to JSON
    records = read_json_records(MANUAL_REPORTS_FILE, "Manual Ingestion")
    records.extend(new_records)
    save_manual_records(records)


def append_simulated_record(record):
    records = read_json_records(SIMULATED_FEED_FILE, "Simulated Live Feed")
    records.append(record)
    SIMULATED_FEED_FILE.write_text(json.dumps(records, indent=2), encoding="utf-8")


def parse_csv_dataset(content):
    text = content.decode("utf-8-sig")
    rows = csv.DictReader(text.splitlines())
    return [dict(row) for row in rows]


def parse_json_dataset(content):
    payload = json.loads(content.decode("utf-8"))
    if isinstance(payload, dict):
        return payload.get("records", [payload])
    return payload


def excel_column_letters_to_index(letters):
    result = 0
    for char in letters:
        result = result * 26 + (ord(char.upper()) - 64)
    return result - 1


def parse_xlsx_dataset(content):
    with zipfile.ZipFile(io_bytes := BytesIO(content)) as workbook:
        shared_strings = []
        if "xl/sharedStrings.xml" in workbook.namelist():
            root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for item in root.findall("a:si", ns):
                shared_strings.append("".join(item.itertext()))

        sheet_name = "xl/worksheets/sheet1.xml"
        if sheet_name not in workbook.namelist():
            return []

        root = ET.fromstring(workbook.read(sheet_name))
        ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        rows = []
        for row in root.findall(".//a:row", ns):
            values = {}
            for cell in row.findall("a:c", ns):
                ref = cell.attrib.get("r", "")
                letters = "".join(char for char in ref if char.isalpha())
                idx = excel_column_letters_to_index(letters) if letters else 0
                cell_type = cell.attrib.get("t")
                value_node = cell.find("a:v", ns)
                value = value_node.text if value_node is not None else ""
                if cell_type == "s" and value:
                    value = shared_strings[int(value)]
                values[idx] = value
            if values:
                max_idx = max(values)
                rows.append([values.get(i, "") for i in range(max_idx + 1)])

        if not rows:
            return []
        headers = [str(item).strip() for item in rows[0]]
        parsed = []
        for row in rows[1:]:
            parsed.append({headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))})
        return parsed


class BytesIO:
    def __init__(self, data):
        self._data = data
        self._index = 0

    def read(self, size=-1):
        if size is None or size < 0:
            size = len(self._data) - self._index
        chunk = self._data[self._index:self._index + size]
        self._index += len(chunk)
        return chunk

    def seek(self, index, whence=0):
        if whence == 0:
            self._index = index
        elif whence == 1:
            self._index += index
        elif whence == 2:
            self._index = len(self._data) + index

    def tell(self):
        return self._index


def parse_dataset_file(filename, content):
    ext = Path(filename).suffix.lower()
    if ext == ".csv":
        return parse_csv_dataset(content)
    if ext == ".json":
        return parse_json_dataset(content)
    if ext == ".xlsx":
        return parse_xlsx_dataset(content)
    raise ValueError("Unsupported dataset format. Use CSV, JSON, or XLSX.")


def parse_multipart(handler):
    content_type = handler.headers.get("Content-Type", "")
    content_length = int(handler.headers.get("Content-Length", "0"))
    body = handler.rfile.read(content_length)
    fake_headers = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=default).parsebytes(fake_headers + body)
    fields = {}
    files = {}

    for part in message.iter_parts():
        disposition = part.get("Content-Disposition", "")
        if "form-data" not in disposition:
            continue
        name = part.get_param("name", header="content-disposition")
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            files[name] = {"filename": filename, "content": payload}
        else:
            fields[name] = payload.decode("utf-8").strip()
    return fields, files


class FusionDashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/intelligence":
            params = urllib.parse.parse_qs(parsed.query)
            records = load_all_records()
            if params.get("format", ["json"])[0] == "csv":
                self.send_csv(records)
                return
            self.send_json({"records": records, "sources": get_source_status()})
            return
        if parsed.path == "/api/simulate-feed":
            self.handle_simulated_feed()
            return
        if parsed.path == "/api/source-status":
            self.send_json(get_source_status())
            return
        if parsed.path.startswith("/uploads/"):
            target = REPO_ROOT / parsed.path.lstrip("/")
            self.serve_file(target)
            return

        target = STATIC_DIR / ("index.html" if parsed.path == "/" else parsed.path.lstrip("/"))
        self.serve_file(target)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/upload/dataset":
            self.handle_dataset_upload()
            return
        if parsed.path == "/api/upload/image":
            self.handle_image_upload()
            return
        if parsed.path == "/api/simulate-feed":
            self.handle_simulated_feed()
            return
        self.send_error(404, "Not found")

    def handle_dataset_upload(self):
        try:
            fields, files = parse_multipart(self)
            uploaded = files.get("file")
            if not uploaded:
                self.send_json({"error": "Dataset file is required."}, 400)
                return

            raw_records = parse_dataset_file(uploaded["filename"], uploaded["content"])
            intel_type = fields.get("intelType", "HUMINT").upper()
            source_name = fields.get("sourceName", "Manual Dataset Upload")
            normalized = []
            for item in raw_records:
                item["intelType"] = item.get("intelType") or intel_type
                item["sourceName"] = item.get("sourceName") or source_name
                normalized.append(normalize_record(item, source_name))

            append_manual_records(normalized)
            self.send_json({"message": f"Ingested {len(normalized)} records.", "records": normalized})
        except Exception as exc:
            self.send_json({"error": str(exc)}, 400)

    def handle_image_upload(self):
        try:
            fields, files = parse_multipart(self)
            uploaded = files.get("file")
            if not uploaded:
                self.send_json({"error": "Image file is required."}, 400)
                return

            ext = Path(uploaded["filename"]).suffix.lower()
            if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
                self.send_json({"error": "Only JPG, JPEG, PNG, and WEBP images are supported."}, 400)
                return

            # Check file size
            file_size_mb = len(uploaded["content"]) / (1024 * 1024)
            if file_size_mb > MAX_IMAGE_SIZE_MB:
                self.send_json({"error": f"Image size exceeds {MAX_IMAGE_SIZE_MB}MB limit."}, 400)
                return

            # Upload to S3 if configured, otherwise store locally
            if IMAGE_UPLOAD_BACKEND == "s3":
                image_path = upload_image_to_s3(uploaded["content"], uploaded["filename"])
                if not image_path:
                    self.send_json({"error": "Failed to upload image to S3. Check configuration."}, 400)
                    return
            else:
                # Store locally
                unique_name = f"{uuid.uuid4().hex}{ext}"
                destination = UPLOADS_DIR / unique_name
                destination.write_bytes(uploaded["content"])
                image_path = f"/uploads/images/{unique_name}"

            record = normalize_record(
                {
                    "intelType": fields.get("intelType", "IMINT"),
                    "sourceName": fields.get("sourceName", "Manual Image Upload"),
                    "title": fields.get("title", Path(uploaded["filename"]).stem),
                    "description": fields.get("description", ""),
                    "lat": fields.get("lat"),
                    "lon": fields.get("lon"),
                    "confidence": fields.get("confidence", "70"),
                    "imagePath": image_path,
                    "metadata": {
                        "filename": uploaded["filename"],
                        "uploadedAt": iso_now(),
                        "uploadBackend": IMAGE_UPLOAD_BACKEND,
                    },
                },
                fields.get("sourceName", "Manual Image Upload"),
            )

            append_manual_records([record])
            self.send_json({"message": "Image ingested.", "record": record})
        except Exception as exc:
            self.send_json({"error": str(exc)}, 400)

    def handle_simulated_feed(self):
        try:
            now = datetime.now(timezone.utc)
            sample_records = [
                {
                    "intelType": "OSINT",
                    "sourceName": "Simulated S3 Feed",
                    "title": "Automated Feed Alert",
                    "description": "Automated ingestion detected possible supply movement near the eastern corridor.",
                    "lat": 25 + (now.second % 50),
                    "lon": 20 + (now.minute % 60),
                    "confidence": 65 + (now.second % 25),
                    "timestamp": iso_now(),
                    "metadata": {"feedType": "s3-mock", "mode": "simulated"},
                },
                {
                    "intelType": "HUMINT",
                    "sourceName": "Simulated Field Feed",
                    "title": "Field Observer Update",
                    "description": "Human source reported vehicle regrouping along the river approach.",
                    "lat": 30 + (now.minute % 40),
                    "lon": 35 + (now.second % 45),
                    "confidence": 55 + (now.minute % 35),
                    "timestamp": iso_now(),
                    "metadata": {"feedType": "humint-mock", "mode": "simulated"},
                },
            ]
            created = []
            for item in sample_records:
                record = normalize_record(item, item["sourceName"])
                append_simulated_record(record)
                created.append(record)
            self.send_json({"message": f"Simulated live feed added {len(created)} records.", "records": created})
        except Exception as exc:
            self.send_json({"error": str(exc)}, 400)

    def serve_file(self, target):
        target = target.resolve()
        allowed_roots = [STATIC_DIR.resolve(), (REPO_ROOT / "uploads").resolve()]
        if not target.exists() or not any(str(target).startswith(str(root)) for root in allowed_roots):
            self.send_error(404, "File not found")
            return

        mime, _ = mimetypes.guess_type(str(target))
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.end_headers()
        with target.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile)

    def send_json(self, payload, status=200):
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_csv(self, records):
        output = StringIO()
        fieldnames = [
            "id",
            "intelType",
            "sourceName",
            "title",
            "description",
            "lat",
            "lon",
            "timestamp",
            "confidence",
            "priority",
            "markerShape",
            "tags",
            "imagePath",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            row = {key: record.get(key, "") for key in fieldnames}
            row["tags"] = ", ".join(record.get("tags", []))
            writer.writerow(row)
        content = output.getvalue().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="fusion-dashboard-export.csv"')
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format_, *args):
        return


def main():
    print("\n" + "="*70)
    print("  STRATEGIC FUSION DASHBOARD - STARTING UP")
    print("="*70 + "\n")
    
    ensure_directories()
    
    print("Configuration Validation:")
    print("-" * 70)
    config_valid = validate_configuration()
    print("-" * 70 + "\n")
    
    if not config_valid:
        print("[WARNING] Configuration errors detected. Some features may be unavailable.")
    
    print(f"Server started: http://{HOST}:{PORT}")
    print(f"Dashboard mode: {'LIVE' if config_valid else 'SAMPLE'}")
    print(f"Debug mode: {DEBUG}")
    print("\nPress Ctrl+C to stop the server.\n")
    print("="*70 + "\n")
    
    server = HTTPServer((HOST, PORT), FusionDashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\nServer shutting down...")
        server.server_close()
        print("Goodbye!")


if __name__ == "__main__":
    main()
