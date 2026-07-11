# Nghiên cứu & so sánh: Tìm profile LinkedIn theo filter

> Cập nhật: **2026-07** · Nhu cầu: **search profile theo tiêu chí lọc** (chức danh,
> địa điểm, công ty, ngành, seniority, số năm KN, trường học).

---

## 1. Bối cảnh: 3 actor Apify được đánh giá ban đầu

| Actor | Kiểu | Output | Giá /1000 |
|---|---|---|---|
| **thescrappa/linkedin-search-scraper** | Tìm qua Google | Chỉ URL + title + snippet | **$0.30** |
| **harvestapi/linkedin-profile-search** ⭐ | Search trực tiếp trong LinkedIn theo filter | Full profile chi tiết | **$8** (Full) |
| **dev_fusion/linkedin-profile-scraper** | Enrich từ URL có sẵn | Full profile + email/SĐT | **$10** |

- `thescrappa`: rẻ nhất nhưng **không lọc** được theo seniority/ngành/công ty, chỉ trả link + snippet.
- `dev_fusion`: bắt buộc phải **có sẵn URL**, không search được.
- `harvestapi`: **search trực tiếp theo filter + trả full profile** → đúng nhu cầu nhất.

---

## 2. Chi phí chi tiết — harvestapi/linkedin-profile-search

Mô hình **pay-per-event**. Điểm mấu chốt: **1 "search page" = tối đa 25 profile**,
giá **$0.10/page**. **Apify KHÔNG tính thêm phí platform** — chỉ trả đúng các event dưới đây.

| Chế độ | Phí | Data nhận được |
|---|---|---|
| **Short** | $0.10/page (25 profile) | Chỉ tên, headline, URL, location cơ bản |
| **Full** | $0.10/page + **$0.004/profile** | Full: kinh nghiệm, học vấn, skills... |
| **Full + Email** | $0.10/page + **$0.01/profile** | Full + email (profile thiếu data thì không bị tính) |

### Quy đổi ra /1000 profile (giả sử mỗi page đủ 25 người)

| Chế độ | Phí search page | Phí profile | **Tổng /1000** |
|---|---|---|---|
| Short | 40 × $0.10 = $4 | — | **~$4** |
| Full | $4 | 1000 × $0.004 = $4 | **~$8** |
| Full + Email | $4 | 1000 × $0.01 = $10 | **~$14** |

### Ví dụ theo volume (chế độ Full)

| Số profile | Full | Full + Email |
|---|---|---|
| 100 | ~$0.80 | ~$1.40 |
| 500 | ~$4.00 | ~$7.00 |
| 1.000 | ~$8.00 | ~$14.00 |
| 5.000 | ~$40.00 | ~$70.00 |
| 10.000 | ~$80.00 | ~$140.00 |

### Vì sao email tính phí riêng?
Email **không có sẵn** trên trang profile LinkedIn (LinkedIn ẩn). Actor phải chạy thêm bước
**email discovery**: suy ra pattern email từ tên + công ty, đối chiếu database bên thứ ba
(Hunter/Apollo/Dropcontact...), rồi **verify**. Bước này tốn phí API bên thứ ba → tách event
riêng ($0.01 thay vì $0.004). Ưu điểm: **profile không tìm ra email thì không bị tính tiền**.
Nhược điểm: tỷ lệ tìm được thường ~40–70%, chủ yếu là **email công ty**, nên verify trước khi gửi.

### Credit miễn phí
- Free plan Apify: **$5 credit/tháng** → ~625 profile Full hoặc ~1250 profile Short miễn phí/tháng.
- Pay-per-event nên **không tốn thêm phí compute** — giá trên là giá cuối.

### Filter hỗ trợ (tham khảo tên field)
`searchQuery`, `currentJobTitles`, `pastJobTitles`, `locations`, `currentCompanies`,
`pastCompanies`, `schools`, `industryIds`, `seniorityLevelIds`, `yearsOfExperienceIds`,
`yearsAtCurrentCompanyIds`, `maxItems`, `startPage`, `takePages`, `profileScraperMode`.

---

## 3. So sánh các nền tảng khác (ngoài Apify)

| Provider | Nhóm | Filter mạnh? | Giá /1000 | Cần cookie? | Cam kết tối thiểu |
|---|---|---|---|---|---|
| **harvestapi (Apify)** ⭐ | A | ✅ Rất mạnh | $4 / $8 / $14 * | ❌ | Không — free $5/tháng |
| **Bright Data — Dataset** | B (kho sẵn) | ✅ Mạnh | **~$2.5** (mua 1 lần) | ❌ | ~$250 (mua tối thiểu ~100K) |
| **Bright Data — Scraper API** | A | ⚠️ Chỉ theo *tên* | $1.5 | ❌ | Không (free 5K/tháng) |
| **Coresignal** | B | ✅ Mạnh (ES DSL) | $5–200 | ❌ | $49–1500/tháng |
| **Apollo.io** | B | ✅ Mạnh + email | seat-based | ❌ | $49–119/user/tháng |
| **People Data Labs** | B | ✅ Mạnh (API) | ~$200–280 | ❌ | $98/tháng |
| **PhantomBuster** | C | ⚠️ Qua Sales Nav | $69+/tháng | ⚠️ **CÓ (rủi ro ban)** | $69/tháng |
| **ScrapingDog** | — | ❌ Chỉ URL-in | rẻ | ❌ | ~$40/tháng |
| ~~Proxycurl~~ | — | ☠️ **Đã đóng cửa 7/2025** | — | — | — |

\* harvestapi: Short / Full / Full+Email

### Ghi chú từng nền tảng

**Bright Data**
- *Dataset Marketplace*: kho ~722M profile mua sẵn, lọc theo filter rồi mua subset → **~$2.5/1000**,
  nhưng **mua tối thiểu ~$250/100K record** và là **dữ liệu tĩnh** (không tươi bằng scrape live).
  Đáng dùng khi cần **hàng chục nghìn+ profile một lần**.
- *Scraper API*: $1.5/1000 nhưng discovery **chỉ theo tên** (first/last name), KHÔNG lọc
  title+location+industry → **không thay được harvestapi**.

**Coresignal** — Employee API có search theo title/location/industry/company (kể cả Elasticsearch DSL),
không cần cookie. Nhưng tính theo **plan tháng** ($49–1500) + mô hình 2 loại credit (Search + Collect).
Rẻ theo record chỉ khi lên plan cao.

**Apollo.io** — Database B2B ~275M contact (không phải LinkedIn live). Filter mạnh + **email/SĐT**,
có UI + CSV, **không cần code**. Rẻ nhất nếu mục tiêu là **email leads**. Đổi lại: data là snapshot
**có thể cũ**; API đầy đủ chỉ ở tier Organization.

**People Data Labs (PDL)** — Database ~3B người, Person Search API (API-first, không có UI đẹp).
~$0.20–0.28/record. Freshness kém (cập nhật theo batch), search tính credit theo từng profile trả về.

**PhantomBuster** — Tự động hóa LinkedIn/Sales Navigator bằng **cookie LinkedIn của bạn** →
**nguy cơ khóa tài khoản**, giới hạn ~100 profile/ngày an toàn. Chỉ dùng nếu bắt buộc cần Sales Navigator.

**ScrapingDog** — Chủ yếu là Profile Scraper theo URL, **không search theo filter**.

**Proxycurl** — ☠️ **Đã đóng cửa 7/2025** (LinkedIn kiện đầu 2025). Successor "NinjaPear" **không**
làm people-search-by-filter. Không dùng được.

---

## 4. Kết luận & khuyến nghị

| Bạn ưu tiên... | Chọn |
|---|---|
| Test nhanh, ít tiền, linh hoạt, data tươi | **harvestapi (Apify)** |
| Số lượng cực lớn 1 lần, tiết kiệm | **Bright Data Dataset** |
| Email để bán hàng, không cần code | **Apollo.io** |
| Tuyệt đối tránh rủi ro acc | Bất kỳ giải pháp **không cần cookie** (né PhantomBuster) |

**Nên tránh:** PhantomBuster (rủi ro khóa acc), Proxycurl (đã chết), ScrapingDog (không filter search).

---

## 5. Nguồn tham khảo

- harvestapi/linkedin-profile-search — https://apify.com/harvestapi/linkedin-profile-search
- thescrappa/linkedin-search-scraper — https://apify.com/thescrappa/linkedin-search-scraper
- dev_fusion/linkedin-profile-scraper — https://apify.com/dev_fusion/linkedin-profile-scraper
- Bright Data — Web Scraper pricing — https://brightdata.com/pricing/web-scraper
- Bright Data — LinkedIn Dataset — https://brightdata.com/products/datasets/linkedin/profiles
- Coresignal pricing — https://coresignal.com/pricing/
- Apollo pricing — https://www.apollo.io/pricing
- People Data Labs pricing — https://www.peopledatalabs.com/pricing/person
- PhantomBuster pricing — https://phantombuster.com/pricing
- ScrapingDog pricing — https://www.scrapingdog.com/pricing/
- Proxycurl đóng cửa — https://nubela.co/blog/goodbye-proxycurl/
- Best LinkedIn Scrapers on Apify 2026 — https://use-apify.com/docs/best-apify-actors/best-linkedin-scrapers
