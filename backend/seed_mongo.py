import json
import os
from pathlib import Path

from pymongo import MongoClient


BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
SEED_FILE = REPO_ROOT / "cloud_samples" / "mongo_seed.json"


def main():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB_NAME", "intelligence")
    collection_name = os.getenv("MONGO_COLLECTION", "osint_records")

    records = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    client = MongoClient(mongo_uri)
    try:
        collection = client[db_name][collection_name]
        collection.delete_many({})
        if records:
            collection.insert_many(records)
        print(f"Seeded {len(records)} records into {db_name}.{collection_name}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
