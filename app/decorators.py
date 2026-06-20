from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user
from app.models import TimAkses

def role_required(*roles):
    """Hanya role tertentu yang boleh akses route ini."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles:
                flash('Anda tidak punya akses ke halaman ini.', 'danger')
                return redirect(url_for('dashboard.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def crud_required(f):
    """Hanya admin, atau tim manajemen yang diberi izin CRUD."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role == 'admin':
            return f(*args, **kwargs)
        if current_user.role == 'tim_manajemen':
            akses = TimAkses.query.filter_by(
                user_id=current_user.id,
                akses_crud=True
            ).first()
            if akses:
                return f(*args, **kwargs)
        abort(403)
    return decorated_function