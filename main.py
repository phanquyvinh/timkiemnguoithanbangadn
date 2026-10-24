import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import APIKeyHeader
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Hệ thống Kết nối Huyết thống Miễn phí",
    description="Ứng dụng hỗ trợ cộng đồng tìm kiếm người thân thất lạc qua chỉ số ADN.\nBản quyền thuộc về Admin: Phan Quý Vinh (SDT: 0975898828).",
    version="1.0.0"
)

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Khóa Admin
ADMIN_API_KEY = "PhanQuyVinh_Secured_2026_0975898828"
api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)

def verify_admin(api_key: str = Security(api_key_header)):
    if api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Quyền truy cập bị từ chối. Chỉ Admin Phan Quý Vinh mới có quyền thay đổi.")
    return api_key

# Mô hình DNA (12 locus phổ biến)
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
    loai_tim_kiem: str  # "TIM_CHA_ME", "TIM_CON", "TIM_ANH_CH_EM"
    so_dien_thoai: str
    email: str
    dia_chi: str
    anh_chan_dung_url: Optional[str] = None
    dna_data: DNAModel

# Cơ sở dữ liệu tạm thời (RAM) - lưu ý: dữ liệu sẽ mất khi restart server
database_server: List[UserProfile] = []

def kiem_tra_truc_he(dna_con: Dict, dna_bm: Dict) -> bool:
    sai_lech = 0
    for locus in dna_con.keys():
        if locus in dna_bm:
            giao_nhau = set(dna_con[locus]).intersection(set(dna_bm[locus]))
            if not giao_nhau:
                sai_lech += 1
                if sai_lech > 1:  # Cho phép tối đa 1 đột biến
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

@app.post("/api/dang-ky-tim-kiem/")
def dang_ky_ho_so(user: UserProfile):
    database_server.append(user)
    ket_qua_goi_y = []

    for target in database_server:
        if target.id == user.id:
            continue

        # 1. Khớp Cha/Mẹ - Con
        if (user.loai_tim_kiem == "TIM_CON" and target.loai_tim_kiem == "TIM_CHA_ME") or \
           (user.loai_tim_kiem == "TIM_CHA_ME" and target.loai_tim_kiem == "TIM_CON"):
            if kiem_tra_truc_he(user.dna_data.model_dump(), target.dna_data.model_dump()):
                ket_qua_goi_y.append({
                    "ho_ten": target.ho_ten,
                    "loai_quan_he": "Cha/Mẹ - Con trực hệ (Khoanh vùng)",
                    "thong_bao": "Vui lòng bấm 'Yêu cầu kết nối' để ẩn danh trao đổi số điện thoại bảo mật."
                })

        # 2. Khớp Anh/Chị/Em
        elif user.loai_tim_kiem == "TIM_ANH_CH_EM" and target.loai_tim_kiem == "TIM_ANH_CH_EM":
            if kiem_tra_anh_em_ruot(user.dna_data.model_dump(), target.dna_data.model_dump()):
                ket_qua_goi_y.append({
                    "ho_ten": target.ho_ten,
                    "loai_quan_he": "Anh/Chị/Em ruột tiềm năng (Khoanh vùng)",
                    "thong_bao": "Vui lòng bấm 'Yêu cầu kết nối' để ẩn danh trao đổi số điện thoại bảo mật."
                })

    return {
        "status": "Hệ thống đã ghi nhận hồ sơ bảo mật thành công",
        "so_luong_trung_khop_uoc_tinh": len(ket_qua_goi_y),
        "goi_y_phah_he": ket_qua_goi_y,
        "copyright": "Bản quyền ứng dụng thuộc về Phan Quý Vinh - 0975898828"
    }

@app.post("/api/admin/update-system/", dependencies=[Depends(verify_admin)])
def update_system():
    return {"status": "Xác thực Admin Phan Quý Vinh thành công. Cấu hình hệ thống đã được cập nhật."}

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "DNA Matching System"}

# Serve frontend
BASE_DIR = Path(__file__).resolve().parent

@app.get("/")
async def serve_index():
    return FileResponse(BASE_DIR / "index.html")
