# 📨 **Anàlisi del microservei `notification-service`**

Perfecte, Joan.  
Ara t’explico **com funciona el servei `notification-service`**, què és **[Pika](pika.md)**, i com es relaciona tot això amb **RabbitMQ**, d’una manera clara, visual i exacta aplicada al teu projecte ShopMicro.

Cap cerca web, perquè treballem exclusivament amb el codi que m’has donat.

***

# 🐇 **1. Què és RabbitMQ? (resum curt i clar)**

RabbitMQ és un **message broker**, és a dir:

> Un servidor que rep missatges d’un microservei i els entrega a un altre, de forma asíncrona, segura i desacoblada.

En el teu cas:

*   **order-service** envia missatges → comandes creades
*   **RabbitMQ** els guarda a la *queue* `orders`
*   **notification-service** escolta aquesta queue i processa els missatges

***

# 🐍 **2. Què és Pika?**

**Pika** és una llibreria de Python que permet connectar-se a RabbitMQ.

No és RabbitMQ.  
No és una eina externa.  
És una **API client** per enviar o rebre missatges des de Python.

En el teu projecte Pika serveix per:

*   Crear connexions amb RabbitMQ
*   Declarar queues
*   Rebre missatges
*   Consumir-los de manera contínua

És l’equivalent a:

| Llenguatge | Client MQ      |
| ---------- | -------------- |
| Python     | Pika           |
| NodeJS     | amqplib        |
| Java       | Spring AMQP    |
| Go         | streadway/amqp |

***

# 📦 **3. Anàlisi del codi del `notification-service`**

Aquí tens el codi del teu servei amb comentaris:

```python
import pika, json, os, time

def callback(ch, method, properties, body):
    order = json.loads(body)
    print(f'[NOTIF] Nova comanda rebuda: {order}', flush=True)
```

👉 Aquesta funció **és cridada automàticament cada vegada que arriba un missatge**  
`body` és el missatge enviat per `order-service`.

***

## 🧠 Com s’inicia la connexió?

```python
conn = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=os.getenv('RABBITMQ_HOST', 'message-queue'),
        credentials=pika.PlainCredentials(
            os.getenv('RABBITMQ_USER', 'admin'),
            os.getenv('RABBITMQ_PASS', 'adminpass')
        )
    )
)
ch = conn.channel()
```

**Explicació:**

*   `BlockingConnection` → connexió síncrona i simple
*   `message-queue` → és el nom del servei Docker RabbitMQ
*   `ch = conn.channel()` → crea un canal AMQP (canal virtual dins la connexió)

***

## 🗃️ Declaració de la queue

```python
ch.queue_declare(queue='orders')
```

*   Si la queue existeix → la reusa
*   Si no → la crea
*   Queue: `orders`

És la mateixa queue on **order-service publica** events.

***

## 🎧 Com es posa a escoltar missatges

```python
ch.basic_consume(
    queue='orders',
    on_message_callback=callback,
    auto_ack=True
)
```

Això vol dir:

### ✔ Cada missatge que arribi a la queue `orders` executa `callback`.

### ✔ `auto_ack=True` significa:

*   RabbitMQ esborra el missatge **tan bon punt el lliura**
*   Si el teu servei cau just després… el missatge es perd

Aquest és el comportament per defecte del teu projecte educatiu, però en producció faries:

    auto_ack=False
    ch.basic_ack(delivery_tag=method.delivery_tag)

***

## ▶️ Iniciar el bucle de consum

```python
ch.start_consuming()
```

Aquí comença un **bucle infinit**:

*   espera missatges
*   quan n’arriba un → crida callback
*   torna a esperar
*   i així sempre

És com un "while True" intern.

***

# 🔄 **4. Flux complet de RabbitMQ en el teu projecte**

Aquí tens el flux visualitzat:

    CLIENT → /api/orders
          → Nginx
          → order-service
              ├── Guarda comanda a MySQL
              └── PUBLISH → RabbitMQ (queue 'orders')
                             ↓
                            RabbitMQ
                             ↓
               notification-service (consumer)
                             ↓
                 callback(order) → print([...])

***

# 📢 **5. Per què serveix tot això? (Avantatges)**

### ✔ Desacoblament total

`order-service` no sap res de `notification-service`.

### ✔ Asincronia real

Es pot enviar 1.000 comandes sense esperar la notificació.

### ✔ Alta escalabilitat

Pots afegir més notificadors sense tocar l’ordre.

### ✔ Fiabilitat

La queue manté els missatges fins que un consumer els processa.

(amb auto\_ack=False encara més segur)

***

# 🧩 **6. Resum final: què és pika i com funciona amb RabbitMQ**

| Component                | Què és                 | Paper en el teu projecte                       |
| ------------------------ | ---------------------- | ---------------------------------------------- |
| **RabbitMQ**             | Message broker         | Guarda i reparteix events de comandes          |
| **Queue 'orders'**       | Llista FIFO            | Emmagatzema les comandes pendents de processar |
| **Pika**                 | Client AMQP per Python | Fa possible connectar-se i consumir missatges  |
| **order-service**        | Producer               | Envia events → `orders`                        |
| **notification-service** | Consumer               | Rep events → mostra o processa comandes        |

***

# Vols aprofundir?

Et puc explicar:

*   🔥 Com fer `manual ack` i evitar pèrdua de missatges
*   🔄 Què són Exchanges i routing keys avançats
*   📦 Com afegir un segon consumer (analytics, email-service, etc.)
*   🚨 Què passa si RabbitMQ cau i com recuperar-se

Només demana!


Aquest microservei és *molt simple* i fa només una cosa:

*   Es connecta a **RabbitMQ**
*   Escolta una cua (`orders`)
*   Rep missatges (normalment notificacions d’una comanda creada)
*   Imprimeix el contingut

Aquí tens el codi anotat:

```python
import pika, json, os, time

def callback(ch, method, properties, body):
    order = json.loads(body)
    print(f'[NOTIF] Nova comanda rebuda: {order}', flush=True)

def start():
    time.sleep(15)  # Esperar que RabbitMQ arrenqui
    conn = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=os.getenv('RABBITMQ_HOST', 'message-queue'),
            credentials=pika.PlainCredentials(
                os.getenv('RABBITMQ_USER', 'admin'),
                os.getenv('RABBITMQ_PASS', 'adminpass')
            )
        )
    )
    ch = conn.channel()
    ch.queue_declare(queue='orders')
    ch.basic_consume(queue='orders', on_message_callback=callback, auto_ack=True)
    print('[NOTIF] Escoltant comandes...', flush=True)
    ch.start_consuming()

if __name__ == '__main__':
    start()
```

***

# 📌 **1. Aquest microservei NO utilitza Redis**

Ni fa:

*   `import redis`
*   `redis.Redis(...)`
*   `SET`, `GET`, `EXPIRE`
*   guarda caches
*   llegeix dades de cache

🔍 **Conclusió:**  
**Aquest microservei no implementa cap patró de cache.**  
Només és un *consumer* de missatges.

Redis no intervé aquí.

***

# 📌 **2. Quin patró segueix? (No és de cache, és de missatgeria)**

En realitat aquest servei segueix un patró de missatgeria:

### ✔ "Event Consumer Pattern"

Rep events d'una cua i fa una acció.

### ✔ "Fire-and-Forget event"

Order-service publica → notification-service rep.  
No hi ha resposta, ni confirmacions, ni persistència extra.

### ✔ Auto-ack

`auto_ack=True` vol dir:

*   Si aquest microservei es trenca just després de rebre un missatge → **EL MISSATGE ES PERD**.

A vegades això és acceptable, a vegades no.

***

# 📌 **3. Flux complet amb RabbitMQ (no Redis)**

    order-service  --emete-->  rabbitmq(queue=orders)  --consume--> notification-service

El patró és:

*   **Publisher**: order-service
*   **Broker**: RabbitMQ
*   **Consumer**: notification-service

***

# 📌 **4. Quin avantatge té això respecte a usar Redis?**

RabbitMQ i Redis serveixen per coses diferents:

| Objectiu                     | RabbitMQ | Redis       |
| ---------------------------- | -------- | ----------- |
| Notificació basada en events | ✔ ideal  | ✖ no tan bo |
| Fiabilitat de missatges      | ✔ sí     | ✖ no        |
| Persistència de missatges    | ✔ sí     | parcial     |
| Cache                        | ✖ no     | ✔ ideal     |

Per tant, és correcte que **aquest microservei no utilitzi Redis**.

***

# 📌 **5. Per què és així en el teu projecte?**

Perquè Redis normalment l’utilitzaràs per:

*   cache de productes (product-service)
*   login, tokens, sessions (user-service)
*   cache de comandes (order-service)

Però **no per la lògica d’events**.

Els events *ja estan resolts* amb RabbitMQ, que és el patró correcte.

***

# 📌 **6. Conclusions per ara**

*   `notification-service` **NO utilitza Redis** → no hi ha patrons de cache.
*   És un *consumer* de RabbitMQ.
*   Usa un patró molt simple i directe: **queue consumer amb auto-ack**.
*   Tot està alineat amb el patró "event-driven" del teu projecte.

***

# 📩 Si vols, puc fer:

✔ Analitzar el següent microservei (quin vols enviar ara?).  
✔ Dibuixar un diagrama complet RabbitMQ ↔ microserveis.  
✔ Comparar com quedaria si volguessis substituir RabbitMQ per Redis Streams.  
✔ Proposar millores, com *dead-letter queues*, *retry*, o *manual ack*.

Només cal que enviïs el següent microservei!
