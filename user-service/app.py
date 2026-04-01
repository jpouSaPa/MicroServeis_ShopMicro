from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import os
import time
from functools import wraps

app = Flask(__name__)

# ───────────────────────────────────────────────
# CONFIGURACIÓ AMB DOCKER SECRETS
# ───────────────────────────────────────────────

def load_secret(path):
    """Llegeix un fitxer secret si existeix"""
    if path and os.path.exists(path):
        with open(path, "r") as f:
            return f.read().strip()
    return None

# 1) SECRET_KEY (JWT)
secret_key_file = os.environ.get("SECRET_KEY_FILE")
secret_key = load_secret(secret_key_file) or os.environ.get("SECRET_KEY") or "dev-secret"
app.config["SECRET_KEY"] = secret_key

# 2) PASSWORD MYSQL
db_password_file = os.environ.get("DB_PASSWORD_FILE")
db_password = load_secret(db_password_file)

db_host = os.environ.get("DB_HOST", "db-users")
db_name = os.environ.get("DB_NAME", "usersdb")

DATABASE_URL = f"mysql+pymysql://root:{db_password}@{db_host}:3306/{db_name}"

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
app.config["JWT_EXPIRATION_HOURS"] = int(os.environ.get('JWT_EXPIRATION_HOURS', 24))
db = SQLAlchemy(app)

# ───────────────────────────────────────────────
# MODEL USER
# ───────────────────────────────────────────────

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active
        }

# ───────────────────────────────────────────────
# JWT HELPERS
# ───────────────────────────────────────────────

def generate_token(user_id):
    payload = {
        'sub': user_id,
        'iat': datetime.datetime.utcnow(),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=app.config['JWT_EXPIRATION_HOURS'])
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')

        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]

        if not token:
            return jsonify({'error': 'Token missing'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['sub'])

            if not current_user or not current_user.is_active:
                return jsonify({'error': 'User not found or inactive'}), 401

        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        return f(current_user, *args, **kwargs)
    return decorated


# ───────────────────────────────────────────────
# DB INIT — AMB REINTENTS (com order-service)
# ───────────────────────────────────────────────

def init_db():
    retries = 10
    for i in range(retries):
        try:
            with app.app_context():
                db.create_all()
            print('[USER] BD inicialitzada correctament', flush=True)
            return
        except Exception as e:
            print(f'[USER] Esperant MySQL... ({i+1}/{retries}): {e}', flush=True)
            time.sleep(3)
    raise RuntimeError("No s'ha pogut connectar a MySQL")

init_db()


# ───────────────────────────────────────────────
# ENDPOINTS
# ───────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify({'status': 'ok', 'service': 'user-service', 'db': 'ok'}), 200
    except:
        return jsonify({'status': 'ok', 'service': 'user-service', 'db': 'error'}), 500


@app.route('/register', methods=['POST'])
def register():
    import socket
    print(f'[REGISTER] Atès per {socket.gethostname()}', flush=True)

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not username or not email or not password:
        return jsonify({'error': 'username, email and password are required'}), 400
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already taken'}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409

    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password, method='pbkdf2:sha256')
    )
    db.session.add(user)
    db.session.commit()

    token = generate_token(user.id)
    return jsonify({'message': 'User created', 'user': user.to_dict(), 'token': token}), 201


@app.route('/login', methods=['POST'])
def login():
    import socket
    print(f'[LOGIN] Atès per {socket.gethostname()}', flush=True)

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'email and password are required'}), 400

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Invalid credentials'}), 401
    if not user.is_active:
        return jsonify({'error': 'Account disabled'}), 403

    token = generate_token(user.id)
    return jsonify({'token': token, 'user': user.to_dict()}), 200


@app.route('/me', methods=['GET'])
@token_required
def get_me(current_user):
    return jsonify({'user': current_user.to_dict()}), 200


@app.route('/me', methods=['PUT'])
@token_required
def update_me(current_user):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    if 'username' in data:
        new_username = data['username'].strip()
        existing = User.query.filter_by(username=new_username).first()
        if existing and existing.id != current_user.id:
            return jsonify({'error': 'Username already taken'}), 409
        current_user.username = new_username

    if 'password' in data:
        if len(data['password']) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        current_user.password_hash = generate_password_hash(data['password'], method='pbkdf2:sha256')

    db.session.commit()
    return jsonify({'message': 'User updated', 'user': current_user.to_dict()}), 200


@app.route('/me', methods=['DELETE'])
@token_required
def delete_me(current_user):
    current_user.is_active = False
    db.session.commit()
    return jsonify({'message': 'Account deactivated'}), 200

@app.route('/admin/enable', methods=['POST'])
def admin_enable_user():
    data = request.get_json()
    if not data or 'email' not in data:
        return jsonify({'error': 'email is required'}), 400

    email = data['email'].strip().lower()

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({'error': 'User not found'}), 404

    user.is_active = True
    db.session.commit()

    return jsonify({
        'status': 'user_enabled',
        'user': user.to_dict()
    }), 200

# ───────────────────────────────────────────────
# ARRANCADA
# ───────────────────────────────────────────────

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)
