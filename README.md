# LinkedIn Profile Crawl Pipeline

Crawl profile LinkedIn từ **Apify (`harvestapi`)** → **Postgres**, chống trùng (dedup theo
slug, chỉ enrich chứ không nhân bản), có **job runner resume** + **dashboard throughput**.

## Tính năng
- Search profile theo filter (chức danh, địa điểm, công ty, ngành...) qua harvestapi.
- Lưu **full profile** vào Postgres (JSONB); cột `email` optional.
- **Dedup** theo LinkedIn slug (UNIQUE) + **deep-merge enrich**, idempotent (chạy lại không trùng).
- **Job runner resume** được (checkpoint) + ghi **throughput metrics**.
- **Dashboard** FastAPI + Chart.js chạy local.

## Yêu cầu
- **Docker** (chạy Postgres 16) · **uv** (`pip install uv`, để tạo venv Python 3.12) · **Apify token**.

## Chạy nhanh (Quickstart)

```bash
# 1) Môi trường
uv venv --python 3.12 .venv
source .venv/Scripts/activate          # Git Bash  |  PowerShell: .venv\Scripts\Activate.ps1
uv pip install -r requirements.txt -e .

# 2) Database
docker compose up -d                    # Postgres 16 @ localhost:5433

# 3) Cấu hình + tạo schema
cp .env.example .env                     # điền APIFY_TOKEN
python -m lps.cli migrate

# 4) Crawl
cp config.example.json config.json       # sửa filter: currentJobTitles, locations, industryIds...
python -m lps.cli crawl --config config.json

# 5) Theo dõi
python -m lps.cli status                 # thống kê run trong terminal
uvicorn dashboard.app:app --port 8000    # dashboard: http://localhost:8000
```

## Lệnh CLI

| Lệnh | Chức năng |
|---|---|
| `python -m lps.cli migrate` | Tạo / nâng cấp schema DB |
| `python -m lps.cli crawl --config config.json` | Chạy 1 crawl |
| `python -m lps.cli crawl --config config.json --resume <RUN_ID>` | Tiếp tục run bị dừng |
| `python -m lps.cli status [--run <RUN_ID>]` | Xem trạng thái run |

## Test

```bash
python -m pytest -q        # cần Docker Postgres đang chạy
```

## Cấu trúc

```
src/lps/          settings · normalize · models · db · ingest · runner · cli · sources/
dashboard/        FastAPI app + static (Chart.js)
db/migrations/    SQL schema
tests/            24 tests (unit + tích hợp DB)
docs/             research-comparison.md · RUNBOOK.md · superpowers/{specs,plans}
```

## Tài liệu
- **So sánh nền tảng** (Apify / Bright Data / Coresignal / Apollo...): [`docs/research-comparison.md`](docs/research-comparison.md)
- **Vận hành / resume / dedup / needs_review**: [`docs/RUNBOOK.md`](docs/RUNBOOK.md)
- **Spec & implementation plan**: [`docs/superpowers/`](docs/superpowers/)

## Lưu ý pháp lý
Scrape LinkedIn vi phạm **ToS** của LinkedIn; email/PII dính **GDPR** — cân nhắc kỹ khi dùng
thương mại. Ưu tiên giải pháp **không cần cookie** để tránh khóa tài khoản cá nhân.
