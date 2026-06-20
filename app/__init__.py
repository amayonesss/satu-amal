from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(Config)
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Silakan login terlebih dahulu.'

    from app.auth import auth_bp
    from app.dashboard import dashboard_bp
    from app.presensi import presensi_bp
    from app.tim_manajemen import tim_manajemen_bp
    from app.relawan import relawan_bp
    from app.master import master_bp
    from app.wilayah import wilayah_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(presensi_bp)
    app.register_blueprint(tim_manajemen_bp)
    app.register_blueprint(relawan_bp)
    app.register_blueprint(master_bp)
    app.register_blueprint(wilayah_bp)      

    @app.context_processor
    def inject_notifications():
        from app.models import Notifikasi
        from flask_login import current_user
        from datetime import datetime
        if current_user.is_authenticated:
            unread_notifications = Notifikasi.query.filter_by(user_id=current_user.id, is_read=False).order_by(Notifikasi.created_at.desc()).all()
            return dict(unread_notifications=unread_notifications, current_year=datetime.now().year)
        return dict(unread_notifications=[], current_year=datetime.now().year)

    @app.route('/')
    def index():
        from flask import redirect, url_for
        return redirect(url_for('auth.login'))

    return app