# ~/shopmicro/notification-service/app.py
import pika, json, os, time

def callback(ch, method, properties, body):
    order = json.loads(body)
    print(f'[NOTIF] Nova comanda rebuda: {order}', flush=True)

def start():
    time.sleep(15)  # Esperar que RabbitMQ arrenqui
    conn = pika.BlockingConnection(pika.ConnectionParameters(host=os.getenv('RABBITMQ_HOST', 'message-queue'),credentials=pika.PlainCredentials(os.getenv('RABBITMQ_USER', 'admin'),os.getenv('RABBITMQ_PASS', 'adminpass'))))
    ch = conn.channel()
    ch.queue_declare(queue='orders')
    ch.basic_consume(queue='orders', on_message_callback=callback, auto_ack=True)
    print('[NOTIF] Escoltant comandes...', flush=True)
    ch.start_consuming()

if __name__ == '__main__': start()
