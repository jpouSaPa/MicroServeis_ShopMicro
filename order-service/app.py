from flask import Flask, jsonify, request
import pika, json, os

app = Flask(__name__)

# Emmagatzematge en memòria (substitueix per una BD real si cal)
orders_store = []

@app.route('/orders', methods=['POST'])
def create_order():
    order = request.json
    order['id'] = len(orders_store) + 1

    # Guardar localment
    orders_store.append(order)

    # Publicar missatge a RabbitMQ
    conn = pika.BlockingConnection(pika.ConnectionParameters(
        host=os.getenv('RABBITMQ_HOST', 'message-queue'),
        credentials=pika.PlainCredentials(
            os.getenv('RABBITMQ_USER', 'admin'),
            os.getenv('RABBITMQ_PASS', 'adminpass')
        )
    ))
    ch = conn.channel()
    ch.queue_declare(queue='orders')
    ch.basic_publish(exchange='', routing_key='orders', body=json.dumps(order))
    conn.close()
    return jsonify({'status': 'order_created', 'order': order}), 201


@app.route('/orders', methods=['GET'])
def get_orders():
    """Retorna totes les comandes emmagatzemades."""
    return jsonify({'orders': orders_store, 'total': len(orders_store)}), 200


@app.route('/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    """Retorna una comanda per ID."""
    order = next((o for o in orders_store if o.get('id') == order_id), None)
    if not order:
        return jsonify({'error': 'Comanda no trobada'}), 404
    return jsonify(order), 200


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
