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
connect_args = {"check_same_thread": False} if not settings.is_postgres else {}
engine = create_engine(settings.sqlalchemy_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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
    
    # Giữ các trường cũ để tương thích ngược dữ liệu nếu cần
    dia_chi_truoc_day: Optional[str] = Field(None, max_length=300)
    vi_tri_that_lac: Optional[str] = Field(None, max_length=300)
    nam_that_lac: Optional[str] = Field(None, max_length=20)
    
    # === CẬP NHẬT TRƯỜNG MỚI THEO FORM INDEX.HTML ===
    # 2. Thông tin người cần tìm
    nguoi_can_tim_ho_ten: Optional[str] = Field(None, max_length=200)
    nguoi_can_tim_bi_danh: Optional[str] = Field(None, max_length=200)
    nguoi_can_tim_nam_sinh: Optional[str] = Field(None, max_length=50)
    nguoi_can_tim_gioi_tinh: Optional[str] = Field(None, max_length=20)
    dac_diem_nhan_dang: Optional[str] = Field(None)
    
    # 3. Thông tin địa lý & thời gian chi tiết mới
    noi_cuoi_cung_gap: Optional[str] = Field(None, max_length=300)
    thoi_diem_mat_lien_lac: Optional[str] = Field(None, max_length=100)
    hoan_canh_mat_lien_lac: Optional[str] = Field(None)
    noi_thuong_sinh_song_truoc_day: Optional[str] = Field(None, max_length=300)
    cac_cach_da_thu: Optional[str] = Field(None)
    
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

    # Map dữ liệu sang Database model mới
    new_user = UserDB(
        id=user_id,
        ho_ten=user.ho_ten.strip(),
        loai_tim_kiem=user.loai_tim_kiem,
        so_dien_thoai_enc=encrypt_field(user.so_dien_thoai),
        email_enc=encrypt_field(user.email.lower()),
        dia_chi_hien_tai=user.dia_chi_hien_tai.strip(),
        
        # Đồng bộ các trường địa lý cũ (bằng cách lấy giá trị từ trường chi tiết mới tương đương)
        dia_chi_truoc_day=(user.noi_thuong_sinh_song_truoc_day or user.dia_chi_truoc_day or "").strip() or None,
        vi_tri_that_lac=(user.noi_cuoi_cung_gap or user.vi_tri_that_lac or "").strip() or None,
        nam_that_lac=(user.thoi_diem_mat_lien_lac or user.nam_that_lac or "").strip() or None,
        
        # Lưu các trường thông tin chi tiết mới vào DB
        nguoi_can_tim_ho_ten=(user.nguoi_can_tim_ho_ten or "").strip() or None,
        nguoi_can_tim_bi_danh=(user.nguoi_can_tim_bi_danh or "").strip() or None,
        nguoi_can_tim_nam_sinh=(user.nguoi_can_tim_nam_sinh or "").strip() or None,
        nguoi_can_tim_gioi_tinh=(user.nguoi_can_tim_gioi_tinh or "").strip() or None,
        dac_diem_nhan_dang=(user.dac_diem_nhan_dang or "").strip() or None,
        
        noi_cuoi_cung_gap=(user.noi_cuoi_cung_gap or "").strip() or None,
        thoi_diem_mat_lien_lac=(user.thoi_diem_mat_lien_lac or "").strip() or None,
        hoan_canh_mat_lien_lac=(user.hoan_canh_mat_lien_lac or "").strip() or None,
        noi_thuong_sinh_song_truoc_day=(user.noi_thuong_sinh_song_truoc_day or "").strip() or None,
        cac_cach_da_thu=(user.cac_cach_da_thu or "").strip() or None,
        
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

        # Kế thừa hàm tính điểm cũ bằng cách truyền tham số địa lý tương thích
        result = tinh_diem_tong_hop(
            user_dna=user_dna,
            target_dna=target_dna,
            user_loai=user.loai_tim_kiem,
            target_loai=target.loai_tim_kiem,
            user_vi_tri=new_user.vi_tri_that_lac,
            target_vi_tri=target.vi_tri_that_lac,
            user_dia_chi_truoc=new_user.dia_chi_truoc_day,
            target_dia_chi_truoc=target.dia_chi_truoc_day,
            user_dia_chi_hien=user.dia_chi_hien_tai,
            target_dia_chi_hien=target.dia_chi_hien_tai,
            user_nam=new_user.nam_that_lac,
            target_nam=target.nam_that_lac,
        )

        if result and result["score"] >= 55:
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
