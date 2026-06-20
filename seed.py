"""
Script untuk inisialisasi database dan buat akun admin pertama.
Jalankan: python seed.py
"""
from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    # Buat semua tabel di database
    db.create_all()
    print("✅ Tabel database berhasil dibuat!")

    # Cek apakah admin sudah ada
    admin = User.query.filter_by(kode_relawan='ADMIN001').first()
    if not admin:
        admin = User(
            kode_relawan='ADMIN001',
            nama='Administrator',
            role='admin',
            aktif=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("✅ Akun admin berhasil dibuat!")
        print("   Kode  : ADMIN001")
        print("   Password: admin123")
        print("   ⚠️  Segera ganti password setelah login!")
    else:
        print("ℹ️  Akun admin sudah ada.")

    # Buat akun tim manajemen contoh
    tim = User.query.filter_by(kode_relawan='TIM001').first()
    if not tim:
        tim = User(
            kode_relawan='TIM001',
            nama='Tim Manajemen',
            role='tim_manajemen',
            aktif=True
        )
        tim.set_password('tim123')
        db.session.add(tim)
        db.session.commit()
        print("✅ Akun tim manajemen berhasil dibuat!")
        print("   Kode    : TIM001")
        print("   Password: tim123")
    else:
        print("ℹ️  Akun tim manajemen sudah ada.")

    print("\n🚀 Jalankan server: python run.py")