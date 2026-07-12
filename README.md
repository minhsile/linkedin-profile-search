# LinkedIn Profile Crawl Pipeline

Crawl profile LinkedIn từ **Apify (`harvestapi`)** → **Postgres**, chống trùng (dedup theo
slug, chỉ enrich chứ không nhân bản), có **job runner resume** được.

## Tính năng
- Search profile theo filter (chức danh, địa điểm, công ty, ngành...) qua harvestapi.
- Lưu **full profile** vào Postgres (JSONB); cột `email` optional.
- **Dedup** theo LinkedIn slug (UNIQUE) + **deep-merge enrich**, idempotent (chạy lại không trùng).
- **Job runner resume** được (checkpoint).
- **Theo dõi tiến độ crawl ngay trên terminal** + lệnh `status` xem lại các run.

## Yêu cầu
- **Docker** (chạy Postgres 16) · **uv** (`pip install uv`, để tạo venv Python 3.12) · **Apify token**.

## Chạy nhanh (Quickstart)

```bash
# 1) Môi trường (Python 3.12 qua uv)
conda deactivate 2>/dev/null           # nếu đang ở conda base — nếu không uv sẽ cài nhầm vào python conda
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -e .
source .venv/Scripts/activate          # Git Bash  |  PowerShell: .venv\Scripts\Activate.ps1

# 2) Database
docker compose up -d                    # Postgres 16 (build + tzdata-legacy) @ localhost:5433
# hoac ban official image thuan (khong build, @ localhost:5434):
# docker compose --profile official up -d db-official

# 3) Cấu hình + tạo schema
cp .env.example .env                     # điền APIFY_TOKEN
python -m lps.cli migrate

# 4) Crawl (tiến độ Apify cào in trực tiếp ra terminal)
cp config.example.json config.json       # sửa filter: currentJobTitles, locations, industryIds...
python -m lps.cli crawl --config config.json

# 5) Xem lại các run
python -m lps.cli status                 # thống kê run trong terminal
```

## Lệnh CLI

| Lệnh | Chức năng |
|---|---|
| `python -m lps.cli migrate` | Tạo / nâng cấp schema DB |
| `python -m lps.cli crawl --config config.json` | Chạy crawl (config 1 object hoặc mảng nhiều bộ) |
| `python -m lps.cli crawl --config config.json --resume <RUN_ID>` | Tiếp tục run bị dừng |
| `python -m lps.cli status [--run <RUN_ID>]` | Xem trạng thái run |

## Theo dõi throughput
Cào xong, terminal in **1 dòng tổng kết**:
`Apify cao xong: N profiles / Ts (~R profiles/s) [SUCCEEDED]` — tổng số profile cào được,
thời gian cào end-to-end (gồm cả lúc Apify khởi động actor), và throughput trung bình `R = N/T`.
Sau đó là bước ingest/dedup, in tổng kết `fetched / inserted / enriched / unchanged / errors`.

## Cấu trúc

```
src/lps/          settings · normalize · models · db · ingest · runner · cli · sources/
db/migrations/    SQL schema
docs/             research-comparison.md · CONFIG.md · dictionaries/ · superpowers/{specs,plans}
```

## Tài liệu
- **So sánh nền tảng** (Apify / Bright Data / Coresignal / Apollo...): [`docs/research-comparison.md`](docs/research-comparison.md)
- **Cấu hình crawl & dictionary (industryIds, takePages...)**: [`docs/CONFIG.md`](docs/CONFIG.md)
- **Spec & implementation plan**: [`docs/superpowers/`](docs/superpowers/)

## Lưu ý pháp lý
Scrape LinkedIn vi phạm **ToS** của LinkedIn; email/PII dính **GDPR** — cân nhắc kỹ khi dùng
thương mại. Ưu tiên giải pháp **không cần cookie** để tránh khóa tài khoản cá nhân.
