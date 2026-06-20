from app import create_app, db
from app.models import User, Keaktifan

app = create_app()

relawan_list = [
    {"kode": "RWL001", "nama": "Ahmad Fauzi", "email": "ahmad@example.com"},
    {"kode": "RWL002", "nama": "Siti Nurhaliza", "email": "siti@example.com"},
    {"kode": "RWL003", "nama": "Budi Santoso", "email": "budi@example.com"},
    {"kode": "RWL004", "nama": "Dewi Lestari", "email": "dewi@example.com"},
    {"kode": "RWL005", "nama": "Rudi Hartono", "email": "rudi@example.com"},
]

with app.app_context():
    created = 0
    skipped = 0
    for r in relawan_list:
        existing = User.query.filter_by(kode_relawan=r["kode"]).first()
        if not existing:
            user = User(
                kode_relawan=r["kode"],
                nama=r["nama"],
                email=r["email"],
                role="relawan",
                aktif=True
            )
            user.set_password("relawan123")
            db.session.add(user)
            db.session.flush()

            keaktifan = Keaktifan(user_id=user.id, jumlah_kehadiran=0, total_manhours=0.0)
            db.session.add(keaktifan)
            created += 1
        else:
            skipped += 1

    db.session.commit()
    print(f"Dibuat: {created}, Sudah ada: {skipped}")
    if created > 0:
        print("\nAkun relawan (password: relawan123):")
        for r in relawan_list:
            print(f"  {r['kode']} - {r['nama']}")
