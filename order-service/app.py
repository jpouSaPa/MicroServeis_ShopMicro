from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import pika, json, os, time, datetime

app = Flask(__name__)

# ─── Config MySQL amb secrets ─────────────────────────────────
def load_db_password():
    path = os.environ.get("DB_PASSWORD_FILE")
    if path and os.path.exists(path):
        with open(path, "r") as f:
            return f.read().strip()
    return None

db_password = load_db_password()
db_host = os.environ.get("DB_HOST", "db-orders")
db_name = os.environ.get("DB_NAME", "ordersdb")

DATABASE_URL = f"mysql+pymysql://root:{db_password}@{db_host}:3306/{db_name}"

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
db = SQLAlchemy(app)


# ─── Model ──────────────────────────────────────────────
class Order(db.Model):
    __tablename__ = 'orders'

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id = db.Column(db.Integer, nullable=True)
    user_id    = db.Column(db.Integer, nullable=True)
    quantity   = db.Column(db.Integer, nullable=True)
    data       = db.Column(db.Text, nullable=False)        # JSON complet de la comanda
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        base = json.loads(self.data)
        base['id']         = self.id
        base['created_at'] = self.created_at.isoformat()
        return base


# ─── Init BD (amb reintents per si MySQL triga a arrencar) ──
def init_db():
    retries = 10
    for i in range(retries):
        try:
            with app.app_context():
                db.create_all()
            print('[ORDER] BD inicialitzada correctament', flush=True)
            return
        except Exception as e:
            print(f'[ORDER] Esperant MySQL... ({i+1}/{retries}): {e}', flush=True)
            time.sleep(3)
    raise RuntimeError('No s\'ha pogut connectar a MySQL')


# ─── RabbitMQ helper ────────────────────────────────────
def publish_order(order_dict):
    try:
        conn = pika.BlockingConnection(pika.ConnectionParameters(
            host=os.getenv('RABBITMQ_HOST', 'message-queue'),
            credentials=pika.PlainCredentials(
                os.getenv('RABBITMQ_USER', 'admin'),
                os.getenv('RABBITMQ_PASS', 'adminpass')
            )
        ))
        ch = conn.channel()
        ch.queue_declare(queue='orders')
        ch.basic_publish(exchange='', routing_key='orders', body=json.dumps(order_dict))
        conn.close()
    except Exception as e:
        print(f'[ORDER] Error publicant a RabbitMQ: {e}', flush=True)


# ─── Routes ─────────────────────────────────────────────
@app.route('/orders', methods=['POST'])
def create_order():
    payload = request.json
    if not payload:
        return jsonify({'error': 'No data provided'}), 400

    order = Order(
        product_id = payload.get('product_id'),
        user_id    = payload.get('user_id'),
        quantity   = payload.get('quantity'),
        data       = json.dumps(payload)
    )
    db.session.add(order)
    db.session.commit()

    order_dict = order.to_dict()
    publish_order(order_dict)

    return jsonify({'status': 'order_created', 'order': order_dict}), 201


@app.route('/orders', methods=['GET'])
def get_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return jsonify({'orders': [o.to_dict() for o in orders], 'total': len(orders)}), 200


@app.route('/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    order = Order.query.get(order_id)
    if not order:
        return jsonify({'error': 'Comanda no trobada'}), 404
    return jsonify(order.to_dict()), 200


@app.route('/health')
def health():
    try:
        db.session.execute(db.text('SELECT 1'))
        db_status = 'ok'
    except Exception:
        db_status = 'error'
    return jsonify({'status': 'ok', 'db': db_status}), 200


# ─── Arrencada ──────────────────────────────────────────
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
