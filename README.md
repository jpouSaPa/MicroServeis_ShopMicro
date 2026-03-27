
# 🧩 **Visió general del projecte**

Aquest projecte implementa una **botiga online (shopmicro)** basada en microserveis. Cada funcionalitat està desacoblada en un servei independent:

- **Productes**
- **Comandes**
- **Usuaris**
- **Notificacions**

Aquests serveis es comuniquen entre ells mitjançant:
- **Bases de dades MySQL** (una per productes, una per comandes)
- **Redis** com a cache
- **RabbitMQ** com a sistema de missatgeria
- **API Gateway** com a punt d’entrada únic
- **Frontend** que consumeix l’API Gateway

La infraestructura està organitzada en tres xarxes:
- `frontend-net` → comunica frontend i API Gateway
- `backend-net` → comunica microserveis, cache i message queue
- `db-net` → comunica microserveis amb les bases de dades

---

# 🗄️ **Bases de dades**

## **1. db-products**
- Imatge: `mysql:8.0`
- Base de dades: `productsdb`
- Guarda informació de productes
- Accessible només per `product-service`
- Connectada a la xarxa `db-net`

## **2. db-orders**
- Imatge: `mysql:8.0`
- Base de dades: `ordersdb`
- Guarda informació de comandes i possiblement usuaris
- Accessible per `order-service` i `user-service`
- Xarxa: `db-net`

---

# ⚡ **Cache**

## **cache (Redis)**
- Imatge: `redis:7-alpine`
- Usat per `product-service` per accelerar consultes de productes
- Xarxa: `backend-net`

---

# 📬 **Cua de missatges**

## **message-queue (RabbitMQ)**
- Imatge: `rabbitmq:3-management-alpine`
- Porta exposada: `15672` (panell de gestió)
- Usat per:
  - `order-service` → envia missatges quan es crea una comanda
  - `notification-service` → escolta missatges i envia notificacions

---

# 🧩 **Microserveis**

## **1. product-service**
- Directori: `./product-service`
- Dependències:
  - Redis (`cache`)
  - MySQL (`db-products`)
- Funció:
  - Gestiona productes
  - Fa servir cache per millorar rendiment
- Xarxes: `backend-net`, `db-net`
- Port intern: 5000

---

## **2. order-service**
- Directori: `./order-service`
- Dependències:
  - MySQL (`db-orders`)
  - RabbitMQ (`message-queue`)
- Funció:
  - Gestiona comandes
  - Escriu a la base de dades
  - Envia missatges a RabbitMQ quan hi ha una nova comanda
- Xarxes: `backend-net`, `db-net`
- Port intern: 5001

---

## **3. user-service**
- Directori: `./user-service`
- Dependència:
  - MySQL (`db-orders`) — possiblement comparteix taules o BD
- Funció:
  - Gestiona usuaris (registre, login, etc.)
- Xarxes: `backend-net`, `db-net`
- Port intern: 5002

---

## **4. notification-service**
- Directori: `./notification-service`
- Dependència:
  - RabbitMQ (`message-queue`)
- Funció:
  - Escolta missatges de comandes
  - Envia notificacions (email, logs, etc.)
- Xarxa: `backend-net`
- Port intern: 5003

---

# 🌐 **API Gateway**

## **api-gateway**
- Directori: `./api-gateway`
- Exposa: `8080:80`
- Funció:
  - Punt d’entrada únic per al frontend
  - Redirigeix peticions als microserveis:
    - `/products` → product-service
    - `/orders` → order-service
    - `/users` → user-service
- Xarxes: `frontend-net`, `backend-net`

---

# 🎨 **Frontend**

## **frontend**
- Directori: `./frontend`
- Exposa: `80:80`
- Funció:
  - Interfície web de la botiga
  - Només parla amb l’API Gateway
- Xarxa: `frontend-net`

---

# 🔗 **Com es relacionen entre ells**

Aquí tens un esquema conceptual:

```
          ┌──────────────┐
          │   Frontend   │
          └───────┬──────┘
                  │ HTTP
                  ▼
          ┌────────────────┐
          │  API Gateway   │
          └───┬────┬──────┘
              │    │
   ┌──────────┘    └───────────┐
   ▼                             ▼
Product-service           Order-service ─────► RabbitMQ ◄──── Notification-service
   │                             │
   ▼                             ▼
MySQL (productsdb)        MySQL (ordersdb)
   │
   ▼
 Redis Cache
```

---

# 📌 **Interpretació del `docker compose ps`**

Tots els serveis estan **UP** i funcionant, incloent:

- Bases de dades MySQL (healthy)
- Redis (healthy)
- RabbitMQ (healthy)
- Microserveis (product, order, user, notification)
- API Gateway exposat a `localhost:8080`
- Frontend exposat a `localhost:80`

Això indica que el sistema complet està operatiu.
