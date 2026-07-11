# Dictionary các field ID (dùng trong config.json)

Tất cả field dưới đây **chỉ nhận SỐ** (trừ companyHeadcount nhận mã chữ). Industry codes
xem file riêng: `industry_codes.md` / `industry_codes.json` (433 mã).

## yearsOfExperienceIds / yearsAtCurrentCompanyIds
| id | Nghĩa |
|---|---|
| 1 | Dưới 1 năm |
| 2 | 1–2 năm |
| 3 | 3–5 năm |
| 4 | 6–10 năm |
| 5 | Trên 10 năm |

## seniorityLevelIds
| id | Nghĩa | id | Nghĩa |
|---|---|---|---|
| 100 | In Training | 210 | Experienced Manager |
| 110 | Entry Level | 220 | Director |
| 120 | Senior | 300 | Vice President |
| 130 | Strategic | 310 | CXO |
| 200 | Entry Level Manager | 320 | Owner / Partner |

## functionIds
| id | Function | id | Function |
|---|---|---|---|
| 1 | Accounting | 14 | Legal |
| 2 | Administrative | 15 | Marketing |
| 3 | Arts and Design | 16 | Media & Communications |
| 4 | Business Development | 17 | Military & Protective Services |
| 5 | Community & Social Services | 18 | Operations |
| 6 | Consulting | 19 | Product Management |
| 7 | Education | 20 | Program & Project Management |
| 8 | Engineering | 21 | Purchasing |
| 9 | Entrepreneurship | 22 | Quality Assurance |
| 10 | Finance | 23 | Real Estate |
| 11 | Healthcare Services | 24 | Research |
| 12 | Human Resources | 25 | Sales |
| 13 | Information Technology | 26 | Customer Success & Support |

## companyHeadcount (mã CHỮ)
| mã | Quy mô nhân sự |
|---|---|
| A | Self-employed |
| B | 1–10 |
| C | 11–50 |
| D | 51–200 |
| E | 201–500 |
| F | 501–1.000 |
| G | 1.001–5.000 |
| H | 5.001–10.000 |
| I | 10.001+ |

## Vài industryIds hay dùng (đầy đủ ở industry_codes.md)
| id | Ngành |
|---|---|
| 4 | Software Development |
| 6 | Technology, Information and Internet |
| 3242 | IT Services and IT Consulting |
| 41 | Banking |
| 43 | Financial Services (Capital Markets nhánh riêng: 129) |
| 1594 | Accounting |
| 104 | Staffing and Recruiting |

> **Lưu ý kiểu dữ liệu:** trong config.json các field `*Ids` để dạng **chuỗi** (vd `["120","130"]`, `["4"]`). Pipeline tự ép số -> chuỗi nếu bạn lỡ viết `[120,130]`, nên cả hai đều chạy.
