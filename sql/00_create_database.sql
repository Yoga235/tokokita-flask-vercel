-- Jalankan TERPISAH pada database bawaan "postgres" di pgAdmin 4.
-- Jika menggunakan Query Tool, aktifkan auto-commit dan jalankan hanya perintah ini.
-- Jika tokokita_db sudah ada, jangan jalankan ulang; lanjut ke 01_schema.sql.
CREATE DATABASE tokokita_db
    WITH ENCODING = 'UTF8';
