import json
import sys
import argparse
from datetime import datetime, timezone

from database import SessionLocal, Profile, create_tables, engine
from sqlalchemy import text

try:
    import uuid6
    def new_uuid() -> str:
        return str(uuid6.uuid7())
except ImportError:
    import uuid
    def new_uuid() -> str:
        return str(uuid.uuid4())


def get_age_group(age: int) -> str:
    if age <= 12:
        return "child"
    elif age <= 17:
        return "teenager"
    elif age <= 59:
        return "adult"
    else:
        return "senior"


def seed(filepath: str = "profiles.json"):
    print(f"Creating tables if they don't exist...")
    create_tables()

    print(f"Loading data from {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Support both a list directly or {"data": [...]}
    if isinstance(data, list):
        profiles_raw = data
    elif isinstance(data, dict):
        profiles_raw = data.get("data", data.get("profiles", []))
    else:
        print("ERROR: Unexpected JSON format")
        sys.exit(1)

    print(f"Found {len(profiles_raw)} profiles to seed...")

    db = SessionLocal()
    try:
        # Fetch existing names for duplicate check
        existing = set(
            row[0] for row in db.execute(text("SELECT name FROM profiles")).fetchall()
        )
        print(f"Already have {len(existing)} profiles in DB.")

        inserted = 0
        skipped = 0
        batch = []

        for raw in profiles_raw:
            name = raw.get("name", "").strip()
            if not name or name in existing:
                skipped += 1
                continue

            age = int(raw.get("age", 0))
            age_group = raw.get("age_group") or get_age_group(age)

            profile = Profile(
                id=new_uuid(),
                name=name,
                gender=raw.get("gender", "").lower(),
                gender_probability=float(raw.get("gender_probability", 0.0)),
                age=age,
                age_group=age_group.lower(),
                country_id=raw.get("country_id", raw.get("country", {}).get("id", "")).upper(),
                country_name=raw.get("country_name", raw.get("country", {}).get("name", "")),
                country_probability=float(raw.get("country_probability", raw.get("country", {}).get("probability", 0.0))),
                created_at=datetime.now(timezone.utc),
            )
            batch.append(profile)
            existing.add(name)
            inserted += 1

            if len(batch) >= 200:
                db.bulk_save_objects(batch)
                db.commit()
                batch = []
                print(f"  ...committed {inserted} so far")

        if batch:
            db.bulk_save_objects(batch)
            db.commit()

        print(f"\nDone! Inserted: {inserted}, Skipped (duplicates): {skipped}")

    except Exception as e:
        db.rollback()
        print(f"ERROR during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="profiles.json", help="Path to JSON file")
    args = parser.parse_args()
    seed(args.file)