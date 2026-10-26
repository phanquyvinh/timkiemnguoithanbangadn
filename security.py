"""
Bảo mật dữ liệu nhạy cảm (SĐT, Email).
Đọc ENCRYPTION_KEY trực tiếp từ môi trường mỗi lần (tránh lỗi cache / import sớm).
"""
import os
from cryptography.fernet import Fernet, InvalidToken

_fernet = None
_fernet_loaded = False


def _get_fernet():
    global _fernet, _fernet_loaded
    if _fernet_loaded:
        return _fernet

    _fernet_loaded = True
    key = (os.getenv("ENCRYPTION_KEY") or "").strip().strip('"').strip("'")
    if not key:
        _fernet = None
        return None
    try:
        _fernet = Fernet(key.encode("utf-8"))
        return _fernet
    except Exception:
        _fernet = None
        return None


def encrypt_field(plain: str) -> str:
    f = _get_fernet()
    if f is None:
        return plain
    return f.encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_field(token: str) -> str:
    f = _get_fernet()
    if f is None:
        return token
    try:
        return f.decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception):
        return token


def is_encryption_enabled() -> bool:
    return _get_fernet() is not None
