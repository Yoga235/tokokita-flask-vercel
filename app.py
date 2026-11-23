"""TokoKita Flask + PostgreSQL (lokal di pgAdmin 4 atau online di Vercel).

Buat tabel menggunakan sql/01_schema.sql. Di Vercel, isi DATABASE_URL dan SECRET_KEY.
"""
import csv
import io
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from flask import (Flask, Response, abort, flash, g, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
app = Flask(__name__, static_folder="public", static_url_path="")
ON_VERCEL = bool(os.getenv("VERCEL"))
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if ON_VERCEL and not DATABASE_URL:
    raise RuntimeError("DATABASE_URL wajib diisi dengan koneksi PostgreSQL online di Vercel.")
DB_INTEGRITY_ERROR = (psycopg.IntegrityError,)

# SECRET_KEY lokal disimpan dalam .env. Jangan commit .env ke Git.
key_file = ROOT / ".flask_secret"
if os.getenv("SECRET_KEY", "").strip() and os.getenv("SECRET_KEY") != "GANTI_DENGAN_KUNCI_ACAK":
    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
elif ON_VERCEL:
    raise RuntimeError("SECRET_KEY wajib diisi di Vercel Environment Variables.")
else:
    # Fallback hanya untuk praktik lokal; file ini tidak boleh dibuat di Vercel.
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32), encoding="utf-8")
        try:
            key_file.chmod(0o600)
        except OSError:
            pass
    app.config["SECRET_KEY"] = key_file.read_text(encoding="utf-8")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=ON_VERCEL)


class PostgresRow:
    """Mengizinkan row['name'] dan row[0] agar query agregasi ringkas."""
    def __init__(self, data):
        self.data = data

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.data.values())[key]
        return self.data[key]

    def __getattr__(self, key):
        # Jinja2 dapat mengakses row.name dan row.id.
        try:
            return self.data[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


class PostgresResult:
    def __init__(self, cursor):
        self.cursor = cursor
        self.rowcount = cursor.rowcount

    def fetchone(self):
        raw = self.cursor.fetchone()
        return PostgresRow(raw) if raw is not None else None

    def fetchall(self):
        return [PostgresRow(row) for row in self.cursor.fetchall()]


class PostgresDatabase:
    """Adapter sederhana untuk query SQL PostgreSQL dengan placeholder '?' di kode."""
    def __init__(self):
        # DATABASE_URL untuk Neon PostgreSQL online; parameter PG* untuk PostgreSQL lokal.
        # Setiap request Flask memegang koneksi sendiri, lalu ditutup di teardown.
        opts = dict(
            row_factory=dict_row,
            autocommit=True,  # Transaksi penjualan memakai BEGIN/COMMIT/ROLLBACK eksplisit.
            connect_timeout=10,
        )
        if DATABASE_URL:
            self.conn = psycopg.connect(DATABASE_URL, **opts)
        else:
            self.conn = psycopg.connect(
                host=os.getenv("PGHOST", "127.0.0.1"),
                port=os.getenv("PGPORT", "5432"),
                dbname=os.getenv("PGDATABASE", "tokokita_db"),
                user=os.getenv("PGUSER", "postgres"),
                password=os.getenv("PGPASSWORD", ""),
                **opts,
            )

    def execute(self, sql, params=()):
        # Semua SQL aplikasi ditulis sendiri: tanda ? hanya dipakai sebagai parameter.
        return PostgresResult(self.conn.execute(sql.replace("?", "%s"), params))

    def close(self):
        self.conn.close()


def database():
    if "db" not in g:
        g.db = PostgresDatabase()
    return g.db


@app.teardown_appcontext
def close_db(_error):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def now_wib():
    return datetime.now(timezone(timedelta(hours=7))).replace(tzinfo=None, microsecond=0)


@app.template_filter("idr")
def to_rupiah(number):
    return "Rp " + format(int(number or 0), ",").replace(",", ".")


@app.context_processor
def inject_defaults():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return {"csrf_token": session["csrf_token"], "current_user": session.get("username")}


@app.before_request
def verify_csrf():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        received = request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        if not expected or not secrets.compare_digest(received, expected):
            abort(400, "Token keamanan formulir tidak valid. Muat ulang halaman.")


def require_login(handler):
    @wraps(handler)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Silakan login terlebih dahulu.", "warning")
            return redirect(url_for("login"))
        return handler(*args, **kwargs)
    return wrapper


def valid_int(value, minimum=0):
    try:
        n = int(value)
        if str(n) != str(value).strip() or n < minimum or n > 9223372036854775807:
            return None
        return n
    except (ValueError, TypeError):
        return None


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not re.fullmatch(r"[A-Za-z0-9_.]{3,30}", username):
            flash("Username 3–30 karakter: huruf, angka, underscore, atau titik.", "danger")
        elif len(password) < 8:
            flash("Password minimal 8 karakter.", "danger")
        else:
            try:
                database().execute("INSERT INTO users(username,password_hash,created_at) VALUES (?,?,?)",
                                   (username, generate_password_hash(password), now_wib()))
                flash("Akun berhasil dibuat. Silakan login.", "success")
                return redirect(url_for("login"))
            except DB_INTEGRITY_ERROR:
                flash("Username sudah digunakan.", "danger")
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        row = database().execute("SELECT * FROM users WHERE LOWER(username)=LOWER(?)", (username,)).fetchone()
        if row and check_password_hash(row["password_hash"], request.form.get("password", "")):
            session.clear()
            session.update(user_id=row["id"], username=row["username"], csrf_token=secrets.token_urlsafe(32))
            flash("Berhasil login!", "success")
            return redirect(url_for("dashboard"))
        flash("Username atau password salah.", "danger")
    return render_template("auth.html", mode="login")


@app.post("/logout")
def logout():
    session.clear()
    flash("Anda telah logout.", "success")
    return redirect(url_for("login"))


@app.get("/")
@require_login
def dashboard():
    db = database()
    stats = {
        "products": db.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "customers": db.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
        "sales": db.execute("SELECT COUNT(*) FROM sales").fetchone()[0],
        "revenue": db.execute("SELECT COALESCE(SUM(total),0) FROM sales").fetchone()[0],
    }
    latest = db.execute("""SELECT s.*, c.name AS customer_name, p.name AS product_name
                           FROM sales s JOIN customers c ON c.id=s.customer_id
                           JOIN products p ON p.id=s.product_id
                           ORDER BY s.id DESC LIMIT 6""").fetchall()
    low_stock = db.execute("SELECT * FROM products WHERE stock<=5 ORDER BY stock,name LIMIT 6").fetchall()
    return render_template("dashboard.html", stats=stats, latest=latest, low_stock=low_stock)


@app.get("/products")
@require_login
def products():
    rows = database().execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    return render_template("products.html", rows=rows)


@app.route("/products/new", methods=["GET", "POST"])
@app.route("/products/<int:item_id>/edit", methods=["GET", "POST"])
@require_login
def product_form(item_id=None):
    db = database()
    row = db.execute("SELECT * FROM products WHERE id=?", (item_id,)).fetchone() if item_id else None
    if item_id and not row:
        abort(404)
    if request.method == "POST":
        sku = request.form.get("sku", "").strip()
        name = request.form.get("name", "").strip()
        price = valid_int(request.form.get("price"), 0)
        stock = valid_int(request.form.get("stock"), 0)
        if not sku or not name or len(sku) > 40 or len(name) > 100 or price is None or stock is None:
            flash("Kode maksimal 40 karakter, nama maksimal 100 karakter, harga dan stok harus angka tidak negatif.", "danger")
        else:
            try:
                if item_id:
                    db.execute("UPDATE products SET sku=?,name=?,price=?,stock=? WHERE id=?",
                               (sku, name, price, stock, item_id))
                else:
                    db.execute("INSERT INTO products(sku,name,price,stock) VALUES(?,?,?,?)",
                               (sku, name, price, stock))
                flash("Data barang berhasil disimpan.", "success")
                return redirect(url_for("products"))
            except DB_INTEGRITY_ERROR:
                flash("Kode barang sudah dipakai.", "danger")
    return render_template("product_form.html", row=row)


@app.post("/products/<int:item_id>/delete")
@require_login
def product_delete(item_id):
    try:
        cursor = database().execute("DELETE FROM products WHERE id=?", (item_id,))
        flash("Barang dihapus." if cursor.rowcount else "Barang tidak ditemukan.", "success" if cursor.rowcount else "warning")
    except DB_INTEGRITY_ERROR:
        flash("Barang sudah digunakan di transaksi dan tidak dapat dihapus.", "danger")
    return redirect(url_for("products"))


@app.get("/customers")
@require_login
def customers():
    rows = database().execute("SELECT * FROM customers ORDER BY id DESC").fetchall()
    return render_template("customers.html", rows=rows)


@app.route("/customers/new", methods=["GET", "POST"])
@app.route("/customers/<int:item_id>/edit", methods=["GET", "POST"])
@require_login
def customer_form(item_id=None):
    db = database()
    row = db.execute("SELECT * FROM customers WHERE id=?", (item_id,)).fetchone() if item_id else None
    if item_id and not row:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        if not name or len(name)>100 or len(phone)>40 or len(email)>150:
            flash("Nama wajib diisi dan panjang data harus sesuai.", "danger")
        else:
            if item_id:
                db.execute("UPDATE customers SET name=?,phone=?,email=? WHERE id=?", (name,phone,email,item_id))
            else:
                db.execute("INSERT INTO customers(name,phone,email) VALUES(?,?,?)", (name,phone,email))
            flash("Data pelanggan berhasil disimpan.", "success")
            return redirect(url_for("customers"))
    return render_template("customer_form.html", row=row)


@app.post("/customers/<int:item_id>/delete")
@require_login
def customer_delete(item_id):
    try:
        cursor = database().execute("DELETE FROM customers WHERE id=?", (item_id,))
        flash("Pelanggan dihapus." if cursor.rowcount else "Pelanggan tidak ditemukan.", "success" if cursor.rowcount else "warning")
    except DB_INTEGRITY_ERROR:
        flash("Pelanggan sudah memiliki transaksi dan tidak dapat dihapus.", "danger")
    return redirect(url_for("customers"))


@app.get("/sales")
@require_login
def sales():
    rows = database().execute("""SELECT s.*, p.name product_name,p.sku, c.name customer_name
                               FROM sales s JOIN products p ON p.id=s.product_id
                               JOIN customers c ON c.id=s.customer_id ORDER BY s.id DESC""").fetchall()
    return render_template("sales.html", rows=rows)


@app.route("/sales/new", methods=["GET", "POST"])
@app.route("/sales/<int:item_id>/edit", methods=["GET", "POST"])
@require_login
def sale_form(item_id=None):
    db = database()
    old = db.execute("SELECT * FROM sales WHERE id=?", (item_id,)).fetchone() if item_id else None
    if item_id and not old:
        abort(404)
    if request.method == "POST":
        product_id = valid_int(request.form.get("product_id"), 1)
        customer_id = valid_int(request.form.get("customer_id"), 1)
        quantity = valid_int(request.form.get("quantity"), 1)
        if None in (product_id, customer_id, quantity):
            flash("Pilih barang dan pelanggan, lalu masukkan jumlah minimal 1.", "danger")
        else:
            try:
                db.execute("BEGIN")
                if item_id:
                    lock_sql = "SELECT * FROM sales WHERE id=? FOR UPDATE"
                    old = db.execute(lock_sql, (item_id,)).fetchone()
                    if old is None:
                        raise ValueError("Transaksi tidak ditemukan.")
                product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
                customer = db.execute("SELECT id FROM customers WHERE id=?", (customer_id,)).fetchone()
                if not product or not customer:
                    raise ValueError("Barang atau pelanggan tidak ditemukan.")
                # Saat mengedit, kembalikan stok transaksi lama terlebih dulu.
                if old:
                    db.execute("UPDATE products SET stock=stock+? WHERE id=?", (old["quantity"],old["product_id"]))
                changed = db.execute("UPDATE products SET stock=stock-? WHERE id=? AND stock>=?",
                                     (quantity,product_id,quantity))
                if changed.rowcount == 0:
                    raise ValueError("Stok tidak mencukupi untuk transaksi ini.")
                total = quantity * product["price"]
                if total > 9223372036854775807:
                    raise ValueError("Total terlalu besar untuk disimpan.")
                if old:
                    db.execute("""UPDATE sales SET customer_id=?,product_id=?,quantity=?,unit_price=?,total=?
                                  WHERE id=?""", (customer_id, product_id, quantity, product["price"], total, item_id))
                else:
                    db.execute("""INSERT INTO sales(customer_id,product_id,quantity,unit_price,total,created_at,user_id)
                                  VALUES (?,?,?,?,?,?,?)""", (customer_id, product_id, quantity,
                                                                product["price"],total,now_wib(),session["user_id"]))
                db.execute("COMMIT")
                flash("Transaksi penjualan berhasil disimpan. Stok diperbarui.", "success")
                return redirect(url_for("sales"))
            except (ValueError, *DB_INTEGRITY_ERROR) as exc:
                db.execute("ROLLBACK")
                flash(str(exc) if isinstance(exc, ValueError) else "Transaksi gagal karena kendala data.", "danger")
            except Exception:
                db.execute("ROLLBACK")
                raise
    prods = db.execute("SELECT * FROM products ORDER BY name").fetchall()
    clients = db.execute("SELECT * FROM customers ORDER BY name").fetchall()
    return render_template("sale_form.html", row=old, products=prods, customers=clients)


@app.post("/sales/<int:item_id>/delete")
@require_login
def sale_delete(item_id):
    db = database()
    try:
        db.execute("BEGIN")
        lock_sql = "SELECT * FROM sales WHERE id=? FOR UPDATE"
        old = db.execute(lock_sql, (item_id,)).fetchone()
        if old:
            db.execute("UPDATE products SET stock=stock+? WHERE id=?", (old["quantity"], old["product_id"]))
            db.execute("DELETE FROM sales WHERE id=?", (item_id,))
        db.execute("COMMIT")
        flash("Transaksi dihapus; stok dikembalikan." if old else "Transaksi tidak ditemukan.",
              "success" if old else "warning")
    except Exception:
        db.execute("ROLLBACK")
        raise
    return redirect(url_for("sales"))


def report_data():
    first, last = request.args.get("start", "").strip(), request.args.get("end", "").strip()
    for date_str in (first, last):
        if date_str:
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                abort(400, "Format tanggal tidak valid.")
    if first and last and first > last:
        abort(400, "Tanggal awal tidak boleh sesudah tanggal akhir.")
    conditions, args = [], []
    if first:
        conditions.append("s.created_at::date >= ?::date")
        args.append(first)
    if last:
        conditions.append("s.created_at::date <= ?::date")
        args.append(last)
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    rows = database().execute("""SELECT s.id,s.created_at,c.name customer_name,p.sku,
                               p.name product_name,s.quantity,s.unit_price,s.total
                               FROM sales s JOIN customers c ON c.id=s.customer_id
                               JOIN products p ON p.id=s.product_id""" + where + " ORDER BY s.created_at DESC,s.id DESC", args).fetchall()
    return first, last, rows


@app.get("/reports")
@require_login
def reports():
    first, last, rows = report_data()
    total = sum(x["total"] for x in rows)
    total_qty = sum(x["quantity"] for x in rows)
    return render_template("reports.html", rows=rows, first=first, last=last,
                           total=total, total_qty=total_qty)


@app.get("/reports/export")
@require_login
def report_export():
    _first, _last, rows = report_data()
    output = io.StringIO()
    # BOM membantu Excel membaca CSV berbahasa Indonesia.
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["ID", "Tanggal WIB", "Pelanggan", "Kode Barang", "Barang", "Jumlah", "Harga Satuan", "Total"])
    for row in rows:
        writer.writerow([row[key] for key in ("id", "created_at", "customer_name", "sku", "product_name", "quantity", "unit_price", "total")])
    return Response(output.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=laporan_penjualan.csv"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=os.getenv("FLASK_DEBUG", "0") == "1")
