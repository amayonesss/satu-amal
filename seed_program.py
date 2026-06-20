from datetime import date
from app import create_app, db
from app.models import Program

app = create_app()

program_list = [
    {
        "nama_program": "Sembako Berkah Ramadhan",
        "kategori": "Sosial",
        "bulan": "Maret",
        "tahun": 2026,
        "tanggal_pelaksanaan": date(2026, 3, 20),
        "lokasi": "Jakarta Pusat",
        "jumlah_relawan": 15,
        "jumlah_penerima_manfaat": 200,
        "nama_tempat": "Masjid Al-Ikhlas"
    },
    {
        "nama_program": "Buka Puasa Bersama Anak Yatim",
        "kategori": "Sosial",
        "bulan": "Maret",
        "tahun": 2026,
        "tanggal_pelaksanaan": date(2026, 3, 25),
        "lokasi": "Jakarta Timur",
        "jumlah_relawan": 10,
        "jumlah_penerima_manfaat": 120,
        "nama_tempat": "Panti Asuhan Harapan"
    },
    {
        "nama_program": "Santunan Anak Yatim",
        "kategori": "Sosial",
        "bulan": "April",
        "tahun": 2026,
        "tanggal_pelaksanaan": date(2026, 4, 10),
        "lokasi": "Jakarta Barat",
        "jumlah_relawan": 8,
        "jumlah_penerima_manfaat": 80,
        "nama_tempat": "Panti Asuhan Kasih Bunda"
    },
    {
        "nama_program": "Edukasi Lingkungan Hidup",
        "kategori": "Pendidikan",
        "bulan": "April",
        "tahun": 2026,
        "tanggal_pelaksanaan": date(2026, 4, 22),
        "lokasi": "Jakarta Selatan",
        "jumlah_relawan": 12,
        "jumlah_penerima_manfaat": 60,
        "nama_tempat": "SDN 01 Menteng"
    },
    {
        "nama_program": "Donor Darah & Cek Kesehatan",
        "kategori": "Kesehatan",
        "bulan": "Mei",
        "tahun": 2026,
        "tanggal_pelaksanaan": date(2026, 5, 15),
        "lokasi": "Jakarta Pusat",
        "jumlah_relawan": 20,
        "jumlah_penerima_manfaat": 150,
        "nama_tempat": "Puskesmas Gambir"
    },
]

with app.app_context():
    created = 0
    skipped = 0
    for p in program_list:
        existing = Program.query.filter_by(nama_program=p["nama_program"]).first()
        if not existing:
            program = Program(**p)
            db.session.add(program)
            created += 1
        else:
            skipped += 1

    db.session.commit()
    print(f"Program dibuat: {created}, Sudah ada: {skipped}")
    if created > 0:
        print("\nDaftar program:")
        for p in program_list:
            print(f"  - {p['nama_program']}")
