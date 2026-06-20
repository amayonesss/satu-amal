"""Seed dummy data untuk dashboard: relawan, presensi, keaktifan, dll."""
import sys, os, random
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from app import create_app, db
from app.models import User, Program, Presensi, Keaktifan, Notifikasi, KoordinatorProgram, EvaluasiProgram, FotoKegiatan

app = create_app()

BULAN_MAP = {
    1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April', 5: 'Mei', 6: 'Juni',
    7: 'Juli', 8: 'Agustus', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
}

NAMA_RELAWAN = [
    "Ahmad Fauzi", "Siti Nurhaliza", "Budi Santoso", "Dewi Lestari", "Rudi Hartono",
    "Fitri Handayani", "Hendra Gunawan", "Indah Permata Sari", "Joko Susilo", "Kartika Dewi",
    "Lukman Hakim", "Maya Anggraini", "Nanda Pratama", "Olivia Rahmawati", "Putra Wijaya",
    "Ratna Sari Dewi", "Sandy Firmansyah", "Tia Kusuma Wardhani", "Ujang Hermawan", "Vera Yuliana",
    "Wahyu Nugroho", "Rina Marlina", "Doni Setiawan", "Eva Susanti", "Fajar Sidik"
]

KODE_ADMIN = 'ADMIN001'

def seed():
    with app.app_context():
        admin = User.query.filter_by(kode_relawan=KODE_ADMIN).first()
        if not admin:
            print('ADMIN001 tidak ditemukan!')
            return

        # ── 1. Tambah relawan baru (jika belum ada) ──
        existing = {u.nama for u in User.query.filter_by(role='relawan').all()}
        baru_count = 0
        for nama in NAMA_RELAWAN:
            if nama in existing:
                continue
            kode = f'REL{random.randint(10000, 99999)}'
            while User.query.filter_by(kode_relawan=kode).first():
                kode = f'REL{random.randint(10000, 99999)}'
            u = User(kode_relawan=kode, nama=nama, role='relawan', aktif=True, email=f'{nama.lower().replace(" ", ".")}@email.com')
            u.set_password('123456')
            db.session.add(u)
            existing.add(nama)
            baru_count += 1
        db.session.commit()
        print(f'Relawan baru: {baru_count}')

        # ── 2. Ambil semua relawan & program ──
        semua_relawan = User.query.filter_by(role='relawan', aktif=True).all()
        semua_program = Program.query.all()
        print(f'Total relawan: {len(semua_relawan)}, Total program: {len(semua_program)}')

        if not semua_program:
            print('Tidak ada program!')
            return

        # ── 3. Hapus presensi/keaktifan lama lalu buat baru ──
        FotoKegiatan.query.delete()
        Presensi.query.delete()
        Keaktifan.query.delete()
        Notifikasi.query.delete()
        KoordinatorProgram.query.delete()
        EvaluasiProgram.query.delete()
        db.session.commit()
        print('Data lama dihapus.')

        # ── 4. Buat presensi untuk setiap relawan ──
        now = datetime.now()
        presensi_count = 0
        # Set active level per relawan
        for idx, relawan in enumerate(semua_relawan):
            # Semakin depan daftar, semakin aktif
            active_level = max(0.3, 1.0 - (idx / len(semua_relawan)) * 0.7)
            base_hours = random.uniform(2, 6)

            # Pilih program yang pernah diikuti relawan ini
            n_programs = max(1, int(len(semua_program) * active_level * 0.05))
            program_diikuti = random.sample(semua_program, min(n_programs, len(semua_program)))

            total_hadir = 0
            total_jam = 0.0

            for prog in program_diikuti:
                # Beberapa kali hadir di program yang sama
                n_hadir = max(0, int(random.gauss(active_level * 4, 1.5)))
                for _ in range(n_hadir):
                    # Tentukan tanggal dalam rentang program
                    if prog.tanggal_pelaksanaan:
                        base_date = prog.tanggal_pelaksanaan
                    elif prog.bulan and prog.tahun:
                        bulan_num = list(BULAN_MAP.keys())[list(BULAN_MAP.values()).index(prog.bulan)] if prog.bulan in BULAN_MAP.values() else None
                        if bulan_num:
                            base_date = date(prog.tahun, bulan_num, 15)
                        else:
                            base_date = date(prog.tahun or 2026, 6, 1)
                    else:
                        base_date = date(2026, 6, 1)

                    # Variasi tanggal
                    tgl = base_date + timedelta(days=random.randint(-7, 7))
                    if tgl > date.today():
                        tgl = date.today() - timedelta(days=random.randint(1, 30))

                    jam_masuk = datetime(tgl.year, tgl.month, tgl.day, random.randint(7, 9), random.randint(0, 59))
                    lama = base_hours + random.uniform(-1, 2)
                    jam_keluar = jam_masuk + timedelta(hours=lama)

                    presensi = Presensi(
                        user_id=relawan.id,
                        program_id=prog.id,
                        nama_program=prog.nama_program,
                        tanggal=tgl,
                        jam_masuk=jam_masuk,
                        jam_keluar=jam_keluar,
                        total_jam=round(lama, 2),
                        metode='face' if random.random() > 0.3 else 'manual',
                        status='hadir',
                    )
                    db.session.add(presensi)
                    total_hadir += 1
                    total_jam += lama
                    presensi_count += 1

            # Keaktifan
            keaktifan = Keaktifan(user_id=relawan.id, jumlah_kehadiran=total_hadir, total_manhours=round(total_jam, 2))
            db.session.add(keaktifan)

        db.session.commit()
        print(f'Presensi dibuat: {presensi_count}')

        # ── 5. Notifikasi untuk beberapa relawan ──
        for relawan in random.sample(semua_relawan, min(5, len(semua_relawan))):
            notif = Notifikasi(
                user_id=relawan.id,
                pesan=f"Selamat! Presensi Anda telah disetujui untuk kegiatan terbaru.",
                is_read=random.random() > 0.5
            )
            db.session.add(notif)
        db.session.commit()
        print(f'Notifikasi: 5')

        # ── 6. Koordinator program ──
        koor_count = 0
        for prog in random.sample(semua_program, min(30, len(semua_program))):
            rel = random.choice(semua_relawan)
            if not KoordinatorProgram.query.filter_by(program_id=prog.id, user_id=rel.id).first():
                koor = KoordinatorProgram(program_id=prog.id, user_id=rel.id, ditunjuk_oleh=admin.id)
                db.session.add(koor)
                koor_count += 1
        db.session.commit()
        print(f'Koordinator: {koor_count}')

        # ── 7. Evaluasi program ──
        eval_count = 0
        for prog in random.sample(semua_program, min(50, len(semua_program))):
            if prog.jumlah_penerima_manfaat > 0:
                keberhasilan = [
                    f"Program berjalan lancar dengan partisipasi {prog.jumlah_relawan} relawan.",
                    "Masyarakat sangat antusias mengikuti kegiatan.",
                    "Tepat sasaran dan sesuai jadwal.",
                    "Kerjasama dengan pihak kelurahan sangat baik.",
                    "Seluruh penerima manfaat merasa terbantu.",
                ]
                kendala = [
                    "Cuaca kurang mendukung saat pelaksanaan.",
                    "Beberapa relawan datang terlambat.",
                    "Keterbatasan transportasi di lokasi.",
                    "Koordinasi dengan pihak setempat perlu ditingkatkan.",
                    "Ketersediaan logistik terbatas.",
                    "",
                    "",
                ]
                eval_prog = EvaluasiProgram(
                    program_id=prog.id,
                    admin_id=admin.id,
                    jumlah_pm_aktual=prog.jumlah_penerima_manfaat + random.randint(-5, 10),
                    catatan_keberhasilan=random.choice(keberhasilan),
                    kendala_lapangan=random.choice(kendala),
                )
                db.session.add(eval_prog)
                eval_count += 1
        db.session.commit()
        print(f'Evaluasi: {eval_count}')

        print('\nSeed selesai! Data dashboard siap.')

if __name__ == '__main__':
    seed()
