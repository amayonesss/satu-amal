from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from app.auth import auth_bp
from app.models import User
from app import db, mail
import secrets
from datetime import datetime, timedelta

@auth_bp.route('/', methods=['GET', 'POST'])
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('dashboard.index'))
        elif current_user.role == 'tim_manajemen':
            return redirect(url_for('tim_manajemen.index'))
        else:
            return redirect(url_for('relawan.index'))

    if request.method == 'POST':
        kode_atau_email = request.form.get('kode_relawan')
        password = request.form.get('password')
        ingat_saya = request.form.get('ingat_saya')

        user = User.query.filter(
            (User.kode_relawan == kode_atau_email) |
            (User.email == kode_atau_email)
        ).first()

        if user and user.check_password(password) and user.aktif:
            login_user(user, remember=bool(ingat_saya))
            print(f"DEBUG - User: {user.nama}, Role: {user.role}")
            if user.role == 'admin':
                return redirect(url_for('dashboard.index'))
            elif user.role == 'tim_manajemen':
                return redirect(url_for('tim_manajemen.index'))
            else:
                return redirect(url_for('relawan.index'))
        else:
            flash('Kode relawan/email atau password salah.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    flash('Pendaftaran mandiri telah ditutup. Silakan hubungi Admin untuk mendaftar.', 'danger')
    return redirect(url_for('auth.login'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_exp = datetime.now() + timedelta(hours=1)
            db.session.commit()

            reset_url = url_for('auth.reset_password', token=token, _external=True)
            msg = Message(
                'Reset Password - Satu Amal Indonesia',
                recipients=[email]
            )
            msg.body = f'''Halo {user.nama},

Kamu menerima email ini karena ada permintaan reset password.

Klik link berikut untuk reset password (berlaku 1 jam):
{reset_url}

Jika kamu tidak merasa meminta reset password, abaikan email ini.

Salam,
Tim Satu Amal Indonesia
'''
            mail.send(msg)

        flash('Jika email terdaftar, link reset password telah dikirim.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()

    if not user or user.reset_token_exp < datetime.now():
        flash('Link reset password tidak valid atau sudah kadaluarsa.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password')
        konfirmasi = request.form.get('konfirmasi_password')

        if password != konfirmasi:
            flash('Password tidak sama.', 'danger')
            return render_template('auth/reset_password.html')

        user.set_password(password)
        user.reset_token = None
        user.reset_token_exp = None
        db.session.commit()

        flash('Password berhasil direset! Silakan login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Berhasil logout.', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/baca-notifikasi/<int:notif_id>', methods=['POST', 'GET'])
@login_required
def baca_notifikasi(notif_id):
    from app.models import Notifikasi
    notif = Notifikasi.query.get_or_404(notif_id)
    if notif.user_id == current_user.id:
        notif.is_read = True
        db.session.commit()
    next_url = request.args.get('next') or request.referrer or url_for('dashboard.index')
    return redirect(next_url)