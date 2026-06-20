import json
import os
import requests
from flask import Blueprint, jsonify

wilayah_bp = Blueprint('wilayah', __name__)

DIR = os.path.join(os.path.dirname(__file__), 'data_indonesia')
CDN = 'https://ibnux.github.io/data-indonesia'

def _load_json(path):
    full = os.path.join(DIR, path)
    if os.path.exists(full):
        with open(full, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def _save_json(path, data):
    full = os.path.join(DIR, path)
    with open(full, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

def _fetch_cdn(path):
    url = f'{CDN}/{path}'
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()

@wilayah_bp.route('/api/wilayah/provinsi')
def provinsi():
    data = _load_json('provinsi.json')
    if data is None:
        data = _fetch_cdn('provinsi.json')
        _save_json('provinsi.json', data)
    return jsonify(data)

@wilayah_bp.route('/api/wilayah/kabupaten/<prov_id>')
def kabupaten(prov_id):
    filename = f'kab_{prov_id}.json'
    data = _load_json(filename)
    if data is None:
        data = _fetch_cdn(f'kabupaten/{prov_id}.json')
        _save_json(filename, data)
    return jsonify(data)

@wilayah_bp.route('/api/wilayah/kecamatan/<kab_id>')
def kecamatan(kab_id):
    filename = f'kec_{kab_id}.json'
    data = _load_json(filename)
    if data is None:
        data = _fetch_cdn(f'kecamatan/{kab_id}.json')
        _save_json(filename, data)
    return jsonify(data)

@wilayah_bp.route('/api/wilayah/kelurahan/<kec_id>')
def kelurahan(kec_id):
    filename = f'kel_{kec_id}.json'
    data = _load_json(filename)
    if data is None:
        data = _fetch_cdn(f'kelurahan/{kec_id}.json')
        _save_json(filename, data)
    return jsonify(data)
