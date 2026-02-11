from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from datetime import timedelta
from dotenv import load_dotenv
import os
import logging

from models import db, init_all_models
from admin_routes import admin_bp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

env_path = os.path.join(PROJECT_ROOT, '.env')
load_dotenv(env_path)

app = Flask(__name__,
            template_folder='views',
            static_folder=None,
            static_url_path='')

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)
app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', 'False') == 'True'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['WTF_CSRF_TIME_LIMIT'] = None

csrf = CSRFProtect(app)

allowed_origins = os.getenv('ALLOWED_ORIGINS', '*').split(',')
CORS(app, origins=allowed_origins, supports_credentials=True)

if os.path.exists(os.path.join(BASE_DIR, 'data')):
    data_dir = os.path.join(BASE_DIR, 'data')
else:
    data_dir = os.path.join(PROJECT_ROOT, 'data')

os.makedirs(data_dir, exist_ok=True)

security_log_path = os.path.join(data_dir, 'security.log')
if not os.path.exists(security_log_path):
    open(security_log_path, 'a').close()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(security_log_path),
        logging.StreamHandler()
    ]
)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(data_dir, "app.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
app.register_blueprint(admin_bp)

_db_initialized = False

def init_db():
    global _db_initialized
    if not _db_initialized:
        with app.app_context():
            init_all_models()
        _db_initialized = True

@app.before_request
def before_first_request():
    init_db()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_spa(path):
    if path.startswith('admin'):
        return redirect('/admin/panel')
    return jsonify({'error': 'Not Found'}), 404

@app.errorhandler(404)
def not_found_error(error):
    if request.path.startswith('/admin/api/'):
        return jsonify({
            'error': 'Not Found',
            'message': 'The requested resource was not found',
            'path': request.path
        }), 404

    return serve_spa(request.path.lstrip('/'))

@app.errorhandler(500)
def internal_error(error):
    security_logger = logging.getLogger('security')
    security_logger.error(f"Internal server error: {str(error)}")

    if request.path.startswith('/admin/api/'):
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500

    return jsonify({
        'error': 'Internal Server Error',
        'message': 'An unexpected error occurred'
    }), 500

@app.errorhandler(403)
def forbidden_error(error):
    if request.path.startswith('/admin/api/'):
        return jsonify({
            'error': 'Forbidden',
            'message': 'Access denied'
        }), 403

    return redirect('/admin/login')

if __name__ == '__main__':
    with app.app_context():
        init_all_models()
    debug_mode = os.getenv('FLASK_DEBUG', 'False') == 'True'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
