"""
Hệ thống Kết nối Huyết thống qua ADN – v4.0
Bản quyền: Phan Quý Vinh (0975898828)

Đặc điểm:
- Dữ liệu ADN tích lũy vĩnh viễn (PostgreSQL + Alembic)
- Mã hóa SĐT/Email
- So khớp đa tiêu chí (ADN + địa lý)
- Nâng cấp code không mất dữ liệu cũ
- Admin API + backup
"""

import os
import json
import uuid
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.security import APIKeyHeader
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr, field_validator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import get_settings
from models import Base, UserDB, MatchLog
from security import encrypt_field, decrypt_field, is_encryption_enabled
from matching import tinh_diem_tong_hop

settings = get_settings()

# ==================== DATABASE ====================
# connect_args chỉ cho SQLite
connect_args = {"check_same_thread": False} if not settings.is_postgres else {}
engine = create_engine(settings.sqlalchemy_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Tạo bảng nếu chưa có (lần đầu). Sau này dùng Alembic để nâng cấp schema.
Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== APP ====================
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title=settings.APP_NAME,
    description=f"Bản quyền: {settings.COPYRIGHT}",
    version=settings.VERSION,
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
    redoc_url=None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS if settings.ALLOWED_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


def verify_admin(api_key: str = Security(api_key_header)):
    if not api_key or api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Quyền truy cập bị từ chối.")
    return api_key


# ==================== SCHEMAS ====================
class DNAModel(BaseModel):
    D3S1358: List[float] = Field(..., min_length=2, max_length=2)
    vWA: List[float] = Field(..., min_length=2, max_length=2)
    FGA: List[float] = Field(..., min_length=2, max_length=2)
    TH01: List[float] = Field(..., min_length=2, max_length=2)
    D21S11: List[float] = Field(..., min_length=2, max_length=2)
    D18S51: List[float] = Field(..., min_length=2, max_length=2)
    D5S818: List[float] = Field(..., min_length=2, max_length=2)
    D13S317: List[float] = Field(..., min_length=2, max_length=2)
    D7S820: List[float] = Field(..., min_length=2, max_length=2)
    D16S539: List[float] = Field(..., min_length=2, max_length=2)
    CSF1PO: List[float] = Field(..., min_length=2, max_length=2)
    TPOX: List[float] = Field(..., min_length=2, max_length=2)

    @field_validator("*", mode="before")
    @classmethod
    def check_alleles(cls, v):
        if isinstance(v, list) and len(v) == 2:
            for a in v:
                if not isinstance(a, (int, float)) or a < 1 or a > 50:
                    raise ValueError("Allele phải trong khoảng 1–50")
        return v


class UserRegister(BaseModel):
    ho_ten: str = Field(..., min_length=2, max_length=200)
    loai_tim_kiem: str = Field(..., pattern="^(TIM_CON|TIM_CHA_ME|TIM_ANH_CH_EM)$")
    so_dien_thoai: str = Field(..., min_length=9, max_length=15)
    email: EmailStr
    dia_chi_hien_tai: str = Field(..., min_length=2, max_length=300)
    dia_chi_truoc_day: Optional[str] = Field(None, max_length=300)
    vi_tri_that_lac: Optional[str] = Field(None, max_length=300)
    nam_that_lac: Optional[str] = Field(None, max_length=20)
    dna_data: DNAModel

    @field_validator("so_dien_thoai")
    @classmethod
    def validate_phone(cls, v):
        cleaned = re.sub(r"[\s\-\.]", "", v)
        if not re.match(r"^(0|\+84)[0-9]{8,11}$", cleaned):
            raise ValueError("Số điện thoại không hợp lệ")
        return cleaned


class StatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(pending|reviewed|matched|rejected)$")
    notes: Optional[str] = None


# ==================== ROUTES ====================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "version": settings.VERSION, "copyright": settings.COPYRIGHT},
    )


@app.post("/api/dang-ky-tim-kiem/")
@limiter.limit(settings.RATE_LIMIT)
def dang_ky_ho_so(request: Request, user: UserRegister, db=Depends(get_db)):
    user_id = str(uuid.uuid4())

    new_user = UserDB(
        id=user_id,
        ho_ten=user.ho_ten.strip(),
        loai_tim_kiem=user.loai_tim_kiem,
        so_dien_thoai_enc=encrypt_field(user.so_dien_thoai),
        email_enc=encrypt_field(user.email.lower()),
        dia_chi_hien_tai=user.dia_chi_hien_tai.strip(),
        dia_chi_truoc_day=(user.dia_chi_truoc_day or "").strip() or None,
        vi_tri_that_lac=(user.vi_tri_that_lac or "").strip() or None,
        nam_that_lac=(user.nam_that_lac or "").strip() or None,
        dna_data=json.dumps(user.dna_data.model_dump()),
        status="pending",
    )
    db.add(new_user)
    db.commit()

    # So khớp với toàn bộ hồ sơ đã tích lũy
    all_users = db.query(UserDB).filter(UserDB.id != user_id).all()
    ket_qua = []
    user_dna = user.dna_data.model_dump()

    for target in all_users:
        try:
            target_dna = json.loads(target.dna_data)
        except Exception:
            continue

        result = tinh_diem_tong_hop(
            user_dna=user_dna,
            target_dna=target_dna,
            user_loai=user.loai_tim_kiem,
            target_loai=target.loai_tim_kiem,
            user_vi_tri=user.vi_tri_that_lac,
            target_vi_tri=target.vi_tri_that_lac,
            user_dia_chi_truoc=user.dia_chi_truoc_day,
            target_dia_chi_truoc=target.dia_chi_truoc_day,
            user_dia_chi_hien=user.dia_chi_hien_tai,
            target_dia_chi_hien=target.dia_chi_hien_tai,
            user_nam=user.nam_that_lac,
            target_nam=target.nam_that_lac,
        )

        if result and result["score"] >= 55:
            # Ghi log match (tích lũy lịch sử)
            log = MatchLog(
                user_id=user_id,
                target_id=target.id,
                loai_quan_he=result["loai_quan_he"],
                diem_tin_cay=result["score"],
                ly_do=json.dumps(result["reasons"], ensure_ascii=False),
            )
            db.add(log)

            ket_qua.append({
                "ho_ten": target.ho_ten,
                "loai_quan_he": result["loai_quan_he"],
                "diem_tin_cay": result["score"],
                "ly_do": result["reasons"],
                "thong_bao": "Đã khoanh vùng. Chờ Admin duyệt kết nối bảo mật.",
            })

    db.commit()
    ket_qua.sort(key=lambda x: x["diem_tin_cay"], reverse=True)

    return {
        "status": "Hồ sơ đã được ghi nhận bảo mật thành công",
        "ma_ho_so": user_id,
        "so_luong_trung_khop_uoc_tinh": len(ket_qua),
        "goi_y_phah_he": ket_qua[:15],
        "huong_dan": (
            "Hãy lưu MÃ HỒ SƠ để tra cứu sau. "
            "Hệ thống bảo mật số điện thoại đối phương. "
            "Admin sẽ liên hệ khi có kết quả được duyệt."
        ),
        "encryption_enabled": is_encryption_enabled(),
        "copyright": settings.COPYRIGHT,
    }


@app.get("/api/tra-cuu/{ma_ho_so}")
@limiter.limit("20/minute")
def tra_cuu(request: Request, ma_ho_so: str, db=Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.id == ma_ho_so).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ")
    return {
        "ma_ho_so": user.id,
        "ho_ten": user.ho_ten,
        "loai_tim_kiem": user.loai_tim_kiem,
        "status": user.status,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "thong_bao": (
            "Hồ sơ đang được bảo mật. "
            "Khi có kết quả duyệt, Admin sẽ liên hệ qua SĐT/Email bạn đã cung cấp."
        ),
    }


# ---------- ADMIN ----------
@app.get("/api/admin/danh-sach/")
def admin_list(
    api_key: str = Depends(verify_admin),
    db=Depends(get_db),
    status: Optional[str] = None,
    limit: int = 200,
):
    q = db.query(UserDB).order_by(UserDB.created_at.desc())
    if status:
        q = q.filter(UserDB.status == status)
    users = q.limit(min(limit, 500)).all()
    result = []
    for u in users:
        result.append({
            "id": u.id,
            "ho_ten": u.ho_ten,
            "loai_tim_kiem": u.loai_tim_kiem,
            "so_dien_thoai": decrypt_field(u.so_dien_thoai_enc),
            "email": decrypt_field(u.email_enc),
            "dia_chi_hien_tai": u.dia_chi_hien_tai,
            "dia_chi_truoc_day": u.dia_chi_truoc_day,
            "vi_tri_that_lac": u.vi_tri_that_lac,
            "nam_that_lac": u.nam_that_lac,
            "status": u.status,
            "notes": u.notes,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })
    return {
        "tong_so": len(result),
        "encryption_enabled": is_encryption_enabled(),
        "danh_sach": result,
    }


@app.patch("/api/admin/ho-so/{user_id}/status")
def admin_update_status(
    user_id: str,
    body: StatusUpdate,
    api_key: str = Depends(verify_admin),
    db=Depends(get_db),
):
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(404, "Không tìm thấy hồ sơ")
    user.status = body.status
    if body.notes is not None:
        user.notes = body.notes
    user.updated_at = datetime.utcnow()
    db.commit()
    return {"status": "ok", "id": user_id, "new_status": body.status}


@app.get("/api/admin/matches/")
def admin_matches(api_key: str = Depends(verify_admin), db=Depends(get_db), limit: int = 100):
    logs = db.query(MatchLog).order_by(MatchLog.created_at.desc()).limit(limit).all()
    return {
        "tong_so": len(logs),
        "matches": [
            {
                "id": m.id,
                "user_id": m.user_id,
                "target_id": m.target_id,
                "loai_quan_he": m.loai_quan_he,
                "diem_tin_cay": m.diem_tin_cay,
                "ly_do": json.loads(m.ly_do) if m.ly_do else [],
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "is_notified": m.is_notified,
            }
            for m in logs
        ],
    }


@app.get("/api/admin/backup/")
def admin_backup(api_key: str = Depends(verify_admin), db=Depends(get_db)):
    """
    Xuất toàn bộ dữ liệu ADN (dạng JSON) để backup.
    Giữ file này an toàn – đây là bản sao dữ liệu quan trọng.
    """
    users = db.query(UserDB).all()
    data = []
    for u in users:
        data.append({
            "id": u.id,
            "ho_ten": u.ho_ten,
            "loai_tim_kiem": u.loai_tim_kiem,
            "so_dien_thoai": decrypt_field(u.so_dien_thoai_enc),
            "email": decrypt_field(u.email_enc),
            "dia_chi_hien_tai": u.dia_chi_hien_tai,
            "dia_chi_truoc_day": u.dia_chi_truoc_day,
            "vi_tri_that_lac": u.vi_tri_that_lac,
            "nam_that_lac": u.nam_that_lac,
            "dna_data": json.loads(u.dna_data),
            "status": u.status,
            "notes": u.notes,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })
    return {
        "version": settings.VERSION,
        "exported_at": datetime.utcnow().isoformat(),
        "total": len(data),
        "users": data,
    }


@app.get("/api/admin/stats/")
def admin_stats(api_key: str = Depends(verify_admin), db=Depends(get_db)):
    total = db.query(UserDB).count()
    pending = db.query(UserDB).filter(UserDB.status == "pending").count()
    matched = db.query(UserDB).filter(UserDB.status == "matched").count()
    matches = db.query(MatchLog).count()
    return {
        "total_ho_so": total,
        "pending": pending,
        "matched": matched,
        "total_matches_logged": matches,
        "encryption_enabled": is_encryption_enabled(),
        "database": "PostgreSQL" if settings.is_postgres else "SQLite",
        "version": settings.VERSION,
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": settings.VERSION,
        "database": "PostgreSQL" if settings.is_postgres else "SQLite",
        "encryption": is_encryption_enabled(),
        "features": [
            "DNA + location multi-criteria matching",
            "Encrypted phone/email",
            "Match history log",
            "Admin backup & status management",
            "Alembic-ready for zero-data-loss upgrades",
        ],
    }
