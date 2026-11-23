-- OPSIONAL. Jalankan pada database tokokita_db setelah 01_schema.sql.
-- Tidak membuat akun: register melalui halaman /register agar password di-hash.
-- Tambahan produk/pelanggan demo. Tidak menduplikasi jika dijalankan lagi.
INSERT INTO products (sku, name, price, stock) VALUES
  ('BRG001', 'Buku Tulis', 15000, 20),
  ('BRG002', 'Pulpen Biru', 5000, 50),
  ('BRG003', 'Penggaris', 8000, 25)
ON CONFLICT DO NOTHING;

INSERT INTO customers (name, phone, email)
SELECT 'Andi', '081234567890', 'andi@example.test'
WHERE NOT EXISTS (SELECT 1 FROM customers WHERE email='andi@example.test');

INSERT INTO customers (name, phone, email)
SELECT 'Siti', '081298765432', 'siti@example.test'
WHERE NOT EXISTS (SELECT 1 FROM customers WHERE email='siti@example.test');
