#!/usr/bin/env python3
"""Tạo ENCRYPTION_KEY và gợi ý ADMIN_API_KEY an toàn."""
from cryptography.fernet import Fernet
import secrets

print("=" * 60)
print("KHÓA BẢO MẬT CHO HỆ THỐNG ADN")
print("=" * 60)
print()
print("ENCRYPTION_KEY (dán vào biến môi trường):")
print(Fernet.generate_key().decode())
print()
print("ADMIN_API_KEY (gợi ý – bạn có thể đổi):")
print(secrets.token_urlsafe(32))
print()
print("Lưu hai giá trị này vào Render Environment Variables.")
print("KHÔNG commit vào GitHub!")
print("=" * 60)
