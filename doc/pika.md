Perfecte, Joan! T’explico **què és Pika** de manera clara i exacta, adaptada al teu projecte.

***

# 🐍 **Què és Pika?**

**Pika és una llibreria de Python** que permet comunicar-se amb **RabbitMQ** utilitzant el protocol **AMQP** (Advanced Message Queuing Protocol).

➡️ Pika **no és RabbitMQ**  
➡️ Pika **no és un servidor**  
➡️ Pika és **el client de AMQP per Python**

És l’eina que fan servir els teus microserveis en Python per:

*   Connectar-se al servidor RabbitMQ
*   Enviar missatges a queues
*   Rebre missatges de queues
*   Crear canals, declarar queues i gestionar missatges

***

# 📦 **Per què s’utilitza Pika?**

Perquè quan tens un microservei Python que necessita enviar o escoltar missatges RabbitMQ, Pika és l’opció més simple i oficialment recomanada per Python.

Funciona molt bé per:

*   microserveis petits (com el teu `order-service`)
*   consumidors simples (com el teu `notification-service`)
*   connexions síncrones

***

# 🔧 **Com funciona Pika per dins?**

Quan fas:

```python
import pika
```

Pika et dona classes per crear:

## ✔ Conexions

Com aquesta:

```python
conn = pika.BlockingConnection(pika.ConnectionParameters(host='message-queue'))
```

Això obre un socket amb RabbitMQ.

***

## ✔ Canals

Després de connectar, cal obrir un canal:

```python
ch = conn.channel()
```

El **canal** és on realment envíes o reps missatges.  
Una connexió pot tenir molts canals → lleugers i ràpids.

***

## ✔ Declaració de queues

Pika pot assegurar-se que una queue existeix:

```python
ch.queue_declare(queue='orders')
```

Si no existeix → la crea.  
Si existeix → la reusa.

***

## ✔ Publicar missatges

Aquest és el teu `order-service` enviant missatges:

```python
ch.basic_publish(
    exchange='',
    routing_key='orders',
    body=json.dumps(order_dict)
)
```

➡️ Això envia un missatge a la **queue `orders`** dins RabbitMQ.

***

## ✔ Rebre missatges (consume)

Aquest és el teu `notification-service`:

```python
ch.basic_consume(
    queue='orders',
    on_message_callback=callback,
    auto_ack=True
)
ch.start_consuming()
```

Pika aquí fa:

*   es registra com a “listener” de la queue `orders`
*   quan arriba un missatge → executa `callback`
*   continua escoltant en un bucle infinit

***

# 🤝 **Com encaixa Pika en el teu projecte ShopMicro**

### 🟠 **order-service** → Producer

Fa servir Pika per:

*   connectar a RabbitMQ
*   enviar missatges a la queue `orders`

### 🟣 **notification-service** → Consumer

Fa servir Pika per:

*   connectar a RabbitMQ
*   escoltar la queue `orders`
*   rebre cada comanda i processar-la

### 🔵 **RabbitMQ**

És el broker central que gestiona tots els missatges.

***

# 🧭 **Per què necessites Pika?**

Perquè sense Pika:

*   no podries enviar events des de order-service
*   no podries escoltar comandes des de notification-service
*   RabbitMQ no interactua directament amb els teus microserveis Python

Pika és el **pont entre Python i RabbitMQ**.

***

# 📌 **Resum final**

**Pika = client Python per RabbitMQ.**

Serveix per:

*   Crear connexions amb RabbitMQ
*   Crear canals AMQP
*   Declarar queues
*   Enviar missatges (producer)
*   Rebre missatges (consumer)

En el teu projecte:

*   `order-service` envia events de comandes via Pika
*   `notification-service` escolta aquests events via Pika
*   RabbitMQ fa de “missatgeria central”

***

Si vols, puc explicar:

*   🔁 com fer servir **manual ack** (important per no perdre missatges)
*   📬 com implementar **retry i dead-letter queues**
*   🎯 diferències entre **BlockingConnection**, **SelectConnection**, etc.
*   🧪 com simular missatges manualment per provar el servei

Només demana!
