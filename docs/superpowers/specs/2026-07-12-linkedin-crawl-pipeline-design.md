# Spec: LinkedIn Profile Crawl Pipeline

- **Ngày:** 2026-07-12
- **Trạng thái:** Design (chờ duyệt để sang bước lập plan)
- **Repo:** D:\workspace\linkedin-profile-search

## 1. Mục tiêu

Crawl profile LinkedIn từ **Apify (`harvestapi/linkedin-profile-search`)** theo bộ lọc,
**lưu HẾT thông tin** vào **Postgres**, đảm bảo **mỗi người = 1 bản ghi duy nhất**
(enrich thêm data chứ không nhân bản), có **job runner resume được**, **theo dõi throughput**
và **dashboard web local** để giám sát luồng.

## 2. Phạm vi (scope)

**Trong phạm vi:**
- 1 nguồn: harvestapi (search theo filter).
- Postgres chạy trong Docker.
- **1 bảng data `person`** (chi tiết để JSONB) + 2 bảng vận hành.
- Dedup theo **slug chuẩn hóa (UNIQUE)** + cơ chế enrich.
- Job runner resume + checkpoint.
- Metrics throughput + dashboard FastAPI + Chart.js.
- Email = cột **optional** (chưa crawl).

**Ngoài phạm vi (để sau, nhưng thiết kế chừa chỗ):**
- Fuzzy matching (giữ sẵn cột `norm_name`/`norm_company`, bật sau không cần migrate lại).
- Email enrichment.
- Nhiều nguồn khác (Apollo/PDL/Bright Data) — kiến trúc adapter cho phép thêm sau.
- Lên lịch định kỳ (scheduling).

## 3. Quyết định thiết kế (chốt từ brainstorming)

| Chủ đề | Quyết định |
|---|---|
| Dedup | **Slug chuẩn hóa + UNIQUE**, exact match. Bỏ fuzzy (YAGNI cho 1 nguồn). |
| Không có slug | Không bỏ data, **insert + gắn cờ `needs_review`**. |
| Quy mô | ~50k profile, 1 máy, không cần message queue. |
| Dashboard | **FastAPI + Chart.js** (self-contained, local). |
| Run mode | **Job runner resume được** (checkpoint, idempotent). |
| Schema | **1 bảng `person`** (JSONB) + `crawl_run` + `run_metric`. |
| Email | Cột nullable, optional. |
| Stack | Python 3.12 (conda) + Postgres 16 (Docker). |

## 4. Kiến trúc (các khối tách biệt)

```
Apify (harvestapi)  --raw items-->  SourceAdapter (normalize)  -->  CanonicalProfile
   -->  Ingest Engine  (match slug -> INSERT | ENRICH | needs_review)  -->  Postgres(person)
Job Runner (run lifecycle, checkpoint, ghi metrics)  -->  crawl_run / run_metric
Dashboard (FastAPI + Chart.js) đọc DB
```

Mỗi khối 1 nhiệm vụ, giao tiếp qua interface rõ ràng:
- **SourceAdapter** — biến raw record của 1 nguồn thành `CanonicalProfile`. Thêm nguồn = thêm adapter.
- **Normalizer** — URL to slug, tên/công ty to `norm_*`, tính content_hash.
- **Ingest Engine** — nhận CanonicalProfile, quyết định insert/enrich, merge JSONB, idempotent.
- **Job Runner** — điều phối 1 run, checkpoint, ghi throughput.
- **DB layer** — kết nối, helper upsert.
- **Dashboard** — đọc DB, hiển thị.
- **CLI** — `migrate`, `crawl`, `status`.

## 5. Data model

### 5.1 person (bảng data duy nhất)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | uuid PK | |
| linkedin_slug | text **UNIQUE** | khóa dedup, đã chuẩn hóa; nullable (case hiếm) |
| linkedin_url | text | URL gốc |
| full_name / first_name / last_name | text | |
| headline | text | |
| location / country | text | |
| current_company / current_title | text | cột lọc nhanh |
| connections / followers | int | |
| email | text NULL | **optional** (chưa crawl) |
| norm_name / norm_company | text | dành cho fuzzy tương lai |
| data | **JSONB** | TẤT CẢ chi tiết: experience, education, skills, certs... |
| sources | text[] | các nguồn đã đóng góp |
| source_hashes | jsonb | {source: content_hash} để idempotent |
| needs_review | bool | true khi không có slug / nhập nhằng |
| created_at / updated_at / last_enriched_at | timestamptz | |

Index: UNIQUE(linkedin_slug), index(current_company), GIN(data).

### 5.2 crawl_run (vận hành: theo dõi + resume)

id, source, status (running/succeeded/failed), params jsonb (filter + apify run id),
apify_run_id, checkpoint jsonb (offset đã xử lý), started_at, finished_at,
tổng: fetched, inserted, enriched, unchanged, errors.

### 5.3 run_metric (vận hành: chart throughput)

id, run_id FK, ts timestamptz, processed, inserted, enriched, errors,
rate_per_sec (rolling). Ghi mỗi K item / T giây.

## 6. Cơ chế dedup + enrich (chi tiết)

Với mỗi CanonicalProfile P:

1. **Chuẩn hóa URL to slug**: bỏ https, www, subdomain quốc gia (vd vn.), dấu / cuối,
   query string, lowercase. VD `https://vn.linkedin.com/in/An-Nguyen-123/?trk=x` to `an-nguyen-123`.
2. **Tính content_hash** của payload (theo nguồn) để idempotent.
3. **Khớp**: có slug thì `SELECT id, source_hashes FROM person WHERE linkedin_slug = :slug`;
   không có slug thì không đoán, sẽ insert + needs_review.
4. **Quyết định**:
   - Không thấy (hoặc không slug) to **INSERT** (needs_review nếu thiếu slug).
   - Thấy: nếu content_hash đã có trong source_hashes[source] to **UNCHANGED**; ngược lại to **ENRICH**.
5. **ENRICH (merge, không nhân bản)**:
   - Điền field còn thiếu (NULL/rỗng to giá trị mới). **Không ghi đè** giá trị đã có bằng rỗng.
   - **Deep-merge data JSONB**: mảng experience/education/skills gộp + khử trùng theo khóa tự nhiên
     (experience trùng nếu cùng company + title + khoảng thời gian).
   - Append source vào sources[], cập nhật source_hashes, last_enriched_at.
   - Có thay đổi thật to đếm enriched; không to unchanged.

**Idempotent toàn cục**: chạy lại/resume cùng payload to không tạo trùng (slug UNIQUE + content_hash).

## 7. Job runner + resume + throughput

- 1 lần crawl = 1 crawl_run (params = filter + apify_run_id).
- Runner gọi actor Apify, iterate dataset, upsert từng item, cập nhật checkpoint.offset định kỳ.
- Crash/chạy lại cùng run id to resume từ checkpoint.offset; idempotent nên reprocess an toàn.
- Mỗi K item / T giây to ghi run_metric (rate_per_sec rolling = processed/elapsed).
- Kết thúc to cập nhật status + tổng.

## 8. Monitoring / Dashboard

**FastAPI + 1 trang HTML + Chart.js inline** (không service ngoài), đọc Postgres:
- Danh sách run (status, tổng, thời lượng).
- **Chart throughput/giây** theo run_metric.
- Tổng: inserted / enriched / unchanged / errors.
- Tổng person trong DB, breakdown theo sources.
- Số needs_review.

CLI `status`: in nhanh thống kê run mới nhất (không cần mở web).

## 9. Stack & hạ tầng

- **Postgres 16** trong Docker (docker-compose, volume bền). pg_trgm/unaccent bật sẵn để dành fuzzy sau.
- **Python 3.12** (conda env). Libs: apify-client, psycopg (v3), pydantic, fastapi + uvicorn, python-dotenv.
- Migration = file SQL + script chạy nhẹ (không Alembic).
- Config: .env (APIFY_TOKEN, DATABASE_URL), config.json (filter search).

## 10. Cấu trúc thư mục

```
linkedin-profile-search/
├── docker-compose.yml
├── .env.example
├── requirements.txt
├── config.example.json
├── db/migrations/001_init.sql
├── src/lps/
│   ├── models.py        # pydantic CanonicalProfile
│   ├── normalize.py     # url->slug, norm_name/company, content_hash
│   ├── db.py            # kết nối, helpers
│   ├── ingest.py        # upsert: match slug -> insert/enrich, deep-merge
│   ├── runner.py        # run lifecycle, checkpoint, metrics
│   ├── cli.py           # migrate / crawl / status
│   └── sources/
│       ├── base.py      # interface SourceAdapter
│       └── harvestapi.py
├── dashboard/
│   ├── app.py           # FastAPI
│   └── static/index.html
└── tests/
```

## 11. Error handling

- Lỗi từng item không giết run: bắt to đếm errors to log to run tiếp tục.
- Lỗi Apify run to cập nhật crawl_run.status = failed, giữ checkpoint để resume.
- DB transient to retry ngắn.

## 12. Testing (TDD)

Unit test:
- normalize: URL->slug (biến thể subdomain/trailing slash/query/case), content_hash ổn định.
- ingest: insert mới; enrich điền field thiếu; **không** ghi đè bằng rỗng; deep-merge + khử trùng array;
  idempotent (2 lần cùng hash = unchanged); thiếu slug to needs_review.
- Dùng Postgres test (Docker) + rollback transaction mỗi test.

## 13. Câu hỏi mở / tương lai

- Bật fuzzy khi thêm nguồn thứ 2 (đã chừa cột norm_*).
- Bật email mode của harvestapi (đã có cột email).
- Cơ chế review UI cho needs_review (hiện chỉ gắn cờ).
