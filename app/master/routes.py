from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Program, User

master_bp = Blueprint('master', __name__)

@master_bp.route('/master/relawan')
@login_required
def master_relawan():
    relawan_list = User.query.filter(
        User.role != 'admin',
        User.aktif == True
    ).order_by(User.nama).all()
    pending_list = User.query.filter(
        User.role == 'relawan',
        User.aktif == False
    ).order_by(User.created_at.desc()).all()
    return render_template('dashboard/master_relawan.html',
        relawan_list=relawan_list,
        pending_list=pending_list
    )

@master_bp.route('/master/program')
@login_required
def master_program():
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    base_query = Program.query.order_by(Program.id.desc())

    if q:
        base_query = base_query.filter(
            db.or_(
                Program.nama_program.ilike(f'%{q}%'),
                Program.kategori.ilike(f'%{q}%'),
                Program.kota.ilike(f'%{q}%'),
                Program.kecamatan.ilike(f'%{q}%'),
                Program.kelurahan.ilike(f'%{q}%'),
                Program.provinsi.ilike(f'%{q}%'),
                Program.nama_tempat.ilike(f'%{q}%'),
            )
        )
        program_list = base_query.all()
        pagination = None
    else:
        pagination = base_query.paginate(page=page, per_page=10, error_out=False)
        program_list = pagination.items

    return render_template('dashboard/master_program.html',
        program_list=program_list, pagination=pagination, search_query=q)

@master_bp.route('/master/program/tambah', methods=['GET', 'POST'])
@login_required
def tambah_program():
    if request.method == 'POST':
        nama        = request.form.get('nama_program', '').strip()
        kategori    = request.form.get('kategori', '')
        bulan       = request.form.get('bulan', '')
        tahun       = request.form.get('tahun', '')
        lokasi      = request.form.get('lokasi', '').strip()
        nama_tempat = request.form.get('nama_tempat', '').strip()
        jml_relawan = request.form.get('jumlah_relawan', 0)

        if not nama:
            flash('Nama program wajib diisi.', 'danger')
            return redirect(url_for('master.tambah_program'))

        program = Program(
            nama_program   = nama,
            kategori       = kategori,
            bulan          = bulan,
            tahun          = int(tahun) if tahun else None,
            lokasi         = lokasi,
            nama_tempat    = nama_tempat,
            jumlah_relawan = int(jml_relawan) if jml_relawan else 0,
        )
        db.session.add(program)
        db.session.commit()
        flash('Program berhasil ditambahkan!', 'success')
        return redirect(url_for('master.master_program'))

    return render_template('dashboard/tambah_program.html')