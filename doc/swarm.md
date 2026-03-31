# SHOPMICRO — Documentació Docker Swarm Stack

> `docker-stack.yml` — Arquitectura de Microserveis amb Alta Disponibilitat

| | |
|---|---|
| **Nodes Swarm** | 1 Manager + 2 Workers |
| **Xarxa** | 10.100.0.0/16 (Proxmox) |
| **Serveis totals** | 11 (3 MySQL, Redis, RabbitMQ, 6 microserveis) |
| **Frontend** | Port 80 (nginx) |
| **API Gateway** | Port 8080 (nginx) |

---

## Índex

1. [Introducció a Docker Swarm](#1-introducció-a-docker-swarm)
2. [Xarxes](#2-xarxes-networks)
3. [Volums](#3-volums-volumes)
4. [Serveis d'infraestructura](#4-serveis-dinfrastructura)
5. [Microserveis](#5-microserveis)
6. [API Gateway i Frontend](#6-api-gateway-i-frontend)
7. [Desplegament i gestió](#7-desplegament-i-gestió)
8. [Flux de dades — Crear una comanda](#8-flux-de-dades--crear-una-comanda)

---

## 1. Introducció a Docker Swarm

Docker Swarm és el sistema d'orquestració de contenidors natiu de Docker. Permet desplegar i gestionar aplicacions en un clúster de múltiples màquines (nodes) de manera transparent, com si fos una sola màquina.

### 1.1 Diferències entre docker-compose i docker stack

| | `docker-compose` | `docker stack` |
|---|---|---|
| **Màquines** | Una sola màquina | Múltiples nodes |
| **Xarxes** | Driver `bridge` | Driver `overlay` |
| **Imatges** | Suporta `build:` | Requereix imatges ja construïdes al registry |
| **Dependències** | Té `depends_on` | No té `depends_on` |
| **Alta disponibilitat** | No | Sí, amb `replicas` |
| **Bloc `deploy:`** | S'ignora | Obligatori per configurar rèpliques i placement |

### 1.2 Arquitectura del clúster

El clúster shopmicro està format per tres nodes Ubuntu Server 22.04 LTS dins d'un entorn Proxmox:

| Hostname | IP | Rol Swarm | Funció |
|---|---|---|---|
| `swarm-manager` | `10.100.1.1` | Manager / Leader | Orquestració + BDs + RabbitMQ + Redis |
| `swarm-worker-1` | `10.100.2.1` | Worker | Microserveis (rèpliques) |
| `swarm-worker-2` | `10.100.3.1` | Worker | Microserveis (rèpliques) |

---

## 2. Xarxes (networks)

El stack defineix tres xarxes **overlay** separades. Les xarxes overlay funcionen sobre la xarxa física del clúster encapsulant el tràfic entre nodes via protocol VXLAN, de manera que els contenidors de nodes diferents es veuen com si estiguessin a la mateixa xarxa local.

```yaml
networks:
  frontend-net:
    driver: overlay    # Comunicació frontend ↔ api-gateway
  backend-net:
    driver: overlay    # Comunicació api-gateway ↔ microserveis ↔ RabbitMQ ↔ Redis
  db-net:
    driver: overlay    # Comunicació microserveis ↔ bases de dades MySQL
```

### 2.1 Separació de xarxes i seguretat

La segmentació en tres xarxes aplica el principi de **mínim privilegi**: cada servei només té accés als altres serveis que necessita.

| Servei | frontend-net | backend-net | db-net |
|---|:---:|:---:|:---:|
| `frontend` | ✅ | ❌ | ❌ |
| `api-gateway` | ✅ | ✅ | ❌ |
| `order-service` | ❌ | ✅ | ✅ |
| `product-service` | ❌ | ✅ | ✅ |
| `user-service` | ❌ | ✅ | ✅ |
| `notification-service` | ❌ | ✅ | ❌ |
| `db-orders` / `db-products` / `db-users` | ❌ | ❌ | ✅ |
| `cache` (Redis) | ❌ | ✅ | ❌ |
| `message-queue` (RabbitMQ) | ❌ | ✅ | ❌ |

> **Per què les BDs no estan a `backend-net`?**
> Les bases de dades MySQL estan NOMÉS a `db-net`. Això significa que el frontend i l'api-gateway no les poden veure directament. Si un atacant compromet el frontend, no pot arribar a les BDs. Només els microserveis que estan a les dues xarxes poden accedir-hi.

---

## 3. Volums (volumes)

Els volums permeten que les dades persisteixin quan un contenidor es reinicia o es recrea. Sense volums, totes les dades es perdrien en cada reinici.

```yaml
volumes:
  db_products_data:   # Dades MySQL del productsdb
  db_orders_data:     # Dades MySQL del ordersdb
  db_users_data:      # Dades MySQL del usersdb
  rabbitmq_data:      # Cua de missatges persistent
```

> ⚠️ **Limitació important amb Docker Swarm**
>
> Els volums Docker en Swarm són **locals a cada node**. Si un servei es mou d'un node a un altre, el nou node NO té les dades de l'anterior. Per això les BDs estan fixades al manager amb `placement: constraints: [node.role == manager]` — sempre s'executen al mateix node i sempre accedeixen als mateixos volums.
>
> Per a producció real amb alta disponibilitat de BDs caldria NFS compartit, Ceph, o un servei de BD extern.

---

## 4. Serveis d'infraestructura

### 4.1 Bases de dades MySQL (`db-products`, `db-orders`, `db-users`)

```yaml
db-orders:
  image: mysql:8.0
  environment:
    MYSQL_ROOT_PASSWORD: rootpass
    MYSQL_DATABASE: ordersdb
  volumes:
    - db_orders_data:/var/lib/mysql
  networks: [db-net]
  deploy:
    replicas: 1
    placement:
      constraints: [node.role == manager]
    restart_policy:
      condition: on-failure
```

| Directiva | Descripció |
|---|---|
| `image: mysql:8.0` | Usa la imatge oficial de MySQL versió 8.0 del Docker Hub |
| `MYSQL_ROOT_PASSWORD` | Contrasenya de l'usuari root. Els microserveis es connecten com a root |
| `MYSQL_DATABASE` | Crea automàticament la base de dades en el primer arrencada |
| `volumes:` | Munta el volum persistent a `/var/lib/mysql` on MySQL guarda les dades |
| `replicas: 1` | Només una instància. Les BDs no es poden replicar amb volums locals |
| `constraints: manager` | Fixa el contenidor al node manager per garantir accés als volums |
| `restart_policy: on-failure` | Reinicia el contenidor automàticament si cau per error |
| `healthcheck` | Comprova cada 10s que MySQL respon. Els microserveis esperen que passi el healthcheck |

### 4.2 Cache Redis

Redis actua com a capa de cache per al `product-service`, emmagatzemant resultats de consultes freqüents a memòria per evitar consultes repetides a MySQL i reduir la latència.

```yaml
cache:
  image: redis:7-alpine
  networks: [backend-net]
  deploy:
    replicas: 1
    placement:
      constraints: [node.role == manager]
```

`alpine` és una distribució Linux minimalista (~5MB) que redueix la superfície d'atac i el temps de descàrrega. Redis s'executa al manager per tenir accés estable des dels workers via xarxa overlay.

### 4.3 Cua de missatges RabbitMQ

RabbitMQ implementa el patró **publish/subscribe**. Quan es crea una comanda, l'`order-service` publica un missatge a la cua `orders`. El `notification-service` escolta la cua i processa les notificacions de manera asíncrona, desacoblant els dos serveis.

```yaml
message-queue:
  image: rabbitmq:3-management-alpine
  environment:
    RABBITMQ_DEFAULT_USER: admin
    RABBITMQ_DEFAULT_PASS: adminpass
  ports:
    - "15672:15672"   # Interfície web de gestió
  volumes:
    - rabbitmq_data:/var/lib/rabbitmq
  deploy:
    replicas: 1
    placement:
      constraints: [node.role == manager]
```

El port `15672` publica la interfície web de gestió de RabbitMQ accessible des de qualsevol node del clúster. El volum persistent garanteix que les cues i missatges pendents no es perdin en un reinici.

---

## 5. Microserveis

### 5.1 Visió general

| Servei | Imatge | Rèpliques | Xarxes | Notes |
|---|---|:---:|---|---|
| `order-service` | `usuari/shopmicro-order-service` | 2 | backend-net, db-net | Flask + MySQL + RabbitMQ. Port 5001 |
| `product-service` | `usuari/shopmicro-product-service` | 2 | backend-net, db-net | Flask + MySQL + Redis cache. Port 5000 |
| `user-service` | `usuari/shopmicro-user-service` | 2 | backend-net, db-net | Flask + MySQL + JWT. Port 5002 |
| `notification-service` | `usuari/shopmicro-notification-service` | 1 | backend-net | Consumidor RabbitMQ. Sense HTTP |
| `api-gateway` | `usuari/shopmicro-api-gateway` | 2 | frontend-net, backend-net | nginx reverse proxy. Port 80 intern |
| `frontend` | `usuari/shopmicro-frontend` | 2 | frontend-net | nginx servint HTML/CSS/JS. Port 80 públic |

### 5.2 Bloc `deploy` dels microserveis

Els microserveis stateless tenen 2 rèpliques amb rolling update configurat:

```yaml
order-service:
  image: usuari/shopmicro-order-service:latest
  environment:
    RABBITMQ_HOST: message-queue
    DATABASE_URL: mysql+pymysql://root:rootpass@db-orders:3306/ordersdb
  networks: [backend-net, db-net]
  deploy:
    replicas: 2                  # 2 còpies distribuïdes entre workers
    restart_policy:
      condition: on-failure      # Reinicia si el procés cau
      delay: 10s                 # Espera 10s abans de reiniciar
    update_config:
      parallelism: 1             # Actualitza d'1 en 1 (rolling update)
      delay: 10s                 # Espera 10s entre actualitzacions
```

| Directiva | Descripció |
|---|---|
| `replicas: 2` | Swarm distribueix les 2 instàncies entre els nodes. Si un node cau, l'altra rèplica segueix servint peticions |
| `restart_policy` | Si un contenidor cau per error (codi de sortida != 0), Swarm el reinicia automàticament |
| `delay: 10s` | Temps d'espera entre reintents de reinici |
| `update_config` | Defineix com fer actualitzacions quan es desplega una nova imatge |
| `parallelism: 1` | Actualitza primer 1 rèplica, espera, i si va bé actualitza la resta. Garanteix zero downtime |

### 5.3 Comunicació entre serveis sense `depends_on`

Docker Swarm **no suporta** `depends_on`. Cada microservei ha de gestionar els reintents de connexió internament.

> **Solució implementada:** La funció `init_db()` dels microserveis Flask fa fins a 10 intents de connexió a MySQL amb 3 segons d'espera entre cada intent. Si un microservei arrenca abans que MySQL estigui llest, simplement reintenta fins a connectar.

---

## 6. API Gateway i Frontend

### 6.1 API Gateway (nginx)

L'`api-gateway` és un nginx que actua com a punt d'entrada únic per a tots els microserveis. Rep peticions al port 8080 i les reenvía al microservei corresponent **eliminant el prefix de la URL**.

```nginx
# nginx.conf del api-gateway
upstream orders   { server order-service:5001; }
upstream products { server product-service:5000; }
upstream users    { server user-service:5002; }

server {
  listen 80;
  location /api/orders/   { proxy_pass http://orders/; }
  location /api/products/ { proxy_pass http://products/; }
  location /api/users/    { proxy_pass http://users/; }
}
```

Exemple de com s'elimina el prefix:
```
Petició entrada:  GET /api/orders/orders
Nginx transforma:          /orders
Envia a:          order-service:5001/orders  ✅
```

Amb 2 rèpliques de l'`api-gateway` i 2 rèpliques de cada microservei, Docker Swarm fa **load balancing automàtic** via la xarxa overlay. Cada servei té una Virtual IP (VIP) que distribueix les connexions entre totes les rèpliques actives de manera round-robin.

✅ Versió corregida amb ALIAS DNS
Això fa que els noms utilitzats dins de la teva imatge (product-service, user-service, etc.) resolguin al nom de Swarm (shopmicro_product-service, etc.)
YAML# ─── API GATEWAY ─────────────────────────────────────api-gateway:  image: jpou/shopmicro-api-gateway:latest  ports:    - "8080:80"  networks:    frontend-net:    backend-net:      aliases:        - product-service        - user-service        - order-service        - notification-service  deploy:    replicas: 2    restart_policy:      condition: on-failure    update_config:      parallelism: 1      delay: 10sMostra més línies

🧠 Per què funciona?
Docker Swarm crea els serveis amb nom:
shopmicro_product-service
shopmicro_user-service
shopmicro_order-service
shopmicro_notification-service

🟢 1. El gateway ara funciona correctament en qualsevol node
Ja no depén del nom intern de Swarm (shopmicro_product-service) sinó que els aliases permeten que el gateway continuï usant els noms que tens a la imatge:
product-service
user-service
order-service
notification-service

Això és exactament el comportament esperat.

✔ Gateway amb aliases a backend-net
És exactament la solució recomanada per Docker Swarm, la mateixa que utilitzen plataformes de producció.

### 6.2 Frontend (nginx)

```yaml
frontend:
  image: usuari/shopmicro-frontend:latest
  ports:
    - "80:80"       # Accessible des de qualsevol node del clúster
  networks: [frontend-net]
  deploy:
    replicas: 2
```

Gràcies al **mode ingress** de Swarm, publicar el port 80 fa que sigui accessible a través de la IP de **qualsevol node** del clúster (10.100.1.1, 10.100.2.1 o 10.100.3.1), independentment de quin node estigui executant la rèplica.

---

## 7. Desplegament i gestió

### Desplegar el stack

```bash
# Des del node manager
docker stack deploy -c docker-stack.yml shopmicro

# Verificar que tots els serveis arrenquen
docker stack services shopmicro

# Veure on s'executa cada contenidor
docker stack ps shopmicro
```

### Actualitzar una imatge (rolling update)

```bash
# 1. Construir i pujar la nova imatge
docker build -t usuari/shopmicro-order-service:latest ./order-service
docker push usuari/shopmicro-order-service:latest

# 2. Re-desplegar (aplica el rolling update automàticament)
docker stack deploy -c docker-stack.yml shopmicro

# Swarm actualitzarà 1 rèplica cada 10s sense downtime
```

### Escalar un servei

```bash
# Escalar order-service a 3 rèpliques
docker service scale shopmicro_order-service=3

# Verificar
docker service ls | grep order
```

### Monitoratge

```bash
# Estat general del stack
docker stack services shopmicro

# Logs d'un servei concret
docker service logs -f shopmicro_order-service

# Veure en quin node s'executa cada contenidor
docker stack ps shopmicro

# Interfície web RabbitMQ
# http://10.100.1.1:15672  (admin / adminpass)
```

### Aturar el stack

```bash
# Atura tots els serveis del stack
docker stack rm shopmicro

# NOTA: Els volums NO s'eliminen. Les dades persiteixen.
# Per eliminar volums (DESTRUEIX LES DADES):
# docker volume rm shopmicro_db_orders_data
```

---

## 8. Flux de dades — Crear una comanda

Recorregut complet d'una petició `POST /api/orders/orders` des del navegador fins a la base de dades:

| Pas | Component | Acció |
|:---:|---|---|
| 1 | Navegador → `frontend:80` | El navegador fa `POST /api/orders/orders`. El nginx del frontend reenvia la petició cap a l'api-gateway via `frontend-net` |
| 2 | `frontend` → `api-gateway:80` | L'api-gateway rep la petició a `/api/orders/orders` |
| 3 | `api-gateway` → `order-service:5001` | Nginx elimina el prefix `/api/orders/` i reenvia `POST /orders` a una de les rèpliques d'`order-service` via `backend-net` |
| 4 | `order-service` → `db-orders:3306` | Flask guarda la comanda a MySQL (`ordersdb`) via `db-net`. SQLAlchemy gestiona la connexió |
| 5 | `order-service` → `message-queue:5672` | Flask publica el missatge JSON de la nova comanda a la cua `orders` de RabbitMQ via `backend-net` |
| 6 | `message-queue` → `notification-service` | RabbitMQ entrega el missatge al `notification-service` que el consumeix i processa la notificació |
| 7 | `order-service` → Navegador | `order-service` retorna `{"status": "order_created"}`. La resposta torna pel mateix camí fins al navegador |

```
Navegador
    │  POST /api/orders/orders
    ▼
frontend:80  ──(frontend-net)──►  api-gateway:80
                                       │  POST /orders
                                       ▼
                              order-service:5001
                                  │           │
                          (db-net)│           │(backend-net)
                                  ▼           ▼
                            db-orders:3306  message-queue:5672
                                                │
                                                ▼
                                    notification-service
```

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

