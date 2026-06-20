from flask import Blueprint

tim_manajemen_bp = Blueprint('tim_manajemen', __name__, url_prefix='/tim-manajemen')

from app.tim_manajemen import routes