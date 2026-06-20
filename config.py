import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'satu-amal-secret-key-2025'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://root:@localhost/satu_amal'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads', 'faces')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    KEGIATAN_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads', 'kegiatan')
      # Konfigurasi Email
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'ameldwiputri14@gmail.com'
    MAIL_PASSWORD = 'qvtj rjav zyzu kild'
    MAIL_DEFAULT_SENDER = 'ameldwiputri14@gmail.com'