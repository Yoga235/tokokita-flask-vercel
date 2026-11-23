"""Periksa koneksi ke database PostgreSQL dan struktur tabel tanpa mengubah data."""
from app import app, database
import psycopg

TABLES = ("users", "products", "customers", "sales")

if __name__ == "__main__":
    try:
        with app.app_context():
            db = database()
            result = db.execute("SELECT current_database() AS database_name, version() AS version").fetchone()
            print("[OK] Terhubung ke PostgreSQL database:", result["database_name"])
            for name in TABLES:
                found = db.execute("SELECT to_regclass(?) AS table_name", ("public." + name,)).fetchone()["table_name"]
                if not found:
                    print(f"[BELUM ADA] Tabel {name}. Jalankan sql/01_schema.sql di Neon SQL Editor atau pgAdmin.")
                else:
                    total = db.execute(f"SELECT COUNT(*) AS n FROM {name}").fetchone()["n"]
                    print(f"[OK] {name}: {total} baris")
    except psycopg.OperationalError as exc:
        print("[GAGAL] Tidak bisa terhubung ke PostgreSQL.")
        print("Periksa DATABASE_URL (Neon) atau PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE (lokal) di .env")
        print("Pesan PostgreSQL:", exc)
        raise SystemExit(1)
    except psycopg.Error as exc:
        print("[GAGAL] SQL gagal:", exc)
        raise SystemExit(1)
