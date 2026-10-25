#!/usr/bin/env python3
"""
Backup nhanh khi chạy local (SQLite).
Khi dùng PostgreSQL, dùng endpoint /api/admin/backup/ hoặc pg_dump.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "dna_data.db"
OUT = Path(__file__).resolve().parent.parent / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

if not DB.exists():
    print("Chưa có file dna_data.db – chưa có dữ liệu để backup.")
    exit(1)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT * FROM users").fetchall()
conn.close()

data = [dict(r) for r in rows]
with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"exported_at": datetime.utcnow().isoformat(), "total": len(data), "users": data}, f, ensure_ascii=False, indent=2)

print(f"Đã backup {len(data)} hồ sơ → {OUT}")
