# Insighta Labs – Intelligence Query Engine

A FastAPI + MySQL REST API for querying demographic intelligence profiles with advanced filtering, sorting, pagination, and natural language search.

---

## Setup & Running

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your MySQL credentials
```

### 3. Seed the Database
```bash
python seed.py --file profiles.json
```
Re-running seed is safe — duplicates (matched by `name`) are skipped automatically.

### 4. Start the Server
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## Endpoints

### `GET /api/profiles`
Supports filtering, sorting, and pagination.

**Filters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `gender` | string | `male` or `female` |
| `age_group` | string | `child`, `teenager`, `adult`, `senior` |
| `country_id` | string | ISO 2-letter code (e.g. `NG`, `GH`) |
| `min_age` | int | Minimum age (inclusive) |
| `max_age` | int | Maximum age (inclusive) |
| `min_gender_probability` | float | 0.0–1.0 |
| `min_country_probability` | float | 0.0–1.0 |

**Sorting:** `sort_by=age|created_at|gender_probability` + `order=asc|desc`

**Pagination:** `page` (default: 1), `limit` (default: 10, max: 50)

**Example:**
```
GET /api/profiles?gender=male&country_id=NG&min_age=25&sort_by=age&order=desc&page=1&limit=10
```

---

### `GET /api/profiles/search?q=<natural language query>`
Parses plain English queries into filters. No AI or LLMs — rule-based only.

**Example:**
```
GET /api/profiles/search?q=young males from nigeria
```

---

## Natural Language Parsing Approach

### How It Works
The parser (`parser.py`) is entirely rule-based. It scans the lowercase query string using regex patterns and keyword lookups. No external models or APIs are used.

The parsing pipeline runs these steps in order:

1. **Gender detection** — looks for `male`, `female`, `men`, `women`, `man`, `woman`. Special case: `"male and female"` → no gender filter applied (both genders included).

2. **Age group / descriptive age** — matches keywords against a lookup table that maps to `(min_age, max_age, age_group)`:
   - `child` / `kids` → ages 0–12, `age_group=child`
   - `teenager` / `teen` / `adolescent` → ages 13–17, `age_group=teenager`
   - `adult` → ages 18–59, `age_group=adult`
   - `senior` / `elderly` → ages 60+, `age_group=senior`
   - `young` / `youth` → ages 16–24 (**not** a stored age group — per task spec)

3. **Explicit numeric age constraints** — parsed after descriptive groups and override them:
   - `above N` / `over N` / `older than N` → `min_age=N`, clears any descriptive `max_age`
   - `below N` / `under N` / `younger than N` → `max_age=N`
   - `between N and M` → `min_age=N`, `max_age=M`

4. **Country detection** — matches against a dictionary of ~70 country names and demonyms (sorted longest-first to avoid partial matches, e.g. `"niger"` matching inside `"nigeria"`). Also handles a `"from <country>"` pattern as a fallback.

### Supported Query Examples
| Query | Parsed Filters |
|-------|---------------|
| `young males` | `gender=male, min_age=16, max_age=24` |
| `females above 30` | `gender=female, min_age=30` |
| `people from angola` | `country_id=AO` |
| `adult males from kenya` | `gender=male, age_group=adult, country_id=KE` |
| `male and female teenagers above 17` | `age_group=teenager, min_age=17` |
| `senior women from ghana` | `gender=female, age_group=senior, country_id=GH` |
| `children from south africa` | `age_group=child, country_id=ZA` |
| `males between 20 and 35` | `gender=male, min_age=20, max_age=35` |

---

## Limitations & Edge Cases Not Handled

1. **"young" age range is for parsing only** — `young` maps to 16–24 per the task spec; it is NOT stored in `age_group`. Queries like `"very young"` or `"quite old"` are not handled.

2. **Ambiguous country names** — `"Congo"` resolves to Republic of Congo (`CG`), not DRC (`CD`). Queries like `"from the Congo"` may not resolve correctly.

3. **Adjective ordering matters partially** — `"male adult"` works, but unusual word orders like `"from Nigeria males"` might miss gender if the sentence structure is very irregular.

4. **No synonym handling** — words like `"guy"`, `"lady"`, `"boy"`, `"girl"` are not mapped to genders.

5. **No multi-country queries** — `"from nigeria or ghana"` is not supported; the parser picks the first matched country.

6. **No negation** — `"not from nigeria"` or `"excluding seniors"` are not handled.

7. **Confidence score filters not supported in NL** — phrases like `"high confidence profiles"` don't map to `min_gender_probability`.

8. **Numeric-only queries** — `"25 year old males"` is not parsed (no exact-age lookup, only ranges).

9. **Misspellings** — `"nigeeria"` or `"ghanna"` will not match; the parser has no fuzzy matching.

---

## Error Responses

All errors follow this structure:
```json
{ "status": "error", "message": "<error message>" }
```

| Scenario | Status Code |
|----------|-------------|
| Missing/empty `q` parameter | 400 |
| Uninterpretable NL query | 400 |
| Invalid parameter type/value | 422 |
| Server error | 500 |

---

## Database Schema

```sql
CREATE TABLE profiles (
    id              VARCHAR(36) PRIMARY KEY,
    name            VARCHAR(255) UNIQUE NOT NULL,
    gender          VARCHAR(10) NOT NULL,
    gender_probability FLOAT NOT NULL,
    age             INT NOT NULL,
    age_group       VARCHAR(20) NOT NULL,
    country_id      VARCHAR(2) NOT NULL,
    country_name    VARCHAR(100) NOT NULL,
    country_probability FLOAT NOT NULL,
    created_at      DATETIME NOT NULL
);
```

Indexes are on: `gender`, `age`, `age_group`, `country_id`, `name` — ensuring no full-table scans for common filter queries.