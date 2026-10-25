# 🧬 Hệ thống Kết nối Huyết thống qua ADN – v4.0

Ứng dụng tìm người thân thất lạc bằng **đối chiếu ADN (12 locus STR) + thông tin địa lý**.

> **Bản quyền:** Phan Quý Vinh – Hotline **0975 898 828**

---

## 🎯 Mục tiêu thiết kế

| Mục tiêu | Cách đạt được |
|----------|----------------|
| **Tích lũy dữ liệu** | Mọi hồ sơ ADN được lưu vĩnh viễn, so khớp với toàn bộ database mỗi lần đăng ký mới |
| **Không mất dữ liệu khi nâng cấp** | PostgreSQL riêng + Alembic migration (chỉ ALTER, không DROP) |
| **Bảo mật** | Mã hóa SĐT + Email (Fernet), rate-limit, Admin API key, không lộ thông tin đối phương |
| **Thông minh** | Chấm điểm đa tiêu chí: ADN + vị trí thất lạc + địa chỉ trước đây + năm thất lạc |
| **Tiện dụng** | Tra cứu bằng mã hồ sơ, Admin backup 1 click, thống kê, cập nhật trạng thái |

---

## 🛡️ Đảm bảo dữ liệu ADN không bị mất khi nâng cấp

1. **Dùng PostgreSQL** (Render / Neon / Supabase / Railway) – dữ liệu nằm ngoài code.
2. **Alembic** quản lý schema:
   ```bash
   # Khi thêm cột mới trong tương lai
   alembic revision --autogenerate -m "them cot moi"
   alembic upgrade head
   ```
   → Chỉ chạy `ALTER TABLE`, **không bao giờ xóa dữ liệu cũ**.
3. **Backup định kỳ**:
   - Admin gọi `GET /api/admin/backup/` (header `X-Admin-Key`)
   - Hoặc `pg_dump` / script `scripts/backup_local.py`

---

## 🚀 Chạy local

```bash
cd dna-matching-system
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# (Tùy chọn) Tạo khóa mã hóa
python scripts/generate_keys.py
# Copy ENCRYPTION_KEY và ADMIN_API_KEY vào file .env

uvicorn main:app --reload --port 8000
```

Mở http://localhost:8000

---

## ☁️ Deploy Render (khuyến nghị)

1. Push repo lên GitHub.
2. Tạo **PostgreSQL** database trên Render → copy `Internal Database URL`.
3. Tạo Web Service, kết nối repo.
4. Environment Variables:
   | Key | Giá trị |
   |-----|---------|
   | `DATABASE_URL` | URL PostgreSQL |
   | `ADMIN_API_KEY` | Chuỗi dài ngẫu nhiên |
   | `ENCRYPTION_KEY` | Kết quả từ `scripts/generate_keys.py` |
   | `ENVIRONMENT` | `production` |
5. Build: `pip install -r requirements.txt`
6. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`

File `render.yaml` đã cấu hình sẵn.

---

## 📡 API quan trọng

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/api/dang-ky-tim-kiem/` | Nộp hồ sơ + so khớp |
| GET | `/api/tra-cuu/{ma_ho_so}` | Tra cứu trạng thái |
| GET | `/api/admin/danh-sach/` | Danh sách hồ sơ (Admin) |
| GET | `/api/admin/matches/` | Lịch sử khớp |
| GET | `/api/admin/backup/` | **Xuất toàn bộ dữ liệu ADN** |
| GET | `/api/admin/stats/` | Thống kê |
| PATCH | `/api/admin/ho-so/{id}/status` | Cập nhật trạng thái |
| GET | `/health` | Health check |

Tất cả endpoint Admin cần header: `X-Admin-Key: <key>`

---

## 📁 Cấu trúc

```
dna-matching-system/
├── main.py                 # FastAPI app
├── config.py               # Cấu hình
├── models.py               # SQLAlchemy models
├── matching.py             # Logic so khớp
├── security.py             # Mã hóa SĐT/Email
├── alembic/                # Migration (nâng cấp không mất data)
├── scripts/
│   ├── generate_keys.py
│   └── backup_local.py
├── static/
├── templates/
├── requirements.txt
├── render.yaml
└── README.md
```

---

## ⚠️ Lưu ý

- Hệ thống chỉ **khoanh vùng sơ bộ**. Kết luận quan hệ huyết thống chính thức cần xét nghiệm tại cơ sở y tế.
- Luôn backup trước khi thay đổi lớn.
- Không commit file `.env` hoặc `ENCRYPTION_KEY` lên GitHub.

---

**Phan Quý Vinh** – 0975 898 828
