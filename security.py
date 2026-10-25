"""
Bảo mật dữ liệu nhạy cảm (SĐT, Email).
ADN được lưu dạng JSON nhưng chỉ Admin mới xem được chi tiết.
"""
from cryptography.fernet import Fernet, InvalidToken
from config import get_settings

_settings = get_settings()
_fernet: Fernet | None = None


def _get_fernet() -> Fernet | None:
    global _fernet
    if _fernet is not None:
        return _fernet
    key = _settings.ENCRYPTION_KEY
    if not key:
        return None
    try:
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
        return _fernet
    except Exception:
        return None


def encrypt_field(plain: str) -> str:
    """Mã hóa chuỗi. Nếu chưa có ENCRYPTION_KEY thì trả về plain (dev mode)."""
    f = _get_fernet()
    if f is None:
        return plain
    return f.encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_field(token: str) -> str:
    """Giải mã. Nếu không phải ciphertext hoặc lỗi → trả nguyên bản."""
    f = _get_fernet()
    if f is None:
        return token
    try:
        return f.decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception):
        return token  # dữ liệu cũ chưa mã hóa vẫn đọc được


def is_encryption_enabled() -> bool:
    return _get_fernet() is not None
