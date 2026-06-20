from flask import render_template, redirect, url_for, flash, send_file, request
from flask_login import login_required, current_user
from functools import wraps
from app.tim_manajemen import tim_manajemen_bp
from app.models import User, Keaktifan, Program, Presensi
from app import db
from types import SimpleNamespace
from sqlalchemy import func
from datetime import date, datetime, timedelta
import pandas as pd
import io

BULAN_NAMES = ['Januari','Februari','Maret','April','Mei','Juni',
               'Juli','Agustus','September','Oktober','November','Desember']

def tim_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['admin', 'tim_manajemen']:
            flash('Akses ditolak.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@tim_manajemen_bp.route('/')
@login_required
@tim_required
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
    
    semua_program     = Program.query.all()

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
    
    total_penerima = int(db.session.query(func.sum(Program.jumlah_penerima_manfaat)).scalar() or 0)
    total_lokasi   = db.session.query(func.count(func.distinct(Program.kota)))\
        .filter(Program.kota != None, Program.kota != '').scalar() or 0

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
    target_labels    = semua_kat
    target_realisasi = [kat_ini.get(k, 0)  for k in semua_kat]
    target_bulan_lalu= [kat_lalu.get(k, 0) for k in semua_kat]

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

    act_query = Program.query
    if bulan_filter:
        act_query = act_query.filter_by(bulan=bulan_filter)
    if tahun_filter:
        act_query = act_query.filter_by(tahun=tahun_filter)
    aktivitas_terbaru = act_query.order_by(Program.id.desc()).limit(10).all()

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
    program_tanpa_lokasi   = Program.query.filter(
        db.or_(Program.kota == None, Program.kota == '')).count()
    pending_presensi_count = Presensi.query.filter_by(status='pending').count()

    top_relawan_query = db.session.query(
        User,
        func.count(Presensi.id).label('jumlah_kehadiran'),
        func.sum(Presensi.total_jam).label('total_manhours')
    ).join(Presensi, User.id == Presensi.user_id)\
     .filter(User.role == 'relawan')
     
    if bulan_filter or tahun_filter:
        top_relawan_query = top_relawan_query.join(Program, Presensi.program_id == Program.id)
        if bulan_filter:
            top_relawan_query = top_relawan_query.filter(Program.bulan == bulan_filter)
        if tahun_filter:
            top_relawan_query = top_relawan_query.filter(Program.tahun == tahun_filter)
            
    top_relawan_raw = top_relawan_query.group_by(User.id)\
     .order_by(func.count(Presensi.id).desc())\
     .limit(5).all()
     
    top_relawan = [
        (row[0], SimpleNamespace(jumlah_kehadiran=row[1], total_manhours=round(row[2] or 0, 2)))
        for row in top_relawan_raw
    ]
    
    top_program_query = Program.query
    if bulan_filter:
        top_program_query = top_program_query.filter(Program.bulan == bulan_filter)
    if tahun_filter:
        top_program_query = top_program_query.filter(Program.tahun == tahun_filter)
    top_program = top_program_query.order_by(Program.jumlah_penerima_manfaat.desc()).limit(5).all()
    
    semua_program = Program.query.all()

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

    semua_program_json = [
        {
            'nama'    : p.nama_program,
            'kategori': p.kategori or 'Lainnya',
            'bulan'   : (p.bulan or '').lower(),
            'tahun'   : p.tahun,
            'relawan' : p.jumlah_relawan or 0,
            'manfaat' : p.jumlah_penerima_manfaat or 0,
        }
        for p in semua_program
    ]

    return render_template('tim_manajemen/index.html',
        total_relawan=total_relawan,
        hadir_hari_ini=hadir_hari_ini,
        total_manhours=round(total_manhours, 2),
        semua_program=semua_program,
        total_penerima=total_penerima,
        total_lokasi=total_lokasi,
        bulan_ini=bulan_ini,
        tahun_ini=tahun_ini,
        pm_bulan_ini=pm_bulan_ini,
        program_bulan_ini=program_bulan_ini,
        lokasi_bulan_ini=lokasi_bulan_ini,
        sebaran_labels=sebaran_labels,
        sebaran_pm=sebaran_pm,
        sebaran_prog=sebaran_prog,
        bulan_lalu=bulan_lalu,
        target_labels=target_labels,
        target_realisasi=target_realisasi,
        target_bulan_lalu=target_bulan_lalu,
        kat_all_labels=kat_all_labels,
        kat_all_pm=kat_all_pm,
        kat_all_prog=kat_all_prog,
        kat_all_pct=kat_all_pct,
        aktivitas_terbaru=aktivitas_terbaru,
        relawan_absen_lama=relawan_absen_lama,
        program_tanpa_lokasi=program_tanpa_lokasi,
        pending_presensi_count=pending_presensi_count,
        top_relawan=top_relawan,
        top_program=top_program,
        tren_labels=tren_labels,
        tren_pm=tren_pm,
        tren_prog=tren_prog,
        semua_program_json=semua_program_json,
        # Variabel Filter
        selected_bulan=bulan_filter,
        selected_tahun=tahun_filter,
        available_years=available_years,
        bulan_names=BULAN_NAMES,
    )

@tim_manajemen_bp.route('/relawan')
@login_required
@tim_required
def lihat_relawan():
    relawan_list = User.query.filter_by(role='relawan').all()
    return render_template('tim_manajemen/relawan.html', relawan_list=relawan_list)



@tim_manajemen_bp.route('/download-presensi-excel')
@login_required
@tim_required
def download_presensi_excel():
    presensi_list = Presensi.query.order_by(Presensi.tanggal.desc()).all()
    data = [{
        'Nama': p.user.nama,
        'Kode Relawan': p.user.kode_relawan,
        'Tanggal': p.tanggal,
        'Jam Masuk': p.jam_masuk.strftime('%H:%M:%S') if p.jam_masuk else '-',
        'Jam Keluar': p.jam_keluar.strftime('%H:%M:%S') if p.jam_keluar else '-',
        'Total Jam': p.total_jam,
        'Status': p.status
    } for p in presensi_list]

    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Presensi')
    output.seek(0)
    return send_file(output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        download_name='rekap_presensi.xlsx',
        as_attachment=True
    )

@tim_manajemen_bp.route('/export-excel')
@login_required
@tim_required
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
        return redirect(url_for('tim_manajemen.index', bulan=bulan, tahun=tahun))

@tim_manajemen_bp.route('/export-pdf')
@login_required
@tim_required
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
    
    back_url = url_for('tim_manajemen.index', bulan=bulan, tahun=tahun)
    
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