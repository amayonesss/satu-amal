from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.relawan import relawan_bp
from app.models import Presensi, Keaktifan, User, Notifikasi
from app import db
from datetime import date
from sqlalchemy import func
import base64
import json
import numpy as np
import cv2
import face_recognition

@relawan_bp.route('/')
@login_required
def index():
    if current_user.role == 'admin':
        return redirect(url_for('dashboard.index'))
    if current_user.role == 'tim_manajemen':
        return redirect(url_for('tim_manajemen.index'))

    from datetime import timedelta, datetime
    import json as _json

    today = date.today()

    # Presensi hari ini (ambil semua, multi-program)
    presensi_hari_ini = Presensi.query.filter_by(
        user_id=current_user.id, tanggal=today
    ).order_by(Presensi.jam_masuk).all()

    # Semua riwayat presensi (untuk tabel + chart)
    riwayat = Presensi.query.filter_by(
        user_id=current_user.id
    ).order_by(Presensi.tanggal.desc(), Presensi.jam_masuk.desc()).all()

    total_manhours = db.session.query(
        func.sum(Presensi.total_jam)
    ).filter_by(user_id=current_user.id).scalar() or 0

    total_kehadiran = db.session.query(
        func.count(Presensi.id)
    ).filter_by(user_id=current_user.id).scalar() or 0

    keaktifan = Keaktifan.query.filter_by(user_id=current_user.id).first()

    # ── 3 Pilar Evaluasi (Versi Relawan Pribadi) ──
    from app.models import Program
    
    # Ambil daftar unik program yang pernah dihadiri relawan ini
    program_diikuti = db.session.query(Program).join(
        Presensi, Presensi.nama_program == Program.nama_program
    ).filter(Presensi.user_id == current_user.id).distinct().all()
    
    total_pm = sum(p.jumlah_penerima_manfaat or 0 for p in program_diikuti)
    total_lokasi = len(set(p.kota for p in program_diikuti if p.kota))

    # ── Chart 1: Kontribusi Jam per Bulan (Lebih bermakna dari per minggu) ──
    bulan_labels = []
    jam_per_bulan = []
    for i in range(5, 0, -1):
        # Simplifikasi: ambil 5 bulan terakhir
        target_month = today.month - i + 1
        target_year = today.year
        if target_month <= 0:
            target_month += 12
            target_year -= 1
            
        jam = db.session.query(func.sum(Presensi.total_jam)).filter(
            Presensi.user_id == current_user.id,
            func.extract('month', Presensi.tanggal) == target_month,
            func.extract('year', Presensi.tanggal) == target_year
        ).scalar() or 0
        
        nama_bulan = ["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agu","Sep","Okt","Nov","Des"][target_month-1]
        bulan_labels.append(f'{nama_bulan} {target_year}')
        jam_per_bulan.append(round(float(jam), 2))

    # ── Chart 2: Kehadiran per Program ──
    program_counts = db.session.query(
        Presensi.nama_program, func.count(Presensi.id)
    ).filter(
        Presensi.user_id == current_user.id,
        Presensi.nama_program != None
    ).group_by(Presensi.nama_program).all()

    cat_labels = [p[0][:20] + '...' if len(p[0]) > 20 else p[0] for p in program_counts]
    cat_data   = [p[1] for p in program_counts]

    # ── Chart 3: Distribusi Lokasi Kegiatan ──
    lokasi_counts = db.session.query(
        Program.kota, func.count(func.distinct(Presensi.tanggal))
    ).join(
        Presensi, Presensi.nama_program == Program.nama_program
    ).filter(
        Presensi.user_id == current_user.id,
        Program.kota != None, Program.kota != ''
    ).group_by(Program.kota).all()
    
    loc_labels = [l[0] for l in lokasi_counts]
    loc_data = [l[1] for l in lokasi_counts]

    return render_template('relawan/index.html',
        presensi=presensi_hari_ini[0] if presensi_hari_ini else None,
        presensi_list=presensi_hari_ini,
        riwayat=riwayat,
        total_manhours=round(float(total_manhours), 2),
        total_kehadiran=total_kehadiran,
        total_pm=total_pm,
        total_lokasi=total_lokasi,
        keaktifan=keaktifan,
        bulan_labels=_json.dumps(bulan_labels),
        jam_per_bulan=_json.dumps(jam_per_bulan),
        cat_labels=_json.dumps(cat_labels),
        cat_data=_json.dumps(cat_data),
        loc_labels=_json.dumps(loc_labels),
        loc_data=_json.dumps(loc_data),
    )


@relawan_bp.route('/profil', methods=['GET', 'POST'])
@login_required
def profil():
    if request.method == 'POST':
        aksi = request.form.get('aksi')

        # --- Ganti Password ---
        if aksi == 'ganti_password':
            password_lama = request.form.get('password_lama')
            password_baru = request.form.get('password_baru')
            konfirmasi    = request.form.get('konfirmasi_password')

            if not current_user.check_password(password_lama):
                flash('Password lama salah.', 'danger')
            elif password_baru != konfirmasi:
                flash('Password baru dan konfirmasi tidak sama.', 'danger')
            elif len(password_baru) < 6:
                flash('Password minimal 6 karakter.', 'danger')
            else:
                current_user.set_password(password_baru)
                db.session.commit()
                flash('Password berhasil diubah!', 'success')

        elif aksi == 'update_kode':
            kode_baru = request.form.get('kode_relawan', '').strip()
            if not kode_baru:
                flash('Kode relawan tidak boleh kosong.', 'danger')
            elif User.query.filter(
                User.kode_relawan == kode_baru,
                User.id != current_user.id
            ).first():
                flash('Kode relawan sudah digunakan orang lain.', 'danger')
            else:
                current_user.kode_relawan = kode_baru
                db.session.commit()
                flash('Kode relawan berhasil diperbarui!', 'success')

        return redirect(url_for('relawan.profil'))

    return render_template('relawan/profil.html')

@relawan_bp.route('/tugas-evaluasi')
@login_required
def tugas_evaluasi():
    from app.models import KoordinatorProgram, EvaluasiProgram
    
    # Ambil program di mana user ini menjadi koordinator
    koordinator_tugas = KoordinatorProgram.query.filter_by(user_id=current_user.id).all()
    
    # Bikin dictionary untuk cek program mana yang sudah dievaluasi
    # by this user (atau secara general by anyone in this program, tp biasanya by this user)
    evaluasi_selesai = {e.program_id: e for e in EvaluasiProgram.query.filter_by(admin_id=current_user.id).all()}
    
    return render_template('relawan/tugas_evaluasi.html', 
                           tugas_list=koordinator_tugas, 
                           evaluasi_selesai=evaluasi_selesai)

@relawan_bp.route('/tugas-evaluasi/<int:program_id>/isi', methods=['GET', 'POST'])
@login_required
def isi_evaluasi(program_id):
    from app.models import KoordinatorProgram, EvaluasiProgram, Program

    cek_koordinator = KoordinatorProgram.query.filter_by(program_id=program_id, user_id=current_user.id).first()
    if not cek_koordinator:
        flash('Anda tidak memiliki akses evaluasi untuk program ini.', 'danger')
        return redirect(url_for('relawan.tugas_evaluasi'))

    program = Program.query.get_or_404(program_id)
    evaluasi_lama = EvaluasiProgram.query.filter_by(program_id=program.id, admin_id=current_user.id).first()

    if request.method == 'POST':
        jml_pm  = request.form.get('jumlah_pm_aktual', 0)
        catatan = request.form.get('catatan_keberhasilan', '').strip()
        kendala = request.form.get('kendala_lapangan', '').strip()

        if evaluasi_lama:
            evaluasi_lama.jumlah_pm_aktual     = int(jml_pm) if jml_pm else 0
            evaluasi_lama.catatan_keberhasilan = catatan
            evaluasi_lama.kendala_lapangan     = kendala
            flash('Evaluasi program berhasil diperbarui.', 'success')
            aksi_label = 'diperbarui'
        else:
            baru = EvaluasiProgram(
                program_id=program.id,
                admin_id=current_user.id,
                jumlah_pm_aktual=int(jml_pm) if jml_pm else 0,
                catatan_keberhasilan=catatan,
                kendala_lapangan=kendala
            )
            db.session.add(baru)
            flash('Evaluasi program berhasil disubmit. Terima kasih!', 'success')
            aksi_label = 'disubmit'

        db.session.commit()

        from sqlalchemy import func
        total_aktual = db.session.query(func.sum(EvaluasiProgram.jumlah_pm_aktual))\
            .filter(EvaluasiProgram.program_id == program.id).scalar() or 0
        program.jumlah_penerima_manfaat = total_aktual
        db.session.commit()

        admins = User.query.filter_by(role='admin').all()
        for admin in admins:
            notif = Notifikasi(
                user_id=admin.id,
                pesan=f"📋 Feedback evaluasi program \"{program.nama_program}\" telah {aksi_label} oleh PIC: {current_user.nama}."
            )
            db.session.add(notif)
        db.session.commit()

        return redirect(url_for('relawan.tugas_evaluasi'))

    return render_template('relawan/form_evaluasi.html',
                           program=program,
                           evaluasi=evaluasi_lama)