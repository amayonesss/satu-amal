from flask import Blueprint

presensi_bp = Blueprint('presensi', __name__, url_prefix='/presensi')

from app.presensi import routes