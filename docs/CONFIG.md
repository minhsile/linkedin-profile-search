# Cấu hình crawl (`config.json`)

Toàn bộ nội dung `config.json` được **gửi nguyên văn** làm input cho actor
`harvestapi/linkedin-profile-search`. Muốn thêm bộ lọc nào → **cứ thêm key vào**, pipeline
không giới hạn. File là JSON thuần (không hỗ trợ comment).

## Field hay dùng

| Key | Kiểu | Ý nghĩa |
|---|---|---|
| `maxItems` | int | **Số profile tối đa** cần lấy |
| `profileScraperMode` | string | `"Short"` \| `"Full"` \| `"Full + email search"` |
| `searchQuery` | string | Từ khóa tổng (hỗ trợ toán tử search LinkedIn) |
| `currentJobTitles` / `pastJobTitles` | string[] | Chức danh hiện tại / trước đây |
| `locations` / `excludeLocations` | string[] | Địa điểm (nên ghi đầy đủ, vd "United Kingdom" thay vì "UK") |
| `currentCompanies` / `pastCompanies` | string[] | **URL LinkedIn đầy đủ** của công ty (vd `https://www.linkedin.com/company/google/`) |
| `schools` | string[] | Tên trường (vd `"Stanford University"`) |
| `firstNames` / `lastNames` | string[] | Lọc theo tên |
| `profileLanguages` | string[] | Ngôn ngữ profile (vd `"English"`) |
| `companyHeadcount` | string[] | Quy mô công ty — **mã chữ** (xem bảng dưới) |
| `companyHeadquarterLocations` | string[] | Địa điểm trụ sở công ty |
| `recentlyChangedJobs` | bool | Đổi việc trong 90 ngày |
| `recentlyPostedOnLinkedIn` | bool | Có đăng bài trong 30 ngày |
| `startPage` | int | Trang bắt đầu (mỗi trang ~25 profile) |
| `takePages` | int | Số trang cào (tối đa 100) |

## Field lọc bằng ID SỐ (chỉ nhận số, không nhận tên)

### `yearsOfExperienceIds` / `yearsAtCurrentCompanyIds`
| ID | Nghĩa |
|---|---|
| 1 | < 1 năm |
| 2 | 1–2 năm |
| 3 | 3–5 năm |
| 4 | 6–10 năm |
| 5 | > 10 năm |

### `seniorityLevelIds`
| ID | Nghĩa | ID | Nghĩa |
|---|---|---|---|
| 100 | In Training | 210 | Experienced Manager |
| 110 | Entry Level | 220 | Director |
| 120 | Senior | 300 | Vice President |
| 130 | Strategic | 310 | CXO |
| 200 | Entry Level Manager | 320 | Owner / Partner |

### `functionIds` (1–26)
Accounting, Administrative, Arts/Design, Business Development, Community/Social Services,
Consulting, Education, Engineering, Entrepreneurship, Finance, Healthcare, HR, IT, Legal,
Marketing, Media/Communications, Military, Operations, **Product Management (19)**,
Program/Project Management, Purchasing, QA, Real Estate, Research, Sales, Customer Success.

### `industryIds`
Chỉ nhận số. Tra mã tại: <https://github.com/HarvestAPI/linkedin-industry-codes-v2/blob/main/linkedin_industry_code_v2_all_eng_with_header.csv>
Ví dụ: `4` = Software Development, `43` = Financial Services.

### `companyHeadcount` (mã chữ)
| Mã | Quy mô | Mã | Quy mô |
|---|---|---|---|
| A | Self-employed | F | 501–1.000 |
| B | 1–10 | G | 1.001–5.000 |
| C | 11–50 | H | 5.001–10.000 |
| D | 51–200 | I | 10.001+ |
| E | 201–500 | | |

Các field loại trừ tương ứng: `excludeIndustryIds`, `excludeSeniorityLevelIds`,
`excludeFunctionIds`, `excludeCurrentCompanies`, `excludeCurrentJobTitles`, `excludeSchools`...

## Ví dụ đầy đủ (nhiều filter)

```json
{
  "profileScraperMode": "Full",
  "searchQuery": "Data Engineer",
  "currentJobTitles": ["Data Engineer", "Senior Data Engineer"],
  "locations": ["Ho Chi Minh City", "Hanoi"],
  "industryIds": [4],
  "seniorityLevelIds": [120, 130],
  "yearsOfExperienceIds": [3, 4],
  "companyHeadcount": ["E", "F", "G"],
  "profileLanguages": ["English"],
  "recentlyChangedJobs": false,
  "maxItems": 100,
  "startPage": 1,
  "takePages": 4
}
```

## Lưu ý (gotchas)
- **`currentCompanies`/`pastCompanies` phải là URL LinkedIn đầy đủ**, không phải tên.
- Field ID (industry/seniority/years/function) **chỉ nhận số** — điền tên sẽ không lọc đúng.
- Lọc càng hẹp → mỗi trang càng đầy đúng đối tượng, đỡ tốn phí trang.
- `takePages` × ~25 nên ≥ `maxItems`/25 để đủ trang (vd maxItems 100 → takePages ≥ 4).
- Mỗi lần `crawl` là 1 actor run mới (tốn phí Apify); dedup tự gộp nếu trùng người đã có.

## Nhiều bộ config trong 1 file (array)

`config.json` có thể là **1 object** hoặc **1 mảng object**. Nếu là mảng, `crawl` chạy
**tuần tự từng bộ** (mỗi bộ = 1 actor run riêng), tất cả đổ vào cùng DB nên **dedup tự gộp**
người trùng giữa các bộ.

```json
[
  { "currentJobTitles": ["Data Engineer"],            "locations": ["Ho Chi Minh City"], "maxItems": 100 },
  { "currentJobTitles": ["Machine Learning Engineer"], "locations": ["Hanoi"],            "maxItems": 100 }
]
```

Chạy như thường:
```bash
python -m lps.cli crawl --config config.json
```
Output in tiến độ từng bộ `[1/2] ... [2/2] ...` + dòng **TỔNG** cuối.
(Mỗi bộ là 1 actor run → tính phí Apify riêng cho mỗi bộ.)

> Các field `*Ids` gửi cho actor phải là **mảng chuỗi**. Pipeline tự động ép số sang chuỗi, nên `[4]` hay `["4"]` đều được.
