# TokoKita — Flask + PostgreSQL (lokal / Vercel)

Aplikasi CRUD penjualan toko untuk tugas: login/register, dashboard, master barang dan pelanggan, transaksi stok otomatis, laporan dan ekspor CSV.

## Penting

PostgreSQL `localhost` di PC sendiri **tidak bisa dipakai oleh aplikasi Vercel**. Untuk deploy, pakai PostgreSQL yang bisa diakses internet (disarankan Neon, tetap PostgreSQL). pgAdmin 4 dapat dipakai untuk mengelola kedua database.

## Isi proyek

- `app.py` — Flask, semua route aplikasi.
- `templates/`, `public/style.css` — UI.
- `requirements.txt`, `.python-version`, `vercel.json` — konfigurasi Vercel.
- `sql/01_schema.sql` — buat empat tabel & indeks di **database yang sudah dibuat**.
- `sql/02_sample_data.sql` — contoh data barang dan pelanggan (opsional).
- `.env.example` — contoh konfigurasi, **jangan unggah `.env`**.
- `check_db.py` — cek koneksi lokal (gunakan `PG*`).

## Menjalankan di komputer Windows + pgAdmin 4

1. Di pgAdmin, buat database `tokokita_db`. Jalankan `sql/01_schema.sql` via Query Tool pada database tersebut.
2. Buka terminal VS Code di folder ini.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

3. Edit `.env` dan isi `PGPASSWORD` yang benar. Pastikan baris `DATABASE_URL` masih berupa komentar.
4. Jalankan `python check_db.py` lalu `python app.py`. Buka `http://127.0.0.1:5000`.

## Deploy GitHub → Vercel + Neon

1. Di <https://console.neon.tech> buat project PostgreSQL (misalnya `tokokita-db`), database misalnya `neondb`.
2. Buka SQL Editor pada database Neon, jalankan **hanya** file `sql/01_schema.sql` (jangan jalankan `00_create_database.sql` karena database Neon sudah dibuat). Untuk contoh produk, jalankan `sql/02_sample_data.sql` sekali.
3. Klik `Connect` pada Neon, salin **pooled connection string** (host berakhiran `-pooler`), yang termasuk SSL. Simpan pribadi.
4. Buat repo GitHub kosong, misalnya `tokokita-flask-vercel`. Dari terminal folder ini:

```powershell
git init
git add .
git commit -m "TokoKita Flask PostgreSQL Vercel"
git branch -M main
git remote add origin https://github.com/USERNAME/tokokita-flask-vercel.git
git push -u origin main
```

   Ganti `USERNAME` dengan username GitHub Anda. Login ke GitHub sesuai metode autentikasi yang disediakan Git atau VS Code. **Pastikan `.env` tidak ikut terunggah.**
5. Buka <https://vercel.com/new> → Import Git Repository → pilih repo → `Root Directory: ./`. Gunakan pengaturan default Flask (Python), tanpa Build/Output Command khusus.
6. Di **Environment Variables** (pilih `Production`) isi:

   - `DATABASE_URL` = URL pooled Neon.
   - `SECRET_KEY` = rahasia acak panjang dari perintah `python -c "import secrets; print(secrets.token_hex(32))"`.

7. Klik `Deploy`. Jika environment variables baru ditambahkan setelah deploy, lakukan `Redeploy`.
8. Kunjungi domain `https://nama-proyek.vercel.app` yang ditampilkan Vercel; uji Register → Login → Barang → Pelanggan → Penjualan → Laporan.

## pgAdmin 4 untuk Neon (opsional)

Klik `Register` → `Server`. Di tab **General** beri nama `TokoKita Neon`; tab **Connection** isi Host, Port `5432`, Username, Password, dan Maintenance database menurut tombol `Connect` pada Neon. Di tab **SSL** gunakan `SSL mode = Require` jika tersedia. Simpan. **Jangan menempel satu connection string ke field Host.**

## Keterangan teknis

- Aplikasi membaca `DATABASE_URL` jika diisi; jika tidak, pakai `PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD`.
- Vercel harus punya `DATABASE_URL` dan `SECRET_KEY`. Tanpa itu, aplikasi sengaja menolak startup agar tidak salah memakai database lokal atau file kunci.
- SQLite tidak digunakan. SQL sudah kompatibel PostgreSQL.
- File `sql/01_schema.sql` tidak otomatis dijalankan saat deploy; jalankan terlebih dahulu di Neon SQL Editor.
- Jangan publikasikan `.env`, URL koneksi, password PostgreSQL, atau kunci aplikasi di GitHub.

Sumber resmi: <https://vercel.com/docs/frameworks/backend/flask> dan <https://neon.com/docs/get-started-with-neon/connect-neon>.
