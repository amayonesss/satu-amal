from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.dashboard import dashboard_bp
from app.models import User, Keaktifan, Program, Presensi, Notifikasi
from app import db
from app.decorators import crud_required, role_required
from types import SimpleNamespace
from sqlalchemy import func
import pandas as pd
from datetime import date, datetime, timedelta
import io

BULAN_NAMES = ['Januari','Februari','Maret','April','Mei','Juni',
               'Juli','Agustus','September','Oktober','November','Desember']

@dashboard_bp.route('/')
@login_required
@role_required('admin', 'tim_manajemen')
def index():
    # Ambil filter dari request.args
    is_filtered = ('bulan' in request.args or 'tahun' in request.args)
    now = datetime.now()
    
    if not is_filtered:
        # Default load: bulan & tahun berjalan
        bulan_filter = BULAN_NAMES[now.month - 1]
        tahun_filter = now.year
    else:
        bulan_filter = request.args.get('bulan', '').strip()
        tahun_filter_str = request.args.get('tahun', '').strip()
        tahun_filter = int(tahun_filter_str) if (tahun_filter_str and tahun_filter_str.isdigit()) else None

    # Tentukan label periode & perbandingan target vs realisasi
    bulan_ini = bulan_filter if bulan_filter else "Semua Bulan"
    tahun_ini = tahun_filter if tahun_filter else "Semua Tahun"
    
    if bulan_filter:
        bln_ini_idx = BULAN_NAMES.index(bulan_filter)
        bln_lalu_idx = bln_ini_idx - 1
        tahun_lalu = tahun_ini
        if bln_lalu_idx < 0:
            bln_lalu_idx = 11
            if isinstance(tahun_lalu, int):
                tahun_lalu -= 1
        bulan_lalu = BULAN_NAMES[bln_lalu_idx]
    else:
        bulan_lalu = "Tahun Lalu"
        tahun_lalu = (tahun_filter - 1) if tahun_filter else (now.year - 1)

    # Query daftar tahun unik yang tersedia
    available_years_raw = db.session.query(func.distinct(Program.tahun)).filter(Program.tahun != None).all()
    available_years = sorted([r[0] for r in available_years_raw], reverse=True)
    if now.year not in available_years:
        available_years.insert(0, now.year)

    # ── STAT DASAR ──
    total_relawan     = User.query.filter_by(role='relawan', aktif=True).count()
    hadir_hari_ini    = Presensi.query.filter_by(tanggal=date.today()).count()
    
    manhours_query = db.session.query(func.sum(Presensi.total_jam)).filter(Presensi.status == 'hadir')
    if bulan_filter or tahun_filter:
        manhours_query = manhours_query.join(Program, Presensi.program_id == Program.id)
        if bulan_filter:
            manhours_query = manhours_query.filter(Program.bulan == bulan_filter)
        if tahun_filter:
            manhours_query = manhours_query.filter(Program.tahun == tahun_filter)
    total_manhours    = manhours_query.scalar() or 0
    
    pending_users_count = User.query.filter_by(role='relawan', aktif=False).count()
    semua_program     = Program.query.all()

    # ── 1. RINGKASAN DAMPAK ──
    pm_query = db.session.query(func.sum(Program.jumlah_penerima_manfaat))
    if bulan_filter:
        pm_query = pm_query.filter(Program.bulan == bulan_filter)
    if tahun_filter:
        pm_query = pm_query.filter(Program.tahun == tahun_filter)
    pm_bulan_ini = int(pm_query.scalar() or 0)

    prog_bulan_query = Program.query
    if bulan_filter:
        prog_bulan_query = prog_bulan_query.filter(Program.bulan == bulan_filter)
    if tahun_filter:
        prog_bulan_query = prog_bulan_query.filter(Program.tahun == tahun_filter)
    program_bulan_ini = prog_bulan_query.count()

    lokasi_bulan_query = db.session.query(func.count(func.distinct(Program.kota)))\
        .filter(Program.kota != None, Program.kota != '')
    if bulan_filter:
        lokasi_bulan_query = lokasi_bulan_query.filter(Program.bulan == bulan_filter)
    if tahun_filter:
        lokasi_bulan_query = lokasi_bulan_query.filter(Program.tahun == tahun_filter)
    lokasi_bulan_ini  = lokasi_bulan_query.scalar() or 0
    
    # Total keseluruhan
    total_penerima = int(db.session.query(func.sum(Program.jumlah_penerima_manfaat)).scalar() or 0)
    total_lokasi   = db.session.query(func.count(func.distinct(Program.kota)))\
        .filter(Program.kota != None, Program.kota != '').scalar() or 0

    # ── 2. SEBARAN WILAYAH ──
    sebaran_query = db.session.query(
        Program.kota,
        func.count(Program.id).label('jumlah_program'),
        func.sum(Program.jumlah_penerima_manfaat).label('total_pm')
    ).filter(Program.kota != None, Program.kota != '')
    if bulan_filter:
        sebaran_query = sebaran_query.filter(Program.bulan == bulan_filter)
    if tahun_filter:
        sebaran_query = sebaran_query.filter(Program.tahun == tahun_filter)
    sebaran_raw = sebaran_query.group_by(Program.kota)\
      .order_by(func.sum(Program.jumlah_penerima_manfaat).desc()).limit(10).all()
      
    sebaran_labels = [r.kota for r in sebaran_raw]
    sebaran_pm     = [int(r.total_pm or 0) for r in sebaran_raw]
    sebaran_prog   = [int(r.jumlah_program or 0) for r in sebaran_raw]

    # ── 3. TARGET VS REALISASI (Bulan Ini vs Bulan Lalu per Kategori) ──
    def pm_per_kat(bulan, tahun):
        rows = db.session.query(
            Program.kategori,
            func.sum(Program.jumlah_penerima_manfaat).label('pm')
        ).filter(Program.kategori != None, Program.kategori != '')
        if bulan:
            rows = rows.filter(Program.bulan == bulan)
        if tahun:
            rows = rows.filter(Program.tahun == tahun)
        rows = rows.group_by(Program.kategori).all()
        return {r.kategori: int(r.pm or 0) for r in rows}

    kat_ini  = pm_per_kat(bulan_filter,  tahun_filter)
    kat_lalu = pm_per_kat(bulan_filter if bulan_filter else None, tahun_lalu)
    semua_kat = sorted(set(list(kat_ini.keys()) + list(kat_lalu.keys())))
    target_labels   = semua_kat
    target_realisasi = [kat_ini.get(k, 0)  for k in semua_kat]
    target_bulan_lalu= [kat_lalu.get(k, 0) for k in semua_kat]

    # ── 4. BREAKDOWN KATEGORI PROGRAM ──
    kat_all_query = db.session.query(
        Program.kategori,
        func.count(Program.id).label('jumlah_program'),
        func.sum(Program.jumlah_penerima_manfaat).label('total_pm')
    ).filter(Program.kategori != None, Program.kategori != '')
    if bulan_filter:
        kat_all_query = kat_all_query.filter(Program.bulan == bulan_filter)
    if tahun_filter:
        kat_all_query = kat_all_query.filter(Program.tahun == tahun_filter)
    kat_all_raw = kat_all_query.group_by(Program.kategori)\
      .order_by(func.sum(Program.jumlah_penerima_manfaat).desc()).all()
      
    kat_all_labels = [r.kategori for r in kat_all_raw]
    kat_all_pm     = [int(r.total_pm or 0) for r in kat_all_raw]
    kat_all_prog   = [int(r.jumlah_program or 0) for r in kat_all_raw]
    total_prog_all = sum(kat_all_prog) or 1
    kat_all_pct    = [round(v / total_prog_all * 100, 1) for v in kat_all_prog]

    # ── 5. AKTIVITAS TERBARU ──
    act_query = Program.query
    if bulan_filter:
        act_query = act_query.filter_by(bulan=bulan_filter)
    if tahun_filter:
        act_query = act_query.filter_by(tahun=tahun_filter)
    aktivitas_terbaru = act_query.order_by(Program.id.desc()).limit(10).all()

    # ── 6. ALERTS ──
    cutoff_absen = date.today() - timedelta(days=30)
    subq_last = db.session.query(
        Presensi.user_id,
        func.max(Presensi.tanggal).label('last_date')
    ).group_by(Presensi.user_id).subquery()

    relawan_absen_lama = db.session.query(User).outerjoin(
        subq_last, User.id == subq_last.c.user_id
    ).filter(
        User.role == 'relawan', User.aktif == True,
        db.or_(subq_last.c.last_date < cutoff_absen, subq_last.c.last_date == None)
    ).all()

    program_tanpa_lokasi = Program.query.filter(
        db.or_(Program.kota == None, Program.kota == '')).count()
    pending_presensi_count = Presensi.query.filter_by(status='pending').count()

    # ── TOP RELAWAN ──
    top_relawan_query = db.session.query(
        User,
        func.count(Presensi.id).label('jumlah_kehadiran'),
        func.sum(Presensi.total_jam).label('total_manhours')
    ).join(Presensi, User.id == Presensi.user_id)\
     .filter(User.role == 'relawan', Presensi.status == 'hadir')
     
    if bulan_filter or tahun_filter:
        top_relawan_query = top_relawan_query.join(Program, Presensi.program_id == Program.id)
        if bulan_filter:
            top_relawan_query = top_relawan_query.filter(Program.bulan == bulan_filter)
        if tahun_filter:
            top_relawan_query = top_relawan_query.filter(Program.tahun == tahun_filter)
            
    top_relawan_raw = top_relawan_query.group_by(User.id)\
     .order_by(func.count(Presensi.id).desc()).limit(5).all()
     
    top_relawan = []
    for row in top_relawan_raw:
        user = row[0]
        prog_raw = db.session.query(
            Presensi.nama_program, func.count(Presensi.id)
        ).filter(Presensi.user_id == user.id, Presensi.status == 'hadir')\
         .group_by(Presensi.nama_program)\
         .order_by(func.count(Presensi.id).desc()).first()
        prog_name = prog_raw[0] if (prog_raw and prog_raw[0]) else '-'
        top_relawan.append((user, SimpleNamespace(
            jumlah_kehadiran=row[1],
            total_manhours=round(row[2] or 0, 2),
            program_utama=prog_name
        )))

    # ── TREN PM PER BULAN (chart) ──
    tren_raw = db.session.query(
        Program.bulan, Program.tahun,
        func.sum(Program.jumlah_penerima_manfaat).label('total_pm'),
        func.count(Program.id).label('jumlah_program')
    ).filter(Program.bulan != None, Program.bulan != '')\
     .group_by(Program.tahun, Program.bulan).all()
    tren_sorted = sorted(
        tren_raw,
        key=lambda x: (x.tahun or 0, BULAN_NAMES.index(x.bulan) if x.bulan in BULAN_NAMES else 99)
    )
    tren_labels = [f"{r.bulan[:3]} {r.tahun or ''}" for r in tren_sorted]
    tren_pm     = [int(r.total_pm or 0)        for r in tren_sorted]
    tren_prog   = [int(r.jumlah_program or 0)  for r in tren_sorted]

    return render_template('dashboard/index.html',
        # Stat dasar
        total_relawan=total_relawan,
        hadir_hari_ini=hadir_hari_ini,
        total_manhours=round(total_manhours, 2),
        pending_users_count=pending_users_count,
        semua_program=semua_program,
        total_penerima=total_penerima,
        total_lokasi=total_lokasi,
        # 1. Ringkasan bulan ini
        bulan_ini=bulan_ini,
        tahun_ini=tahun_ini,
        pm_bulan_ini=pm_bulan_ini,
        program_bulan_ini=program_bulan_ini,
        lokasi_bulan_ini=lokasi_bulan_ini,
        # 2. Sebaran wilayah
        sebaran_labels=sebaran_labels,
        sebaran_pm=sebaran_pm,
        sebaran_prog=sebaran_prog,
        # 3. Target vs realisasi
        bulan_lalu=bulan_lalu,
        target_labels=target_labels,
        target_realisasi=target_realisasi,
        target_bulan_lalu=target_bulan_lalu,
        # 4. Breakdown kategori
        kat_all_labels=kat_all_labels,
        kat_all_pm=kat_all_pm,
        kat_all_prog=kat_all_prog,
        kat_all_pct=kat_all_pct,
        # 5. Aktivitas terbaru
        aktivitas_terbaru=aktivitas_terbaru,
        # 6. Alerts
        relawan_absen_lama=relawan_absen_lama,
        program_tanpa_lokasi=program_tanpa_lokasi,
        pending_presensi_count=pending_presensi_count,
        # Top relawan & tren
        top_relawan=top_relawan,
        tren_labels=tren_labels,
        tren_pm=tren_pm,
        tren_prog=tren_prog,
        # Variabel Filter
        selected_bulan=bulan_filter,
        selected_tahun=tahun_filter,
        available_years=available_years,
        bulan_names=BULAN_NAMES,
    )

@dashboard_bp.route('/master-relawan')
@login_required
@role_required('admin', 'tim_manajemen')
def master_relawan():
    relawan_list  = User.query.filter(User.role != 'admin', User.aktif == True).order_by(User.nama).all()
    pending_list  = User.query.filter(User.role == 'relawan', User.aktif == False).order_by(User.created_at.desc()).all()
    return render_template('master/master_relawan.html', relawan_list=relawan_list, pending_list=pending_list)

@dashboard_bp.route('/import-relawan', methods=['POST'])
@login_required
@crud_required
def import_relawan():
    import secrets
    if 'file' not in request.files:
        flash('Tidak ada file yang dipilih.', 'danger')
        return redirect(url_for('master.master_relawan'))

    file = request.files['file']
    try:
        xl = pd.read_excel(file, sheet_name=None)  # Baca semua sheet
        berhasil = 0
        dilewati = 0
        
        for sheet_name, df in xl.items():
            # Coba cari kolom nama (bisa 'Nama' atau 'Nama Lengkap')
            col_nama = 'Nama Lengkap' if 'Nama Lengkap' in df.columns else 'Nama'
            col_email = 'Email Address' if 'Email Address' in df.columns else 'Email'
            col_kode = 'Nomor Relawan'
            
            if col_nama not in df.columns:
                continue # Skip sheet jika tidak ada kolom nama
                
            df = df.dropna(subset=[col_nama])
            
            for _, row in df.iterrows():
                nama_val = str(row[col_nama]).strip()
                email_val = str(row[col_email]).strip() if col_email in df.columns and pd.notna(row[col_email]) else None
                kode_val = str(row[col_kode]).strip() if col_kode in df.columns and pd.notna(row[col_kode]) else None
                
                # 1. Anti-dobel: Cek by Kode Relawan (jika ada)
                existing = None
                if kode_val and kode_val.lower() != 'nan':
                    existing = User.query.filter_by(kode_relawan=kode_val).first()
                
                # 2. Anti-dobel: Cek by Email (jika ada)
                if not existing and email_val and email_val.lower() != 'nan':
                    existing = User.query.filter_by(email=email_val).first()
                    
                # 3. Anti-dobel: Cek by Nama (case-insensitive)
                if not existing:
                    existing = User.query.filter(db.func.lower(User.nama) == nama_val.lower()).first()
                
                if not existing:
                    # Buat kode relawan baru jika tidak disediakan
                    if not kode_val or kode_val.lower() == 'nan':
                        kode_val = f'REL{secrets.token_hex(3).upper()}'
                        
                    user = User(
                        kode_relawan=kode_val,
                        nama=nama_val,
                        email=email_val if email_val and email_val.lower() != 'nan' else None,
                        role='relawan',
                        aktif=True
                    )
                    user.set_password('123456') # Default password
                    db.session.add(user)
                    berhasil += 1
                else:
                    dilewati += 1
                    
        db.session.commit()
        flash(f'Berhasil import {berhasil} relawan baru. {dilewati} data dilewati (sudah ada di database).', 'success')
    except Exception as e:
        flash(f'Error saat import: {str(e)}', 'danger')

    return redirect(url_for('master.master_relawan'))

@dashboard_bp.route('/tambah-relawan', methods=['POST'])
@login_required
@crud_required
def tambah_relawan():
    import secrets
    nama = request.form.get('nama', '').strip()
    email = request.form.get('email', '').strip()
    role = request.form.get('role', 'relawan')
    
    if not nama:
        flash('Nama wajib diisi!', 'danger')
        return redirect(url_for('master.master_relawan'))
        
    kode_relawan = f'REL{secrets.token_hex(3).upper()}'
    
    if email:
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash(f'Gagal menambahkan. Email {email} sudah digunakan!', 'danger')
            return redirect(url_for('master.master_relawan'))
            
    user = User(
        kode_relawan=kode_relawan,
        nama=nama,
        email=email if email else None,
        role=role,
        aktif=True
    )
    user.set_password('123456')
    db.session.add(user)
    db.session.commit()
    flash(f'Relawan {nama} berhasil ditambahkan secara manual! (Kode: {kode_relawan}, Password Default: 123456)', 'success')
    return redirect(url_for('master.master_relawan'))

@dashboard_bp.route('/import-keaktifan', methods=['POST'])
@login_required
@crud_required
def import_keaktifan():
    if 'file' not in request.files:
        flash('Tidak ada file yang dipilih.', 'danger')
        return redirect(url_for('dashboard.index'))

    file = request.files['file']
    try:
        xl = pd.ExcelFile(file)
        total = 0
        for sheet in xl.sheet_names:
            df = xl.parse(sheet, header=3)
            df = df.dropna(subset=['Nama Relawan'])
            for _, row in df.iterrows():
                user = User.query.filter_by(nama=str(row['Nama Relawan'])).first()
                if user:
                    keaktifan = Keaktifan.query.filter_by(user_id=user.id).first()
                    hasil = int(row.get('HASIL', 0)) if pd.notna(row.get('HASIL', 0)) else 0
                    if keaktifan:
                        keaktifan.jumlah_kehadiran += hasil
                    else:
                        keaktifan = Keaktifan(user_id=user.id, jumlah_kehadiran=hasil)
                        db.session.add(keaktifan)
                    total += 1
        db.session.commit()
        flash(f'Berhasil import keaktifan {total} relawan!', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/import-program', methods=['POST'])
@login_required
@crud_required
def import_program():
    if 'file' not in request.files:
        flash('Tidak ada file yang dipilih.', 'danger')
        return redirect(url_for('dashboard.index'))

    file = request.files['file']
    try:
        xl = pd.ExcelFile(file)
        bulan_valid = {
            'januari': 'Januari', 'februari': 'Februari', 'maret': 'Maret',
            'april': 'April', 'mei': 'Mei', 'juni': 'Juni', 'juli': 'Juli',
            'agustus': 'Agustus', 'september': 'September', 'oktober': 'Oktober',
            'november': 'November', 'desember': 'Desember'
        }
        filename = file.filename
        tahun = None
        for part in filename.replace('-', '_').split('_'):
            if part.isdigit() and len(part) == 4:
                tahun = int(part)
                break
        berhasil = 0
        for sheet_name in xl.sheet_names:
            bulan_key = sheet_name.strip().lower()
            if bulan_key not in bulan_valid:
                continue
            nama_bulan = bulan_valid[bulan_key]
            df = xl.parse(sheet_name, header=0)
            col_nama = col_pm = None
            for col in df.columns:
                col_str = str(col).strip().lower()
                if 'nama program' in col_str or ('program' in col_str and col_nama is None):
                    col_nama = col
                elif 'jumlah pm' in col_str or col_str == 'pm':
                    col_pm = col
            if col_nama is None:
                continue
            df = df.dropna(subset=[col_nama])
            for _, row in df.iterrows():
                nama = str(row[col_nama]).strip()
                if nama.lower() in ['jumlah', 'total', 'nan', '']:
                    continue
                jumlah_pm = int(row[col_pm]) if col_pm and pd.notna(row.get(col_pm)) else 0
                program = Program(
                    nama_program=nama,
                    kategori='',
                    bulan=nama_bulan,
                    tahun=tahun,
                    jumlah_penerima_manfaat=jumlah_pm
                )
                db.session.add(program)
                berhasil += 1
        db.session.commit()
        flash(f'Berhasil import {berhasil} program dari file {filename}!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/edit-relawan/<int:user_id>', methods=['GET', 'POST'])
@login_required
@crud_required
def edit_relawan(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.nama         = request.form.get('nama', user.nama).strip()
        user.email        = request.form.get('email', '').strip() or None
        user.kode_relawan = request.form.get('kode_relawan', user.kode_relawan).strip()
        user.role         = request.form.get('role', user.role)
        user.aktif        = request.form.get('aktif') == '1'
        password_baru = request.form.get('password_baru', '').strip()
        if password_baru:
            if len(password_baru) < 6:
                flash('Password minimal 6 karakter.', 'danger')
                return render_template('dashboard/edit_relawan.html', user=user)
            user.set_password(password_baru)
        duplikat = User.query.filter(
            User.kode_relawan == user.kode_relawan,
            User.id != user.id
        ).first()
        if duplikat:
            flash('Kode relawan sudah digunakan.', 'danger')
            return render_template('dashboard/edit_relawan.html', user=user)
        db.session.commit()
        flash(f'Data {user.nama} berhasil diperbarui!', 'success')
        return redirect(url_for('master.master_relawan'))
    return render_template('dashboard/edit_relawan.html', user=user)

@dashboard_bp.route('/hapus-relawan/<int:user_id>', methods=['POST'])
@login_required
@crud_required
def hapus_relawan(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == 'admin':
        flash('Tidak bisa menghapus akun admin.', 'danger')
        return redirect(url_for('master.master_relawan'))
    from app.models import TimAkses
    Presensi.query.filter_by(user_id=user.id).delete()
    Keaktifan.query.filter_by(user_id=user.id).delete()
    TimAkses.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    flash(f'Relawan {user.nama} berhasil dihapus.', 'success')
    return redirect(url_for('master.master_relawan'))


@dashboard_bp.route('/approve-relawan/<int:user_id>', methods=['POST'])
@login_required
@role_required('admin')
def approve_relawan(user_id):
    user = User.query.get_or_404(user_id)
    user.aktif = True
    db.session.commit()
    flash(f'Akun relawan {user.nama} ({user.kode_relawan}) telah disetujui. Relawan sudah bisa login.', 'success')
    return redirect(url_for('master.master_relawan'))


@dashboard_bp.route('/tolak-relawan/<int:user_id>', methods=['POST'])
@login_required
@role_required('admin')
def tolak_relawan(user_id):
    user = User.query.get_or_404(user_id)
    nama = user.nama
    from app.models import TimAkses
    Presensi.query.filter_by(user_id=user.id).delete()
    Keaktifan.query.filter_by(user_id=user.id).delete()
    TimAkses.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    flash(f'Pendaftaran relawan {nama} telah ditolak dan dihapus.', 'warning')
    return redirect(url_for('master.master_relawan'))

# ── ROUTE APPROVAL PRESENSI ──
@dashboard_bp.route('/approval-presensi')
@login_required
@role_required('admin', 'tim_manajemen')
def approval_presensi():
    # Ambil presensi yang statusnya masih 'pending'
    pending_list = Presensi.query.filter_by(status='pending').order_by(Presensi.created_at.desc()).all()
    return render_template('dashboard/approval_presensi.html', pending_list=pending_list)

@dashboard_bp.route('/approve-absen/<int:presensi_id>', methods=['POST'])
@login_required
@role_required('admin')
def approve_absen(presensi_id):
    p = Presensi.query.get_or_404(presensi_id)
    p.status = 'hadir'
    
    # Update keaktifan relawan
    keaktifan = Keaktifan.query.filter_by(user_id=p.user_id).first()
    if not keaktifan:
        keaktifan = Keaktifan(user_id=p.user_id, jumlah_kehadiran=1, total_manhours=p.total_jam or 0)
        db.session.add(keaktifan)
    else:
        keaktifan.jumlah_kehadiran += 1
        keaktifan.total_manhours += (p.total_jam or 0)
        
    # Tambah Notifikasi
    notif = Notifikasi(
        user_id=p.user_id,
        pesan=f"Presensi Anda untuk program '{p.nama_program}' pada {p.tanggal.strftime('%d/%m/%Y')} telah DISETUJUI."
    )
    db.session.add(notif)
        
    db.session.commit()
    flash(f'Presensi {p.user.nama} berhasil disetujui.', 'success')
    return redirect(url_for('dashboard.approval_presensi'))

@dashboard_bp.route('/tolak-absen/<int:presensi_id>', methods=['POST'])
@login_required
@role_required('admin')
def tolak_absen(presensi_id):
    p = Presensi.query.get_or_404(presensi_id)
    p.status = 'ditolak'
    
    # Tambah Notifikasi
    notif = Notifikasi(
        user_id=p.user_id,
        pesan=f"Mohon maaf, presensi Anda untuk program '{p.nama_program}' pada {p.tanggal.strftime('%d/%m/%Y')} DITOLAK."
    )
    db.session.add(notif)
    
    db.session.commit()
    flash(f'Presensi {p.user.nama} telah ditolak (Dianggap tidak hadir).', 'danger')
    return redirect(url_for('dashboard.approval_presensi'))

@dashboard_bp.route('/master-program')
@login_required
@role_required('admin', 'tim_manajemen')
def master_program():
    program_list = Program.query.order_by(Program.id.desc()).all()
    return render_template('dashboard/master_program.html', program_list=program_list)
@dashboard_bp.route('/reset-wajah/<int:user_id>', methods=['POST'])
@login_required
@crud_required
def reset_wajah(user_id):
    user = User.query.get_or_404(user_id)
    user.face_encoding = None
    user.foto_wajah = None
    db.session.commit()
    flash(f'Data wajah relawan "{user.nama}" berhasil direset. Silakan minta relawan untuk mendaftar wajah kembali.', 'success')
    return redirect(url_for('master.master_relawan'))

@dashboard_bp.route('/tambah-program', methods=['GET', 'POST'])
@login_required
@crud_required
def tambah_program():
    if request.method == 'POST':
        from datetime import date as _date
        nama         = request.form.get('nama_program', '').strip()
        kategori     = request.form.get('kategori', '').strip()
        bulan        = request.form.get('bulan', '').strip()
        tahun        = request.form.get('tahun', '')
        tgl_str      = request.form.get('tanggal_pelaksanaan', '').strip()
        nama_tempat = request.form.get('nama_tempat','').strip()
        jml_relawan  = request.form.get('jumlah_relawan', 0)
        jml_penerima = request.form.get('jumlah_penerima_manfaat', 0)
        lama_menit   = request.form.get('lama_kegiatan_menit', '')
        kecamatan   = request.form.get('kecamatan', '').strip()
        kelurahan   = request.form.get('kelurahan', '').strip()
        kota        = request.form.get('kota', '').strip()
        provinsi    = request.form.get('provinsi', '').strip()
        
        # Jika tanggal diisi, otomatis isi bulan & tahun dari tanggal tersebut
        tanggal_obj = None
        if tgl_str:
            try:
                tanggal_obj = _date.fromisoformat(tgl_str)
                if not bulan:
                    bulan = BULAN_NAMES[tanggal_obj.month - 1]
                if not tahun:
                    tahun = str(tanggal_obj.year)
            except ValueError:
                pass
        
        if not nama:
            flash('Nama program tidak boleh kosong.', 'danger')
            return redirect(url_for('dashboard.tambah_program'))
        program = Program(
            nama_program=nama, kategori=kategori, bulan=bulan,
            tahun=int(tahun) if tahun else None,
            nama_tempat=nama_tempat,
            tanggal_pelaksanaan=tanggal_obj,
            jumlah_relawan=int(jml_relawan) if jml_relawan else 0,
            jumlah_penerima_manfaat=int(jml_penerima) if jml_penerima else 0,
            lama_kegiatan_menit=int(lama_menit) if lama_menit else None,
            kecamatan=kecamatan, kelurahan=kelurahan, kota=kota, provinsi=provinsi,
        )
        db.session.add(program)
        db.session.commit()
        flash(f'Program "{nama}" berhasil ditambahkan!', 'success')
        return redirect(url_for('master.master_program'))
    return render_template('dashboard/tambah_program.html')

@dashboard_bp.route('/edit-program/<int:program_id>', methods=['GET', 'POST'])
@login_required
@crud_required
def edit_program(program_id):
    from datetime import date as _date
    program = Program.query.get_or_404(program_id)
    if request.method == 'POST':
        program.nama_program            = request.form.get('nama_program', '').strip()
        program.kategori                = request.form.get('kategori', '').strip()
        program.bulan                   = request.form.get('bulan', '').strip()
        program.tahun                   = int(request.form.get('tahun')) if request.form.get('tahun') else None
        tgl_str = request.form.get('tanggal_pelaksanaan', '').strip()
        if tgl_str:
            try:
                program.tanggal_pelaksanaan = _date.fromisoformat(tgl_str)
                # Auto-isi bulan & tahun jika kosong
                if not program.bulan:
                    program.bulan = BULAN_NAMES[program.tanggal_pelaksanaan.month - 1]
                if not program.tahun:
                    program.tahun = program.tanggal_pelaksanaan.year
            except ValueError:
                program.tanggal_pelaksanaan = None
        else:
            program.tanggal_pelaksanaan = None
        program.nama_tempat             = request.form.get('nama_tempat', '').strip()
        program.jumlah_relawan          = int(request.form.get('jumlah_relawan', 0))
        program.jumlah_penerima_manfaat = int(request.form.get('jumlah_penerima_manfaat', 0))
        lama_menit = request.form.get('lama_kegiatan_menit', '')
        program.lama_kegiatan_menit = int(lama_menit) if lama_menit else None
        program.kecamatan  = request.form.get('kecamatan', '').strip()
        program.kelurahan  = request.form.get('kelurahan', '').strip()
        program.kota       = request.form.get('kota', '').strip()
        program.provinsi   = request.form.get('provinsi', '').strip()
        if not program.nama_program:
            flash('Nama program tidak boleh kosong.', 'danger')
            return render_template('dashboard/edit_program.html', program=program)
        db.session.commit()
        flash(f'Program "{program.nama_program}" berhasil diperbarui!', 'success')
        return redirect(url_for('master.master_program'))
    return render_template('dashboard/edit_program.html', program=program)

@dashboard_bp.route('/get-program/<int:program_id>')
@login_required
@role_required('admin', 'tim_manajemen')
def get_program(program_id):
    program = Program.query.get_or_404(program_id)
    return jsonify({
        'id':                      program.id,
        'nama_program':            program.nama_program,
        'kategori':                program.kategori or '',
        'bulan':                   program.bulan or '',
        'tahun':                   program.tahun or '',
        'tanggal_pelaksanaan':     program.tanggal_pelaksanaan.isoformat() if program.tanggal_pelaksanaan else '',
        'nama_tempat':            program.nama_tempat or '',
        'jumlah_relawan':          program.jumlah_relawan or 0,
        'jumlah_penerima_manfaat': program.jumlah_penerima_manfaat or 0,
        'lama_kegiatan_menit':     program.lama_kegiatan_menit or 0,
        'kecamatan':               program.kecamatan or '',
        'kelurahan':               program.kelurahan or '',
        'kota':                    program.kota or '',
        'provinsi':                program.provinsi or '',
    })

@dashboard_bp.route('/koordinator-program/<int:program_id>', methods=['GET', 'POST'])
@login_required
@crud_required
def koordinator_program(program_id):
    from app.models import KoordinatorProgram
    program = Program.query.get_or_404(program_id)
    
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        aksi = request.form.get('aksi')
        
        if aksi == 'tambah':
            if not user_id:
                flash('Pilih relawan terlebih dahulu.', 'danger')
            else:
                existing = KoordinatorProgram.query.filter_by(program_id=program.id, user_id=user_id).first()
                if existing:
                    flash('Relawan ini sudah menjadi koordinator di program ini.', 'warning')
                else:
                    baru = KoordinatorProgram(program_id=program.id, user_id=user_id, ditunjuk_oleh=current_user.id)
                    db.session.add(baru)
                    db.session.commit()
                    flash('Koordinator berhasil ditambahkan!', 'success')
        
        elif aksi == 'hapus':
            koor_id = request.form.get('koordinator_id')
            koor = KoordinatorProgram.query.get(koor_id)
            if koor:
                db.session.delete(koor)
                db.session.commit()
                flash('Koordinator berhasil dihapus.', 'success')
                
        return redirect(url_for('dashboard.koordinator_program', program_id=program.id))
        
    relawan_list = User.query.filter_by(role='relawan', aktif=True).order_by(User.nama).all()
    koordinator_list = KoordinatorProgram.query.filter_by(program_id=program.id).all()
    
    return render_template('dashboard/koordinator_program.html', 
                           program=program, 
                           relawan_list=relawan_list, 
                           koordinator_list=koordinator_list)

@dashboard_bp.route('/hapus-program/<int:program_id>', methods=['POST'])
@login_required
@crud_required
def hapus_program(program_id):
    program = Program.query.get_or_404(program_id)
    nama = program.nama_program
    db.session.delete(program)
    db.session.commit()
    flash(f'Program "{nama}" berhasil dihapus.', 'success')
    return redirect(url_for('master.master_program'))

@dashboard_bp.route('/evaluasi-program/<int:program_id>')
@login_required
@role_required('admin', 'tim_manajemen')
def view_evaluasi_program(program_id):
    from app.models import EvaluasiProgram, KoordinatorProgram
    program = Program.query.get_or_404(program_id)
    evaluasi_list = EvaluasiProgram.query.filter_by(program_id=program.id)\
        .order_by(EvaluasiProgram.created_at.desc()).all()
    koordinator_list = KoordinatorProgram.query.filter_by(program_id=program.id).all()
    return render_template('dashboard/evaluasi_program.html',
                           program=program,
                           evaluasi_list=evaluasi_list,
                           koordinator_list=koordinator_list)

@dashboard_bp.route('/semua-evaluasi')
@login_required
@role_required('admin', 'tim_manajemen')
def semua_evaluasi():
    from app.models import EvaluasiProgram
    evaluasi_list = EvaluasiProgram.query.order_by(EvaluasiProgram.created_at.desc()).all()
    total_eval = len(evaluasi_list)
    total_pm_aktual = sum(e.jumlah_pm_aktual or 0 for e in evaluasi_list)
    program_sudah_eval = len(set(e.program_id for e in evaluasi_list))
    total_program = Program.query.count()
    return render_template('dashboard/semua_evaluasi.html',
                           evaluasi_list=evaluasi_list,
                           total_eval=total_eval,
                           total_pm_aktual=total_pm_aktual,
                           program_sudah_eval=program_sudah_eval,
                           total_program=total_program)

@dashboard_bp.route('/hak-akses', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def hak_akses():
    from app.models import TimAkses

    if request.method == 'POST':
        user_id    = request.form.get('user_id')
        akses_crud = request.form.get('akses_crud') == '1'
        hapus      = request.form.get('hapus') == '1'

        user = User.query.get_or_404(user_id)
        if user.role != 'tim_manajemen':
            flash('Hanya tim manajemen yang bisa diberi hak akses.', 'danger')
            return redirect(url_for('dashboard.hak_akses'))

        akses = TimAkses.query.filter_by(user_id=user_id).first()

        if hapus:
            if akses:
                db.session.delete(akses)
                db.session.commit()
                flash(f'Hak akses {user.nama} berhasil dihapus!', 'success')
        elif akses:
            akses.akses_crud = akses_crud
            db.session.commit()
            flash(f'Hak akses {user.nama} berhasil diperbarui!', 'success')
        else:
            akses = TimAkses(
                user_id=user_id,
                akses_crud=akses_crud,
                diberikan_oleh=current_user.id
            )
            db.session.add(akses)
            db.session.commit()
            flash(f'Hak akses {user.nama} berhasil ditambahkan!', 'success')

        return redirect(url_for('dashboard.hak_akses'))

    tim_list     = User.query.filter_by(role='tim_manajemen').all()
    semua_tim    = User.query.filter_by(role='tim_manajemen', aktif=True).all()
    relawan_list = User.query.filter_by(role='relawan').all()
    akses_list   = {a.user_id: a for a in TimAkses.query.all()}

    return render_template('dashboard/hak_akses.html',
        tim_list=tim_list,
        semua_tim=semua_tim,
        relawan_list=relawan_list,
        akses_list=akses_list
    )

@dashboard_bp.route('/laporan-keaktifan')
@login_required
@role_required('admin', 'tim_manajemen')
def laporan_keaktifan():
    # Initial page load
    # Filter options
    kategori_list = db.session.query(Program.kategori).filter(Program.kategori != None, Program.kategori != '').distinct().all()
    kategori_list = [k[0] for k in kategori_list]
    
    # Get available months/years from presensi
    from sqlalchemy import func, extract
    dates = db.session.query(
        extract('year', Presensi.tanggal).label('y'),
        extract('month', Presensi.tanggal).label('m')
    ).distinct().order_by('y', 'm').all()
    
    periode_list = []
    for d in dates:
        y, m = int(d.y), int(d.m)
        periode_list.append(f"{y}-{m:02d}")
        
    return render_template('dashboard/laporan_keaktifan.html',
        kategori_list=kategori_list,
        periode_list=periode_list
    )

@dashboard_bp.route('/api/laporan-keaktifan-data')
@login_required
@role_required('admin', 'tim_manajemen')
def api_laporan_data():
    from sqlalchemy import func, extract
    
    periode  = request.args.get('periode', '')
    kategori = request.args.get('kategori', '')
    
    # Base query for users
    relawans = User.query.filter_by(role='relawan', aktif=True).all()
    
    # Base presensi query
    pq = db.session.query(Presensi)
    
    if periode:
        y, m = periode.split('-')
        pq = pq.filter(extract('year', Presensi.tanggal) == y, extract('month', Presensi.tanggal) == m)
        
    if kategori:
        pq = pq.join(Program, Presensi.nama_program == Program.nama_program).filter(Program.kategori == kategori)
        
    # Group presensi per user
    presensi_stats = pq.with_entities(
        Presensi.user_id,
        func.count(Presensi.id).label('hadir'),
        func.sum(Presensi.total_jam).label('jam'),
        func.max(Presensi.tanggal).label('terakhir')
    ).group_by(Presensi.user_id).all()
    
    stats_map = {p.user_id: {'hadir': p.hadir, 'jam': p.jam or 0, 'terakhir': p.terakhir} for p in presensi_stats}
    
    # Kategori terbanyak per user (based on filtered presensi if needed, or overall?)
    # Usually "kategori terbanyak" means overall or within period. Let's do within period.
    kat_q = db.session.query(
        Presensi.user_id,
        Program.kategori,
        func.count(Presensi.id).label('cnt')
    ).join(Program, Presensi.nama_program == Program.nama_program)
    
    if periode:
        y, m = periode.split('-')
        kat_q = kat_q.filter(extract('year', Presensi.tanggal) == y, extract('month', Presensi.tanggal) == m)
        
    kategori_data = kat_q.group_by(Presensi.user_id, Program.kategori).order_by(Presensi.user_id, func.count(Presensi.id).desc()).all()
    
    kat_map = {}
    for row in kategori_data:
        uid = row.user_id
        if uid not in kat_map:
            kat_map[uid] = row.kategori or 'Lainnya'

    table_data = []
    for r in relawans:
        st = stats_map.get(r.id, {'hadir': 0, 'jam': 0, 'terakhir': None})
        hadir = st['hadir']
        jam = st['jam']
        
        if hadir == 0 and (periode or kategori):
            continue # skip if no data in filtered period
            
        skor = (hadir * 4) + (jam * 1)
        if skor > 100: skor = 100
        
        status = 'Kurang Aktif'
        if skor >= 80: status = 'Sangat Aktif'
        elif skor >= 50: status = 'Aktif'
        
        table_data.append({
            'id': r.id,
            'nama': r.nama,
            'kode': r.kode_relawan,
            'hadir': hadir,
            'jam': round(jam, 2),
            'kategori': kat_map.get(r.id, '-'),
            'terakhir': st['terakhir'].strftime('%Y-%m-%d') if st['terakhir'] else '-',
            'skor': round(skor, 1),
            'status': status
        })
        
    total_relawan = len(table_data)
    total_hadir_all = sum(d['hadir'] for d in table_data)
    rata_hadir = total_hadir_all / total_relawan if total_relawan > 0 else 0
    total_manhours_all = sum(d['jam'] for d in table_data)
    sangat_aktif = sum(1 for d in table_data if d['status'] == 'Sangat Aktif')
    
    return jsonify({
        'summary': {
            'total_relawan': total_relawan,
            'rata_hadir': round(rata_hadir, 1),
            'total_manhours': round(total_manhours_all, 1),
            'sangat_aktif': sangat_aktif
        },
        'table': table_data
    })

@dashboard_bp.route('/api/relawan/<int:user_id>/detail')
@login_required
@role_required('admin', 'tim_manajemen')
def api_relawan_detail(user_id):
    user = User.query.get_or_404(user_id)
    presensis = Presensi.query.filter_by(user_id=user.id).order_by(Presensi.tanggal.desc()).all()
    
    riwayat = []
    kat_manhours = {}
    hadir = 0
    jam_total = 0
    
    for p in presensis:
        hadir += 1
        jam = p.total_jam or 0
        jam_total += jam
        
        prog = Program.query.filter_by(nama_program=p.nama_program).first()
        kat = prog.kategori if prog and prog.kategori else 'Lainnya'
        
        if kat not in kat_manhours:
            kat_manhours[kat] = 0
        kat_manhours[kat] += jam
        
        riwayat.append({
            'tanggal': p.tanggal.strftime('%d/%m/%Y'),
            'nama_program': p.nama_program or '-',
            'kategori': kat,
            'jam': round(jam, 2)
        })
        
    return jsonify({
        'nama': user.nama,
        'kode': user.kode_relawan,
        'hadir': hadir,
        'jam': round(jam_total, 2),
        'chart_labels': list(kat_manhours.keys()),
        'chart_data': [round(v, 2) for v in kat_manhours.values()],
        'riwayat': riwayat
    })


@dashboard_bp.route('/profil', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'tim_manajemen')
def profil():
    if request.method == 'POST':
        nama = request.form.get('nama')
        email = request.form.get('email', '').strip()
        password_lama = request.form.get('password_lama')
        password_baru = request.form.get('password_baru')
        konfirmasi_password = request.form.get('konfirmasi_password')

        current_user.nama = nama
        current_user.email = email if email else None

        if password_lama or password_baru:
            if not current_user.check_password(password_lama):
                flash('Kata sandi lama salah.', 'danger')
                return redirect(url_for('dashboard.profil'))
            
            if len(password_baru) < 6:
                flash('Kata sandi baru minimal 6 karakter.', 'danger')
                return redirect(url_for('dashboard.profil'))
            
            if password_baru != konfirmasi_password:
                flash('Konfirmasi kata sandi tidak cocok.', 'danger')
                return redirect(url_for('dashboard.profil'))
            
            current_user.set_password(password_baru)
            flash('Profil dan kata sandi berhasil diperbarui!', 'success')
        else:
            flash('Profil berhasil diperbarui!', 'success')

        db.session.commit()
        return redirect(url_for('dashboard.profil'))

    return render_template('profil_admin.html')

@dashboard_bp.route('/export-excel')
@login_required
@role_required('admin', 'tim_manajemen')
def export_excel():
    from app.report_utils import generate_program_excel
    from flask import send_file
    
    bulan = request.args.get('bulan', '').strip()
    tahun_str = request.args.get('tahun', '').strip()
    tahun = int(tahun_str) if (tahun_str and tahun_str.isdigit()) else None
    
    try:
        output = generate_program_excel(bulan=bulan or None, tahun=tahun)
        filename = 'rekap_program'
        if bulan:
            filename += f'_{bulan.lower()}'
        if tahun:
            filename += f'_{tahun}'
        filename += '.xlsx'
        return send_file(output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            download_name=filename,
            as_attachment=True
        )
    except Exception as e:
        flash(f'Gagal mengekspor Excel: {str(e)}', 'danger')
        return redirect(url_for('dashboard.index', bulan=bulan, tahun=tahun))

@dashboard_bp.route('/export-pdf')
@login_required
@role_required('admin', 'tim_manajemen')
def export_pdf():
    from app.models import Program, User
    from app import db
    from sqlalchemy import func
    
    bulan = request.args.get('bulan', '').strip()
    tahun_str = request.args.get('tahun', '').strip()
    tahun = int(tahun_str) if (tahun_str and tahun_str.isdigit()) else None
    
    prog_query = Program.query
    if bulan:
        prog_query = prog_query.filter(Program.bulan == bulan)
    if tahun:
        prog_query = prog_query.filter(Program.tahun == tahun)
    total_program = prog_query.count()
    
    pm_query = db.session.query(func.sum(Program.jumlah_penerima_manfaat))
    if bulan:
        pm_query = pm_query.filter(Program.bulan == bulan)
    if tahun:
        pm_query = pm_query.filter(Program.tahun == tahun)
    total_penerima = pm_query.scalar() or 0
    
    lokasi_query = db.session.query(func.count(func.distinct(Program.kota))).filter(Program.kota != None, Program.kota != '')
    if bulan:
        lokasi_query = lokasi_query.filter(Program.bulan == bulan)
    if tahun:
        lokasi_query = lokasi_query.filter(Program.tahun == tahun)
    total_lokasi = lokasi_query.scalar() or 0
    
    total_relawan = User.query.filter_by(role='relawan', aktif=True).count()
    
    kat_query = db.session.query(
        Program.kategori,
        func.count(Program.id).label('jumlah_program'),
        func.sum(Program.jumlah_penerima_manfaat).label('total_pm')
    ).filter(Program.kategori != None, Program.kategori != '')
    if bulan:
        kat_query = kat_query.filter(Program.bulan == bulan)
    if tahun:
        kat_query = kat_query.filter(Program.tahun == tahun)
    kat_all_raw = kat_query.group_by(Program.kategori)\
     .order_by(func.sum(Program.jumlah_penerima_manfaat).desc()).all()
     
    sebaran_query = db.session.query(
        Program.kota,
        func.count(Program.id).label('jumlah_program'),
        func.sum(Program.jumlah_penerima_manfaat).label('total_pm')
    ).filter(Program.kota != None, Program.kota != '')
    if bulan:
        sebaran_query = sebaran_query.filter(Program.bulan == bulan)
    if tahun:
        sebaran_query = sebaran_query.filter(Program.tahun == tahun)
    sebaran_raw = sebaran_query.group_by(Program.kota)\
     .order_by(func.sum(Program.jumlah_penerima_manfaat).desc()).all()
     
    program_list = prog_query.order_by(Program.id.desc()).all()
    printed_at = datetime.now().strftime('%d %B %Y, %H:%M')
    
    back_url = url_for('dashboard.index', bulan=bulan, tahun=tahun)
    
    return render_template('dashboard/laporan_pdf.html',
        total_program=total_program,
        total_penerima=total_penerima,
        total_lokasi=total_lokasi,
        total_relawan=total_relawan,
        kat_all_raw=kat_all_raw,
        sebaran_raw=sebaran_raw,
        program_list=program_list,
        printed_at=printed_at,
        printed_by=current_user.nama,
        back_url=back_url,
        selected_bulan=bulan,
        selected_tahun=tahun
    )