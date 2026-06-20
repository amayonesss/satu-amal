from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id            = db.Column(db.Integer, primary_key=True)
    kode_relawan  = db.Column(db.String(20), unique=True, nullable=False)
    nama          = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    reset_token   = db.Column(db.String(100), nullable=True)
    reset_token_exp = db.Column(db.DateTime, nullable=True)
    role            = db.Column(db.String(20), nullable=False, default='relawan')
    foto_wajah      = db.Column(db.String(200), nullable=True)
    face_encoding   = db.Column(db.Text, nullable=True)  # Menyimpan vektor wajah (JSON string)
    aktif           = db.Column(db.Boolean, default=True)
    created_at      = db.Column(db.DateTime, default=datetime.now)
   
    presensi  = db.relationship('Presensi', backref='user', lazy=True)
    keaktifan = db.relationship('Keaktifan', backref='user', uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.kode_relawan} - {self.nama}>'

class TimAkses(db.Model):
    __tablename__ = 'tim_akses'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    akses_crud = db.Column(db.Boolean, default=False)  # True = boleh CRUD relawan & program
    diberikan_oleh = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    user  = db.relationship('User', foreign_keys=[user_id], backref='tim_akses')
    admin = db.relationship('User', foreign_keys=[diberikan_oleh])

class Keaktifan(db.Model):
    __tablename__ = 'keaktifan'

    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    jumlah_kehadiran = db.Column(db.Integer, default=0)
    total_manhours   = db.Column(db.Float, default=0.0)
    updated_at       = db.Column(db.DateTime, default=datetime.now)


class Program(db.Model):
    __tablename__ = 'program'

    id                      = db.Column(db.Integer, primary_key=True)
    nama_program            = db.Column(db.String(200), nullable=False)
    kategori                = db.Column(db.String(100), nullable=True)
    bulan                   = db.Column(db.String(20), nullable=True)
    tahun                   = db.Column(db.Integer, nullable=True)
    tanggal_pelaksanaan     = db.Column(db.Date, nullable=True)  # Tanggal spesifik pelaksanaan (opsional)
    lokasi                  = db.Column(db.String(200), nullable=True)
    jumlah_relawan          = db.Column(db.Integer, default=0)
    jumlah_penerima_manfaat = db.Column(db.Integer, default=0)
    nama_tempat = db.Column(db.String(200), nullable=True)
    kecamatan   = db.Column(db.String(100), nullable=True)
    kelurahan   = db.Column(db.String(100), nullable=True)
    kota        = db.Column(db.String(100), nullable=True)
    provinsi    = db.Column(db.String(100), nullable=True)
    lama_kegiatan_menit = db.Column(db.Integer, nullable=True)


class Presensi(db.Model):
    __tablename__ = 'presensi'

    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    program_id    = db.Column(db.Integer, db.ForeignKey('program.id'), nullable=True)
    tanggal       = db.Column(db.Date, nullable=False, default=datetime.now)
    jam_masuk     = db.Column(db.DateTime, nullable=True)
    jam_keluar    = db.Column(db.DateTime, nullable=True)
    total_jam     = db.Column(db.Float, default=0.0)
    metode        = db.Column(db.String(20), default='face')
    status        = db.Column(db.String(20), default='hadir')
    nama_program  = db.Column(db.String(200), nullable=True) # Tetap dipertahankan untuk backward compatibility
    foto_presensi = db.Column(db.String(200), nullable=True)
    created_at    = db.Column(db.DateTime, default=datetime.now)
    
    program = db.relationship('Program', backref='presensi_list')

class Notifikasi(db.Model):
    __tablename__ = 'notifikasi'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    pesan      = db.Column(db.String(255), nullable=False)
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    user = db.relationship('User', foreign_keys=[user_id], backref='notifikasi_list')

class KoordinatorProgram(db.Model):
    __tablename__ = 'koordinator_program'

    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    ditunjuk_oleh = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    program = db.relationship('Program', backref='koordinator_list')
    user = db.relationship('User', foreign_keys=[user_id], backref='tugas_koordinator')

class EvaluasiProgram(db.Model):
    __tablename__ = 'evaluasi_program'

    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    jumlah_pm_aktual = db.Column(db.Integer, default=0)
    catatan_keberhasilan = db.Column(db.Text, nullable=True)
    kendala_lapangan = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    program = db.relationship('Program', backref='evaluasi_list')
    admin = db.relationship('User', foreign_keys=[admin_id], backref='evaluasi_dibuat')

class FotoKegiatan(db.Model):
    __tablename__ = 'foto_kegiatan'

    id         = db.Column(db.Integer, primary_key=True)
    presensi_id = db.Column(db.Integer, db.ForeignKey('presensi.id'), nullable=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id'), nullable=True)
    file_path  = db.Column(db.String(200), nullable=False)
    tanggal    = db.Column(db.Date, default=datetime.now)
    created_at = db.Column(db.DateTime, default=datetime.now)

    user     = db.relationship('User', backref='foto_kegiatan')
    program  = db.relationship('Program', backref='foto_kegiatan')
    presensi = db.relationship('Presensi', backref='foto_kegiatan')
