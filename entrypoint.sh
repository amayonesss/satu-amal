#!/bin/bash
set -e

echo "Membuat tabel database..."
python seed.py

echo "Menandai migrasi sebagai sudah dijalankan..."
flask db stamp head

echo "Memulai Gunicorn..."
exec gunicorn -w 4 -b 0.0.0.0:5001 "app:create_app()"
