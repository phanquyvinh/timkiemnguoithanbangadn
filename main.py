import os
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import APIKeyHeader
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base

# ==================== CẤU HÌNH DATABASE ====================
DATABASE_URL = os.getenv("DATABASE_URL")

# Render PostgreSQL dùng postgres://, SQLAlchemy cần postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

Base = declarative_base()

class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    ho_ten = Column(String(200), nullable=False)
    loai_tim_kiem = Column(String(50), nullable=False)
    so_dien_thoai = Column(String(30), nullable=False)
    email = Column(String(150), nullable=False)
    dia_chi = Column(String(300), nullable=False)
    dna_data = Column(Text, nullable=False)  # Lưu JSON

# Nếu có DATABASE_URL thì dùng PostgreSQL, không thì dùng SQLite tạm (vẫn tốt hơn RAM)
if DATABASE_URL:
    engine = create_engine(DATABASE_URL)
else:
    # SQLite file - dữ liệu vẫn còn khi restart (nhưng mất khi Render xóa disk Free)
    engine = create_engine("sqlite:///./dna_data.db", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==================== APP ====================
app = FastAPI(
    title="Hệ thống Kết nối Huyết thống Miễn phí",
    description="Ứng dụng hỗ trợ cộng đồng tìm kiếm người thân thất lạc qua chỉ số ADN.\nBản quyền thuộc về Admin: Phan Quý Vinh (SDT: 0975898828).",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "PhanQuyVinh_Secured_2026_0975898828")
api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)

def verify_admin(api_key: str = Security(api_key_header)):
    if api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Quyền truy cập bị từ chối. Chỉ Admin Phan Quý Vinh mới có quyền.")
    return api_key

# ==================== MODELS ====================
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

class UserProfile(BaseModel):
    id: int
    ho_ten: str
    loai_tim_kiem: str
    so_dien_thoai: str
    email: str
    dia_chi: str
    anh_chan_dung_url: Optional[str] = None
    dna_data: DNAModel

# ==================== LOGIC SO SÁNH ====================
def kiem_tra_truc_he(dna_con: Dict, dna_bm: Dict) -> bool:
    sai_lech = 0
    for locus in dna_con.keys():
        if locus in dna_bm:
            giao_nhau = set(dna_con[locus]).intersection(set(dna_bm[locus]))
            if not giao_nhau:
                sai_lech += 1
                if sai_lech > 1:
                    return False
    return True

def kiem_tra_anh_em_ruot(dna_1: Dict, dna_2: Dict) -> bool:
    diem_chung = 0
    tong_so_locus = 0
    for locus in dna_1.keys():
        if locus in dna_2:
            tong_so_locus += 1
            giao_nhau = set(dna_1[locus]).intersection(set(dna_2[locus]))
            if giao_nhau:
                diem_chung += 1
    return (diem_chung / tong_so_locus) >= 0.55 if tong_so_locus > 0 else False

# ==================== API ====================
@app.post("/api/dang-ky-tim-kiem/")
def dang_ky_ho_so(user: UserProfile, db=Depends(get_db)):
    # Lưu vào database
    new_user = UserDB(
        id=user.id,
        ho_ten=user.ho_ten,
        loai_tim_kiem=user.loai_tim_kiem,
        so_dien_thoai=user.so_dien_thoai,
        email=user.email,
        dia_chi=user.dia_chi,
        dna_data=json.dumps(user.dna_data.model_dump())
    )
    db.add(new_user)
    db.commit()

    # Lấy tất cả hồ sơ để so sánh
    all_users = db.query(UserDB).all()
    ket_qua_goi_y = []

    user_dna = user.dna_data.model_dump()

    for target in all_users:
        if target.id == user.id:
            continue

        try:
            target_dna = json.loads(target.dna_data)
        except:
            continue

        # 1. Cha/Mẹ - Con
        if (user.loai_tim_kiem == "TIM_CON" and target.loai_tim_kiem == "TIM_CHA_ME") or \
           (user.loai_tim_kiem == "TIM_CHA_ME" and target.loai_tim_kiem == "TIM_CON"):
            if kiem_tra_truc_he(user_dna, target_dna):
                ket_qua_goi_y.append({
                    "ho_ten": target.ho_ten,
                    "loai_quan_he": "Cha/Mẹ - Con trực hệ (Khoanh vùng)",
                    "thong_bao": "Vui lòng chờ quản trị viên duyệt kết nối bảo mật."
                })

        # 2. Anh/Chị/Em
        elif user.loai_tim_kiem == "TIM_ANH_CH_EM" and target.loai_tim_kiem == "TIM_ANH_CH_EM":
            if kiem_tra_anh_em_ruot(user_dna, target_dna):
                ket_qua_goi_y.append({
                    "ho_ten": target.ho_ten,
                    "loai_quan_he": "Anh/Chị/Em ruột tiềm năng (Khoanh vùng)",
                    "thong_bao": "Vui lòng chờ quản trị viên duyệt kết nối bảo mật."
                })

    return {
        "status": "Hệ thống đã ghi nhận hồ sơ bảo mật thành công",
        "so_luong_trung_khop_uoc_tinh": len(ket_qua_goi_y),
        "goi_y_phah_he": ket_qua_goi_y,
        "copyright": "Bản quyền ứng dụng thuộc về Phan Quý Vinh - 0975898828"
    }

@app.get("/api/admin/danh-sach/")
def danh_sach_ho_so(api_key: str = Depends(verify_admin), db=Depends(get_db)):
    """Chỉ Admin xem được danh sách hồ sơ"""
    users = db.query(UserDB).all()
    result = []
    for u in users:
        result.append({
            "id": u.id,
            "ho_ten": u.ho_ten,
            "loai_tim_kiem": u.loai_tim_kiem,
            "so_dien_thoai": u.so_dien_thoai,
            "email": u.email,
            "dia_chi": u.dia_chi
        })
    return {"tong_so": len(result), "danh_sach": result}

@app.post("/api/admin/update-system/", dependencies=[Depends(verify_admin)])
def update_system():
    return {"status": "Xác thực Admin Phan Quý Vinh thành công."}

@app.get("/health")
def health_check():
    db_type = "PostgreSQL" if DATABASE_URL else "SQLite"
    return {"status": "ok", "database": db_type, "version": "2.0.0"}

# Serve frontend
BASE_DIR = Path(__file__).resolve().parent

@app.get("/")
async def serve_index():
    return FileResponse(BASE_DIR / "index.html")
