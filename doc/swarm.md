Aquí tens **una explicació clara, estructurada i completa en Markdown** del teu fitxer **`docker-stack.yml`**.  
Està pensada per a documentació tècnica o per posar-la al README del projecte.

***

# 🐳 Documentació del fitxer `docker-stack.yml`

Aquesta és l’explicació detallada del desplegament **Docker Swarm** del projecte **ShopMicro**, amb una arquitectura basada en microserveis, bases de dades independents, un cache Redis, una cua de missatges i un frontend públic.

***

# 1. Versió i estructura general

```yaml
version: '3.8'
```

Es fa servir la versió `3.8` del format Compose, necessària per a Docker Swarm (`docker stack deploy`).

L’arxiu defineix **3 blocs principals**:

*   **networks:** xarxes overlay del clúster
*   **volumes:** volums persistents
*   **services:** tots els serveis (BDs, microserveis, cache, RabbitMQ, frontend...)

***

# 2. Xarxes Overlay

```yaml
networks:
  frontend-net:
    driver: overlay
  backend-net:
    driver: overlay
  db-net:
    driver: overlay
```

### Funció:

*   **overlay** permet comunicar contenidors entre diferents nodes del Swarm.
*   Separació en 3 segments:
    *   **frontend-net** → frontend i API gateway
    *   **backend-net** → microserveis + Redis + RabbitMQ
    *   **db-net** → microserveis + bases de dades

### Beneficis:

*   Aïllament i seguretat
*   Compliment del principi de mínim privilegi
*   Evita que serveis innecessaris accedeixin a les BDs

***

# 3. Volums Persistents

```yaml
volumes:
  db_products_data:
  db_orders_data:
  db_users_data:
  rabbitmq_data:
```

### Funció:

*   Persistir dades de:
    *   **3 bases de dades MySQL** (products, orders, users)
    *   **RabbitMQ** (cues durables)

### Important:

Els volums de Swarm són **locals al node**, per això **les BDs sempre s’executen al manager**.

***

# 4. Bases de dades MySQL

Hi ha **3 instàncies MySQL separades**, una per microservei:

```yaml
db-products:
db-orders:
db-users:
```

### Característiques comunes:

*   `image: mysql:8.0`
*   Variables d'entorn:
    *   `MYSQL_ROOT_PASSWORD`
    *   `MYSQL_DATABASE`
*   Volum dedicat
*   Només a **db-net**
*   **deploy → constraints: \[node.role == manager]**  
    → sempre en el node manager
*   **healthcheck** amb `mysqladmin ping`

### Raó per tenir 3 BDs:

*   Aïllament de dades
*   Millor mantenibilitat
*   Microserveis realment independents

***

# 5. Redis Cache

```yaml
cache:
  image: redis:7-alpine
```

### Funció:

*   Cache per a `product-service`
*   Millora rendiment reduint consultes MySQL

### Característiques:

*   Executat només al manager
*   `healthcheck` amb `redis-cli ping`
*   Xarxa: `backend-net`

***

# 6. RabbitMQ (Message Queue)

```yaml
message-queue:
  image: rabbitmq:3-management-alpine
```

### Funció:

*   Sistema de missatgeria **publish/subscribe**
*   `order-service` publica missatges
*   `notification-service` els consumeix

### Característiques:

*   Ports exposats: **15672** (interfície web)
*   Volum propi
*   Healthcheck amb `rabbitmq-diagnostics ping`
*   Xarxa: `backend-net`

***

# 7. Microserveis

Tots tenen:

*   Dues xarxes (excepte notification-service)
*   Variables d’entorn per connexions a BD, Redis o RabbitMQ
*   Rèpliques (1 o 2)
*   `restart_policy` i `update_config` per rolling updates
*   Imatges personalitzades:

<!---->

    jpou/shopmicro-*-service:latest

***

## 7.1 product-service

### Funció:

*   Gestiona informació de productes
*   Usa:
    *   **Redis** (cache)
    *   **MySQL productsdb**

### Xarxes:

*   `backend-net`
*   `db-net`

***

## 7.2 order-service

### Funció:

*   Gestiona comandes
*   Publica missatges a RabbitMQ

### Xarxes:

*   `backend-net`
*   `db-net`

***

## 7.3 user-service

### Funció:

*   Gestió d’usuaris + JWT

### Xarxes:

*   `backend-net`
*   `db-net`

### Nota important:

Inclou una `SECRET_KEY` llarga i complexa per JWT.

***

## 7.4 notification-service

### Funció:

*   Consumidor de missatges de RabbitMQ
*   No té HTTP; només procés intern

### Xarxa:

*   `backend-net` únicament

***

# 8. API Gateway

```yaml
api-gateway:
  ports:
    - "8080:80"
```

### Funció:

*   Reverse proxy basat en **nginx**
*   Punt únic d’entrada a tots els microserveis

### Rèpliques:

*   2, amb rolling updates

### Xarxes:

*   `frontend-net` (entrada pública)
*   `backend-net` (microserveis)

***

# 9. Frontend

```yaml
frontend:
  ports:
    - "80:80"
```

### Funció:

*   Serveix HTML/CSS/JS
*   Envia peticions `/api/...` cap a l’API Gateway

### Característiques:

*   2 rèpliques
*   Accessible des de qualsevol node (mode ingress)

***

# 10. Resum visual de l’arquitectura

          Internet
              │
          ┌─────────┐
          │ Frontend│  (port 80)
          └────┬────┘
               │ frontend-net
          ┌─────────────┐
          │ API Gateway │ (port 8080)
          └────┬────────┘
         backend-net
     ┌───────┼───────────────────────────────┐
     │       │               │               │
     │  product-svc   order-svc       user-svc
     │       │               │               │
     │   Redis ←─────┐      │               │
     │                │      │               │
     │          message-queue (RabbitMQ)     │
     │                │                      │
     │      notification-service             │
     └──────────┼───────────────┬────────────┘
                │ db-net         │ db-net
          db-products      db-orders      db-users

***

# 11. Característiques destacables del deploy

### ✔️ Alta disponibilitat

*   Microserveis i API gateway: **2 rèpliques**
*   Load balancing automàtic via Virtual IP

### ✔️ Rolling updates

*   Canvi d’imatge sense downtime
*   `update_config: parallelism: 1`

### ✔️ Aïllament i seguretat

*   Xarxes separades
*   BDs no accessibles des del frontend

### ✔️ Persistència

*   4 volums dedicats

***

