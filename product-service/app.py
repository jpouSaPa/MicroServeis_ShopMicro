from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import redis, json, os, datetime

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────
#  CONFIGURACIÓ BASE DE DADES (MySQL) AMB DOCKER SECRETS
# ─────────────────────────────────────────────────────────────
import os

# 1) Llegir la contrasenya del fitxer secret
def load_db_password():
    path = os.environ.get("DB_PASSWORD_FILE")
    if path and os.path.exists(path):
        with open(path, "r") as f:
            return f.read().strip()
    return None

db_password = load_db_password()

# 2) Variables configurables
db_host = os.environ.get("DB_HOST", "db-products")
db_name = os.environ.get("DB_NAME", "productsdb")

# 3) Construir DATABASE_URL definitivament
DATABASE_URL = f"mysql+pymysql://root:{db_password}@{db_host}:3306/{db_name}"

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}
db = SQLAlchemy(app)

# ─────────────────────────────────────────────────────────────
#  CONFIGURACIÓ REDIS (CACHE)
# ─────────────────────────────────────────────────────────────

r = redis.Redis(
    host=os.getenv('REDIS_HOST', 'cache'),
    port=6379,
    decode_responses=True
)

CACHE_TTL = 60  # segons


# ─────────────────────────────────────────────────────────────
#  MODEL DE PRODUCTE
# ─────────────────────────────────────────────────────────────

class Product(db.Model):
    __tablename__ = 'products'

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name       = db.Column(db.String(200), nullable=False)
    price      = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'created_at': self.created_at.isoformat()
        }


# ─────────────────────────────────────────────────────────────
#  INIT DB (només primer cop)
# ─────────────────────────────────────────────────────────────

_initialized = False

@app.before_request
def init_db():
    global _initialized
    if not _initialized:
        db.create_all()
        _initialized = True


# ─────────────────────────────────────────────────────────────
#  FUNCIONS DE CACHE
# ─────────────────────────────────────────────────────────────

def cache_get_product(product_id):
    data = r.get(f"product:{product_id}")
    return json.loads(data) if data else None

def cache_set_product(product):
    r.setex(f"product:{product['id']}", CACHE_TTL, json.dumps(product))

def cache_delete_product(product_id):
    r.delete(f"product:{product_id}")

def cache_get_list():
    data = r.get("products:list")
    return json.loads(data) if data else None

def cache_set_list(products):
    r.setex("products:list", CACHE_TTL, json.dumps(products))

def cache_delete_list():
    r.delete("products:list")


# ─────────────────────────────────────────────────────────────
#  GET /products (llista → amb cache)
# ─────────────────────────────────────────────────────────────

@app.route('/products', methods=['GET'])
def list_products():
    cached = cache_get_list()
    if cached:
        return jsonify({'source': 'cache', 'data': cached})

    # Consulta MySQL
    products = Product.query.order_by(Product.created_at.desc()).all()
    data = [p.to_dict() for p in products]

    cache_set_list(data)

    return jsonify({'source': 'db', 'data': data})


# ─────────────────────────────────────────────────────────────
#  GET /products/<id> (producte → amb cache)
# ─────────────────────────────────────────────────────────────

@app.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    # 1️⃣ Intentar cache
    cached = cache_get_product(product_id)
    if cached:
        return jsonify({'source': 'cache', 'data': cached})

    # 2️⃣ Si no existeix → MySQL
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'error': 'Producte no trobat'}), 404

    data = product.to_dict()

    # 3️⃣ Guardar a cache
    cache_set_product(data)

    return jsonify({'source': 'db', 'data': data})


# ─────────────────────────────────────────────────────────────
#  POST /products (crear producte)
# ─────────────────────────────────────────────────────────────

@app.route('/products', methods=['POST'])
def create_product():
    data = request.get_json()

    if not data or 'name' not in data or 'price' not in data:
        return jsonify({'error': 'Cal name i price'}), 400

    product = Product(
        name=data['name'],
        price=float(data['price'])
    )
    db.session.add(product)
    db.session.commit()

    p_dict = product.to_dict()

    # Actualitzar cache
    cache_set_product(p_dict)
    cache_delete_list()  # Perquè la llista ha canviat

    return jsonify({'status': 'product_created', 'product': p_dict}), 201


# ─────────────────────────────────────────────────────────────
#  PUT /products/<id> (actualitzar)
# ─────────────────────────────────────────────────────────────

@app.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    product = Product.query.get(product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404

    if 'name' in data:
        product.name = data['name']
    if 'price' in data:
        product.price = float(data['price'])

    db.session.commit()

    p_dict = product.to_dict()

    # Actualitzar cache
    cache_set_product(p_dict)
    cache_delete_list()

    return jsonify({'status': 'product_updated', 'product': p_dict}), 200


# ─────────────────────────────────────────────────────────────
#  DELETE /products/<id> (eliminar)
# ─────────────────────────────────────────────────────────────

@app.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404

    db.session.delete(product)
    db.session.commit()

    # Netejar cache
    cache_delete_product(product_id)
    cache_delete_list()

    return jsonify({'status': 'product_deleted'}), 200


# ─────────────────────────────────────────────────────────────
#  HEALTHCHECK
# ─────────────────────────────────────────────────────────────

@app.route('/health')
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify({'status': 'ok', 'db': 'ok'}), 200
    except:
        return jsonify({'status': 'ok', 'db': 'error'}), 500


# ─────────────────────────────────────────────────────────────
#  ARRANCADA
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
