# LinkedIn Profile Search — So sánh phương pháp thu thập profile theo filter

Repo nghiên cứu & so sánh các cách **tìm profile LinkedIn theo tiêu chí lọc**
(chức danh, địa điểm, công ty, ngành, seniority...) trên **Apify** và các nền tảng khác.

> ⚠️ Repo này hiện **chỉ chứa tài liệu nghiên cứu**, chưa có code.
> Mục tiêu: chọn được nền tảng/phương pháp trước khi triển khai.

- 📅 Cập nhật: **2026-07**
- 📄 So sánh chi tiết từng nền tảng + giá + nguồn: [`docs/research-comparison.md`](docs/research-comparison.md)

---

## TL;DR — Chọn nhanh theo nhu cầu

| Bạn ưu tiên... | Nên chọn | Giá tham khảo |
|---|---|---|
| Test nhanh, ít tiền, linh hoạt, data tươi (live) | **harvestapi (Apify)** | $8/1000 (Full) |
| Số lượng cực lớn 1 lần, tiết kiệm | **Bright Data — Dataset** | ~$2.5/1000 (min ~$250) |
| Cần email để bán hàng, không cần code | **Apollo.io** | ~$49/tháng/seat |
| Tuyệt đối tránh rủi ro khóa acc | Bất kỳ giải pháp **không cần cookie** | — |

**Khuyến nghị để BẮT ĐẦU: `harvestapi/linkedin-profile-search` trên Apify.**
Lý do: pay-as-you-go (không phí cố định), filter mạnh nhất, data live, không cần cookie
LinkedIn, có free $5/tháng để thử.

---

## 3 nhóm giải pháp (khác nhau về bản chất)

| Nhóm | Bản chất | Ví dụ |
|---|---|---|
| **A. Scrape LinkedIn live theo filter** | Cào dữ liệu LinkedIn thời gian thực, lọc theo tiêu chí | harvestapi (Apify), Bright Data Scraper API |
| **B. Database B2B có sẵn** | Query kho dữ liệu riêng của họ (không phải LinkedIn real-time) | Bright Data Dataset, Coresignal, Apollo, People Data Labs |
| **C. Tự động hóa bằng cookie của BẠN** | Dùng session LinkedIn cá nhân → **rủi ro khóa acc** | PhantomBuster |

---

## Cấu trúc repo

```
linkedin-profile-search/
├── README.md                       # bản tóm tắt + khuyến nghị (file này)
└── docs/
    └── research-comparison.md      # so sánh chi tiết + giá + nguồn tham khảo
```

---

## ⚠️ Lưu ý pháp lý & rủi ro
- Scrape LinkedIn vi phạm **Điều khoản dịch vụ (ToS)** của LinkedIn.
- Lấy email/SĐT dính **GDPR / luật bảo vệ dữ liệu cá nhân** — cân nhắc kỹ khi dùng thương mại.
- Ưu tiên giải pháp **không cần cookie** để tránh nguy cơ bị khóa tài khoản cá nhân.

## Chạy pipeline

1. `conda create -n lps python=3.12 -y && conda activate lps`
2. `pip install -r requirements.txt && pip install -e .`
3. `docker compose up -d`   # Postgres 16 tại localhost:5433
4. `cp .env.example .env`   # điền APIFY_TOKEN
5. `python -m lps.cli migrate`
6. `cp config.example.json config.json`  # sửa filter
7. `python -m lps.cli crawl --config config.json`
8. `uvicorn dashboard.app:app --port 8000`  # dashboard tại http://localhost:8000
9. `python -m lps.cli status`  # xem thống kê run

Chi tiết vận hành/resume: xem `docs/RUNBOOK.md`.
Kiến trúc & spec: `docs/superpowers/specs/`, kế hoạch: `docs/superpowers/plans/`.
