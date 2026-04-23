from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc
from typing import Optional
from datetime import timezone
 
from database import get_db, Profile, create_tables
from parser import parse_nl_query
 
app = FastAPI(title="Insighta Labs – Intelligence Query Engine")
 
# CORS — required by grading script
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
 
@app.on_event("startup")
def on_startup():
    create_tables()
 
 
# Helpers
 
SORTABLE_FIELDS = {
    "age": Profile.age,
    "created_at": Profile.created_at,
    "gender_probability": Profile.gender_probability,
}
 
VALID_GENDERS = {"male", "female"}
VALID_AGE_GROUPS = {"child", "teenager", "adult", "senior"}
VALID_ORDERS = {"asc", "desc"}
 
 
def format_profile(p: Profile) -> dict:
    created_at = p.created_at
    if created_at and created_at.tzinfo is None:
        # MySQL stores UTC but without tzinfo — attach it
        from datetime import timezone as tz
        created_at = created_at.replace(tzinfo=tz.utc)
    return {
        "id": p.id,
        "name": p.name,
        "gender": p.gender,
        "gender_probability": p.gender_probability,
        "age": p.age,
        "age_group": p.age_group,
        "country_id": p.country_id,
        "country_name": p.country_name,
        "country_probability": p.country_probability,
        "created_at": created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if created_at else None,
    }
 
 
def apply_filters(query, gender, age_group, country_id, min_age, max_age,
                  min_gender_probability, min_country_probability):
    if gender is not None:
        query = query.filter(Profile.gender == gender)
    if age_group is not None:
        query = query.filter(Profile.age_group == age_group)
    if country_id is not None:
        query = query.filter(Profile.country_id == country_id.upper())
    if min_age is not None:
        query = query.filter(Profile.age >= min_age)
    if max_age is not None:
        query = query.filter(Profile.age <= max_age)
    if min_gender_probability is not None:
        query = query.filter(Profile.gender_probability >= min_gender_probability)
    if min_country_probability is not None:
        query = query.filter(Profile.country_probability >= min_country_probability)
    return query
 
 
def apply_sort(query, sort_by: Optional[str], order: str):
    col = SORTABLE_FIELDS.get(sort_by or "created_at", Profile.created_at)
    return query.order_by(asc(col) if order == "asc" else desc(col))
 
 
def paginate(query, page: int, limit: int):
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return total, items
 
 
# GET /api/profiles
@app.get("/api/profiles")
def get_profiles(
    gender: Optional[str] = Query(None),
    age_group: Optional[str] = Query(None),
    country_id: Optional[str] = Query(None),
    min_age: Optional[int] = Query(None, ge=0),
    max_age: Optional[int] = Query(None, ge=0),
    min_gender_probability: Optional[float] = Query(None, ge=0.0, le=1.0),
    min_country_probability: Optional[float] = Query(None, ge=0.0, le=1.0),
    sort_by: Optional[str] = Query(None),
    order: str = Query("asc"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    # Validate enum-like params
    if gender is not None and gender not in VALID_GENDERS:
        raise HTTPException(
            status_code=422,
            detail={"status": "error", "message": "Invalid query parameters"},
        )
    if age_group is not None and age_group not in VALID_AGE_GROUPS:
        raise HTTPException(
            status_code=422,
            detail={"status": "error", "message": "Invalid query parameters"},
        )
    if sort_by is not None and sort_by not in SORTABLE_FIELDS:
        raise HTTPException(
            status_code=422,
            detail={"status": "error", "message": "Invalid query parameters"},
        )
    if order not in VALID_ORDERS:
        raise HTTPException(
            status_code=422,
            detail={"status": "error", "message": "Invalid query parameters"},
        )
 
    q = db.query(Profile)
    q = apply_filters(q, gender, age_group, country_id, min_age, max_age,
                      min_gender_probability, min_country_probability)
    q = apply_sort(q, sort_by, order)
    total, profiles = paginate(q, page, limit)
 
    return {
        "status": "success",
        "page": page,
        "limit": limit,
        "total": total,
        "data": [format_profile(p) for p in profiles],
    }
 
 
# GET /api/profiles/search  (natural language)
@app.get("/api/profiles/search")
def search_profiles(
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    sort_by: Optional[str] = Query(None),
    order: str = Query("asc"),
    db: Session = Depends(get_db),
):
    if not q or not q.strip():
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "message": "Missing or empty parameter: q"},
        )
 
    parsed = parse_nl_query(q)
    if parsed is None:
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "message": "Unable to interpret query"},
        )
 
    if sort_by is not None and sort_by not in SORTABLE_FIELDS:
        raise HTTPException(
            status_code=422,
            detail={"status": "error", "message": "Invalid query parameters"},
        )
    if order not in VALID_ORDERS:
        raise HTTPException(
            status_code=422,
            detail={"status": "error", "message": "Invalid query parameters"},
        )
 
    dbq = db.query(Profile)
    dbq = apply_filters(
        dbq,
        gender=parsed.gender,
        age_group=parsed.age_group,
        country_id=parsed.country_id,
        min_age=parsed.min_age,
        max_age=parsed.max_age,
        min_gender_probability=None,
        min_country_probability=None,
    )
    dbq = apply_sort(dbq, sort_by, order)
    total, profiles = paginate(dbq, page, limit)
 
    return {
        "status": "success",
        "page": page,
        "limit": limit,
        "total": total,
        "data": [format_profile(p) for p in profiles],
    }
@app.post("/api/seed")
def seed_database(db: Session = Depends(get_db)):
    import json, os
    filepath = "seed_profiles.json"
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail={"status": "error", "message": "Seed file not found"})
    with open(filepath, "r") as f:
        data = json.load(f)
    profiles_raw = data if isinstance(data, list) else data.get("data", data.get("profiles", []))
    from sqlalchemy import text
    existing = set(row[0] for row in db.execute(text("SELECT name FROM profiles")).fetchall())
    inserted = 0
    try:
        import uuid6
        def new_uuid(): return str(uuid6.uuid7())
    except:
        import uuid
        def new_uuid(): return str(uuid.uuid4())
    from datetime import datetime, timezone
    batch = []
    for raw in profiles_raw:
        name = raw.get("name", "").strip()
        if not name or name in existing:
            continue
        age = int(raw.get("age", 0))
        def get_age_group(a):
            if a <= 12: return "child"
            elif a <= 17: return "teenager"
            elif a <= 59: return "adult"
            else: return "senior"
        batch.append(Profile(
            id=new_uuid(), name=name,
            gender=raw.get("gender","").lower(),
            gender_probability=float(raw.get("gender_probability",0)),
            age=age, age_group=raw.get("age_group") or get_age_group(age),
            country_id=raw.get("country_id","").upper(),
            country_name=raw.get("country_name",""),
            country_probability=float(raw.get("country_probability",0)),
            created_at=datetime.now(timezone.utc)
        ))
        existing.add(name)
        inserted += 1
    db.bulk_save_objects(batch)
    db.commit()
    return {"status": "success", "inserted": inserted}
 
 
# Health check
@app.get("/")
def root():
    return {"status": "ok", "message": "Insighta Labs API is running"}
 
 

# Override FastAPI's default error format to match task spec
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
 
 
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    detail = exc.detail
    if isinstance(detail, dict):
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": str(detail)},
    )
 
 
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"status": "error", "message": "Invalid query parameters"},
    )
 