from flask import Blueprint

relawan_bp = Blueprint('relawan', __name__, url_prefix='/relawan')

from app.relawan import routes