# Satu Amal - Project Guide

## Overview
Aplikasi manajemen relawan (volunteer management) berbasis Flask untuk organisasi Satu Amal Indonesia. Fitur utama: CRUD relawan/program, presensi dengan face recognition + anti-spoofing liveness detection, evaluasi program, dan pelaporan Excel/PDF.

## Tech Stack
- **Runtime:** Python 3.12+
- **Framework:** Flask (App Factory pattern + Blueprints)
- **ORM:** Flask-SQLAlchemy + MySQL (pymysql)
- **Migrations:** Flask-Migrate (Alembic)
- **Auth:** Flask-Login + Werkzeug hashing
- **Templating:** Jinja2 (all `*.html`)
- **Face Recognition:** `face-recognition` (dlib) + OpenCV
- **Liveness:** LBP/DCT/entropy anti-spoofing (`app/liveness.py`)
- **Data:** Pandas + openpyxl (Excel import/export)
- **Frontend:** Vanilla HTML/CSS/JS, Font Awesome, inline styles (no CSS framework)

## Directory Structure
```
satu-amal/
├── run.py                    # Entry point: python run.py
├── seed.py                   # Seeder: creates tables + default users
├── config.py                 # Flask config (DB, email, uploads)
├── requirements.txt
├── .env
├── update_colors.py          # Bulk-update hex colors in templates
├── get_color.py              # Extract hex color from image
├── app/
│   ├── __init__.py           # create_app(), blueprint registration
│   ├── models.py             # SQLAlchemy models
│   ├── decorators.py         # @role_required, @crud_required
│   ├── liveness.py           # Anti-spoofing detection
│   ├── report_utils.py       # Excel report generation
│   ├── auth/                 # Login, register, forgot/reset password
│   ├── dashboard/            # Admin dashboard (CRUD relawan, program, evaluasi)
│   ├── presensi/             # Face scan, register face, liveness check
│   ├── relawan/              # Volunteer self-service dashboard
│   ├── tim_manajemen/        # Management team views
│   └── master/               # Master data listings
├── templates/                # Jinja2 templates
│   ├── base_admin.html       # Base layout with sidebar
│   ├── auth/                 # Login, register, forgot/reset password
│   ├── dashboard/            # 13 admin templates
│   ├── presensi/             # Face scan page
│   ├── relawan/              # 4 volunteer templates
│   └── tim_manajemen/        # 2 management templates
├── static/
│   ├── img/logo.png
│   └── css/ (empty), js/ (empty)
├── uploads/faces/            # Face photo uploads
└── migrations/versions/      # 7 migration files
```

## Database Models
- **User** (`users`): kode_relawan, nama, email, password_hash, role (admin/tim_manajemen/relawan), foto_wajah, face_encoding (JSON), aktif
- **TimAkses** (`tim_akses`): user_id, akses_crud, diberikan_oleh
- **Program** (`program`): nama_program, kategori, bulan, tahun, tanggal_pelaksanaan, lokasi, jumlah_relawan, jumlah_penerima_manfaat, nama_tempat
- **Presensi** (`presensi`): user_id, program_id, tanggal, jam_masuk, jam_keluar, total_jam, metode (face/manual), status (pending/hadir/ditolak), foto_presensi
- **Keaktifan** (`keaktifan`): user_id, jumlah_kehadiran, total_manhours
- **Notifikasi** (`notifikasi`): user_id, pesan, is_read
- **KoordinatorProgram** (`koordinator_program`): program_id, user_id, ditunjuk_oleh
- **EvaluasiProgram** (`evaluasi_program`): program_id, admin_id, jumlah_pm_aktual, catatan_keberhasilan, kendala_lapangan

## Key Commands
| Command | Purpose |
|---|---|
| `python run.py` | Start dev server on `0.0.0.0:5000` (debug + ad-hoc SSL) |
| `python seed.py` | Create tables + default users (ADMIN001/admin123, TIM001/tim123) |
| `flask db upgrade` | Apply migrations |
| `flask db migrate -m "msg"` | Create migration |
| `python update_colors.py` | Replace hex colors in templates |

## Authentication & Roles
- **3 roles:** `admin`, `tim_manajemen`, `relawan`
- Login via kode_relawan or email + password
- Self-registration disabled (redirects to "hubungi admin")
- `@role_required('admin', 'tim_manajemen')` — restricts to admin/TM
- `@crud_required` — allows admin or TM with `TimAkses.akses_crud = True`

## Code Conventions
- **Bahasa Indonesia** for all code (comments, variables, UI text, docstrings)
- Flask Blueprints with fat route handlers (no service layer)
- Jinja2 templates with inline `<style>` tags (no external CSS)
- Color scheme: primary `#1f59d2`, accent `#f5a623`, font Segoe UI
- Mixed naming: snake_case for DB columns, camelCase in some JS
- No tests, no linter, no formatter configured
- All templates extend `base_admin.html` which has the sidebar layout

## Face Recognition
- Register: capture webcam -> `face_recognition.face_encodings()` -> store 128-d vector JSON
- Scan: compare encoding with tolerance 0.42 -> record check-in/check-out
- Liveness: composite score (LBP 45%, variance 30%, DCT 25%) + blink detection
- Presensi starts as `pending`, must be approved by admin/TM
