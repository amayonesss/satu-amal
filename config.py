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
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'ameldwiputri14@gmail.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'qvtj rjav zyzu kild'
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or MAIL_USERNAME