from flask import render_template, request, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from app.presensi import presensi_bp
from app.models import User, Presensi, Program, Notifikasi, FotoKegiatan
from app import db
from datetime import datetime, date, timedelta
import base64
import os
import json
import uuid
import numpy as np
import cv2
import face_recognition
from werkzeug.utils import secure_filename

from app.liveness import analyze_liveness

FACE_AVAILABLE = True
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@presensi_bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(current_app.config['KEGIATAN_FOLDER'], filename)


@presensi_bp.route('/')
@login_required
def index():
    presensi_list = Presensi.query.filter_by(
        user_id=current_user.id,
        tanggal=date.today()
    ).order_by(Presensi.jam_masuk).all()

    programs = Program.query.filter(
        Program.tanggal_pelaksanaan == date.today()
    ).order_by(Program.nama_program).all()

    return render_template('presensi/index.html',
        presensi_list=presensi_list,
        programs=programs
    )


@presensi_bp.route('/upload-foto', methods=['POST'])
@login_required
def upload_foto():
    program_id = request.form.get('program_id') or 0
    if program_id:
        program_id = int(program_id)
    file = request.files.get('file')

    if not program_id:
        return jsonify({'success': False, 'message': 'Program harus dipilih.'})

    program = Program.query.get(program_id)
    if not program:
        return jsonify({'success': False, 'message': 'Program tidak ditemukan.'})

    if not file or file.filename == '':
        return jsonify({'success': False, 'message': 'Pilih file foto terlebih dahulu.'})

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'message': 'Format file tidak didukung. Gunakan PNG, JPG, JPEG, GIF, atau WebP.'})

    try:
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{current_user.kode_relawan}_{program_id}_{uuid.uuid4().hex[:8]}.{ext}"
        upload_dir = current_app.config['KEGIATAN_FOLDER']
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)

        presensi = Presensi.query.filter_by(
            user_id=current_user.id,
            program_id=program_id,
            tanggal=date.today(),
            jam_keluar=None
        ).order_by(Presensi.jam_masuk.desc()).first()

        foto = FotoKegiatan(
            user_id=current_user.id,
            program_id=program_id,
            presensi_id=presensi.id if presensi else None,
            file_path=filename
        )
        db.session.add(foto)
        db.session.commit()

        total = FotoKegiatan.query.filter_by(
            user_id=current_user.id,
            program_id=program_id,
            tanggal=date.today()
        ).count()

        return jsonify({
            'success': True,
            'message': 'Foto berhasil diupload.',
            'filename': filename,
            'total': total
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Gagal upload: {str(e)}'})


@presensi_bp.route('/cek-foto', methods=['POST'])
@login_required
def cek_foto():
    data = request.get_json()
    program_id = data.get('program_id') or 0
    if program_id:
        program_id = int(program_id)

    if not program_id:
        return jsonify({'success': False, 'count': 0})

    total = FotoKegiatan.query.filter_by(
        user_id=current_user.id,
        program_id=program_id,
        tanggal=date.today()
    ).count()

    return jsonify({'success': True, 'count': total, 'required': 4})


@presensi_bp.route('/scan', methods=['POST'])
@login_required
def scan_wajah():
    data         = request.get_json()
    nama_program = data.get('nama_program', '')
    program_id   = data.get('program_id') or None
    if program_id:
        program_id = int(program_id)
    foto_base64  = data.get('image', '')
    blink_verified = data.get('blink_verified', False)

    if not nama_program:
        return jsonify({'success': False, 'message': 'Program harus dipilih.'})

    if not current_user.face_encoding:
        return jsonify({'success': False, 'message': 'Anda belum mendaftarkan wajah! Silakan klik tombol Daftar Wajah Saya.'})

    if not foto_base64:
        return jsonify({'success': False, 'message': 'Gagal mengambil gambar dari kamera.'})

    if not blink_verified:
        return jsonify({
            'success': False,
            'message': 'Liveness gagal: kedipan mata tidak terdeteksi. Silakan kedipkan mata di depan kamera.'
        })

    try:
        header, encoded = foto_base64.split(",", 1)
        img_data = base64.b64decode(encoded)
        nparr    = np.frombuffer(img_data, np.uint8)
        img      = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        rgb_img  = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        liveness_result = analyze_liveness(img)
        if not liveness_result['is_live']:
            return jsonify({
                'success': False,
                'message': f"Anti-spoofing gagal: {liveness_result['reason']} (skor: {liveness_result['score']})"
            })

        face_locations = face_recognition.face_locations(rgb_img, model='hog')
        if len(face_locations) == 0:
            return jsonify({'success': False, 'message': 'Wajah tidak terdeteksi. Harap hadap kamera dengan jelas dan pencahayaan cukup.'})
        if len(face_locations) > 1:
            return jsonify({'success': False, 'message': 'Terdeteksi lebih dari 1 wajah. Pastikan hanya Anda yang ada di depan kamera.'})

        face_encodings = face_recognition.face_encodings(rgb_img, face_locations)
        if len(face_encodings) == 0:
            return jsonify({'success': False, 'message': 'Gagal mengekstrak fitur wajah.'})

        TOLERANCE      = 0.42
        saved_encoding = np.array(json.loads(current_user.face_encoding))

        matches  = face_recognition.compare_faces([saved_encoding], face_encodings[0], tolerance=TOLERANCE)
        distance = face_recognition.face_distance([saved_encoding], face_encodings[0])[0]

        if not matches[0] or distance > TOLERANCE:
            return jsonify({
                'success': False,
                'message': 'Wajah tidak cocok! Pastikan pencahayaan cukup dan wajah menghadap lurus ke kamera.'
            })

        presensi = Presensi.query.filter_by(
            user_id=current_user.id,
            tanggal=date.today(),
            nama_program=nama_program
        ).order_by(Presensi.jam_masuk.desc()).first()

        now = datetime.now()

        if presensi is None or presensi.jam_keluar is not None or presensi.status == 'ditolak':
            presensi_baru = Presensi(
                user_id      = current_user.id,
                program_id   = program_id,
                tanggal      = date.today(),
                jam_masuk    = now,
                status       = 'pending',
                nama_program = nama_program,
                metode       = 'face'
            )
            db.session.add(presensi_baru)
            db.session.flush()

            admins = User.query.filter(User.role.in_(['admin', 'tim_manajemen'])).all()
            for adm in admins:
                notif = Notifikasi(
                    user_id=adm.id,
                    pesan=f"Relawan {current_user.nama} telah melakukan presensi untuk program '{nama_program}'. Mohon segera disetujui."
                )
                db.session.add(notif)

            db.session.commit()
            return jsonify({
                'success': True,
                'message': f'Presensi Masuk [{nama_program}] dicatat pukul {now.strftime("%H:%M:%S")}. Menunggu verifikasi Admin.',
                'is_check_out': False
            })

        else:
            if not presensi.program_id:
                return jsonify({'success': False, 'message': 'Data program tidak valid.'})

            foto_count = FotoKegiatan.query.filter_by(
                user_id=current_user.id,
                program_id=presensi.program_id,
                tanggal=date.today()
            ).count()
            if foto_count < 4:
                return jsonify({
                    'success': False,
                    'message': f'Anda harus upload minimal 4 foto kegiatan terlebih dahulu sebelum absen keluar. Saat ini: {foto_count}/4.',
                    'need_photos': True
                })

            presensi.jam_keluar = now
            if presensi.jam_masuk:
                delta = (now - presensi.jam_masuk).total_seconds() / 3600
                presensi.total_jam = round(delta, 2)
            db.session.commit()
            return jsonify({
                'success': True,
                'message': f'Presensi Keluar [{nama_program}] pukul {now.strftime("%H:%M:%S")} | Total: {presensi.total_jam} jam',
                'is_check_out': True
            })

    except Exception as e:
        return jsonify({'success': False, 'message': f'Terjadi kesalahan server: {str(e)}'})


@presensi_bp.route('/foto-presensi/<int:presensi_id>')
@login_required
def foto_presensi(presensi_id):
    presensi = Presensi.query.get_or_404(presensi_id)

    if current_user.role not in ['admin', 'tim_manajemen'] and current_user.id != presensi.user_id:
        return jsonify({'success': False, 'message': 'Akses ditolak.'})

    photos = FotoKegiatan.query.filter_by(presensi_id=presensi_id).order_by(FotoKegiatan.created_at).all()

    return jsonify({
        'success': True,
        'relawan': presensi.user.nama,
        'program': presensi.nama_program,
        'tanggal': presensi.tanggal.strftime('%d %B %Y'),
        'photos': [{'id': f.id, 'url': f'/presensi/uploads/{f.file_path}'} for f in photos]
    })


@presensi_bp.route('/daftar-wajah', methods=['POST'])
@login_required
def daftar_wajah():
    data        = request.get_json()
    foto_base64 = data.get('image', '')

    if not foto_base64:
        return jsonify({'success': False, 'message': 'Gagal mengambil gambar dari kamera.'})

    try:
        header, encoded = foto_base64.split(",", 1)
        img_data = base64.b64decode(encoded)
        nparr    = np.frombuffer(img_data, np.uint8)
        img      = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        rgb_img  = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(rgb_img, model='hog')
        if len(face_locations) == 0:
            return jsonify({'success': False, 'message': 'Wajah tidak terdeteksi. Harap hadap kamera dengan jelas dan pencahayaan cukup.'})
        elif len(face_locations) > 1:
            return jsonify({'success': False, 'message': 'Terdeteksi lebih dari 1 wajah! Pastikan hanya Anda di depan kamera.'})

        face_encodings = face_recognition.face_encodings(rgb_img, face_locations)
        if len(face_encodings) > 0:
            encoding = face_encodings[0].tolist()
            current_user.face_encoding = json.dumps(encoding)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Wajah berhasil didaftarkan! Silakan coba Scan Presensi.'})
        else:
            return jsonify({'success': False, 'message': 'Gagal mengekstrak fitur wajah.'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Terjadi kesalahan server: {str(e)}'})
