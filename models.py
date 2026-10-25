"""
SQLAlchemy models.
Khi nâng cấp schema → dùng Alembic migration, KHÔNG bao giờ drop table.
Dữ liệu ADN cũ luôn được giữ nguyên.
"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, DateTime, Integer, Float, Index, Boolean
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class UserDB(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, index=True)  # UUID
    ho_ten = Column(String(200), nullable=False, index=True)
    loai_tim_kiem = Column(String(50), nullable=False, index=True)

    # Thông tin liên lạc – được mã hóa khi có ENCRYPTION_KEY
    so_dien_thoai_enc = Column(String(500), nullable=False)
    email_enc = Column(String(500), nullable=False)

    # Địa lý – dùng để thu hẹp kết quả
    dia_chi_hien_tai = Column(String(300), nullable=False)
    dia_chi_truoc_day = Column(String(300), nullable=True, index=True)
    vi_tri_that_lac = Column(String(300), nullable=True, index=True)
    nam_that_lac = Column(String(20), nullable=True)

    # ADN lưu JSON text (12 locus)
    dna_data = Column(Text, nullable=False)

    # Trạng thái
    status = Column(String(30), default="pending", index=True)
    # pending | reviewed | matched | rejected

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = Column(Text, nullable=True)  # Ghi chú của admin

    __table_args__ = (
        Index("ix_users_loai_status", "loai_tim_kiem", "status"),
    )


class MatchLog(Base):
    """Lưu lịch sử các lần phát hiện khớp để audit & không mất thông tin khi nâng cấp."""
    __tablename__ = "match_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)
    target_id = Column(String(36), nullable=False, index=True)
    loai_quan_he = Column(String(100), nullable=False)
    diem_tin_cay = Column(Float, nullable=False)
    ly_do = Column(Text, nullable=True)  # JSON list
    created_at = Column(DateTime, default=datetime.utcnow)
    is_notified = Column(Boolean, default=False)
