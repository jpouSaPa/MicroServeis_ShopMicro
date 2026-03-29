# 🟦 **ANÀLISI COMPLET DEL `user-service`**

Aquest microservei és responsable de:

*   registre i login d’usuaris
*   autenticació via JWT
*   consulta i modificació del perfil
*   gestió d’activació/desactivació
*   actualment usa **SQLite local** (ho canviarem a MySQL)

***

# 🧩 1. Configuració actual de la BD

```python
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'sqlite:///users.db'
)
```

📌 **Ara mateix user-service usa SQLite**, un fitxer local dins el contenidor.

Això té inconvenients:

*   Es perd si recrees el contenidor
*   No és compartit per altres instàncies
*   No escala
*   No és coherent amb la resta de microserveis

🔥 **Ho convertirem a MySQL**, com et fa il·lusió fer.

***

# 🟦 2. Model `User`

```python
class User(db.Model):
    id = db.Column(...)
    username = unique
    email = unique
    password_hash = hashed
    is_active = Boolean
```

Correcte i senzill.  
Suficient per un microservei d’autenticació.

***

# 🧠 3. Autenticació JWT

Molt ben implementat:

*   `generate_token(user_id)` → HS256
*   conté `sub`, `iat`, `exp`
*   valides el token amb un decorador `@token_required`

Aquest és un patró completament estàndard.

### 🔒 Punt feble actual

Si un usuari es desactiva (`is_active=False`), qualsevol token antic **continua funcionant** fins que caduqui.

Quan vegi el conjunt complet et diré com millorar-ho amb:

*   Redis
*   token blacklist
*   invalidació immediata

***

# 🟧 4. Rutes principals

### ✔ `/register`

Crea usuari, genera token.  
Valida:

*   nom
*   email
*   password > 8
*   duplicats

Tot correcte.

### ✔ `/login`

Valida credencials → genera token.

### ✔ `/me` GET

Requereix token → torna l’usuari.

### ✔ `/me` PUT

Actualitza username o password.

### ✔ `/me` DELETE

Marca usuari com inactiu.

### ✔ `/health`

Resposta simple.

***

# 🟥 5. Errors menors detectats

### 🔸 Igual que en product-service i order-service:

Tens HTML escapada:

    &lt;

En concret:

```python
if len(password) &lt; 8:
```

Cal que sigui:

```python
if len(password) < 8:
```

També en altres línies.

***

# 🟩 6. BD init

```python
_db_initialized = False
@app.before_request
def init_db():
    db.create_all()
```

Això crea la BD (SQLite o MySQL) abans de la primera petició.  
Funciona, però **amb MySQL s’haurà d’adaptar lleugerament** perquè MySQL pot trigar a arrencar i pot fallar si no fem reintents (igual que order-service).

Ho arreglaré quan migrem.

***

# 🟪 7. Conclusió del user-service

| Component     | Estat                                       |
| ------------- | ------------------------------------------- |
| Flask         | ✔ Correcte                                  |
| SQLAlchemy    | ✔ Correcte                                  |
| SQLite        | ⚠️ L’hem de substituir per MySQL            |
| JWT           | ✔ Ben implementat                           |
| Validacions   | ✔ Correctes                                 |
| Tokens        | ⚠️ No es poden invalidar (possible millora) |
| HTML escapada | ❌ S’ha de corregir                          |

***

# 🎯 I ara què farem?

Tal com has dit:

> *em demanaràs algun canvi al servei user-service perquè hi vull fer servir un mysql, també.*

I **sí, ho podem fer PERFECTE** perquè tens la mateixa estructura que a product-service i order-service.

***

# 🚀 El que faré quan m’ho demanis

Quan em diguis *“Fes que el user-service utilitzi MySQL com els altres”*, et prepararé:

### ✔ `DATABASE_URL` correcte per a MySQL

Exemple:

    mysql+pymysql://root:rootpass@db-orders:3306/usersdb

o millor:

    db-users

si vols una BD separada.

### ✔ Codi adaptat amb reintents com order-service

`init_db()` similar a:

```python
for _ in range(10):
    try:
        db.create_all()
        return
    except:
        time.sleep(3)
```

### ✔ Correcció de tots els `&lt;`

Flask necessita `<` literal.

### ✔ Actualització del docker-compose:

    user-service:
      environment:
        DATABASE_URL: mysql+pymysql://root:rootpass@db-users:3306/usersdb

### ✔ Creació del servei `db-users` (o reutilitzar db-orders)

Recomanació: crear **db-users** per separació i seguridad.

***

Aquí tens **l’anàlisi complet del teu `user-service`**, explicant si fa servir Redis, quin **patró de cache** utilitza (si n’utilitza), quina és l’arquitectura interna i quins patrons de disseny aplica.

Aquest és el microservei més “gran” i on podríem esperar ús de cache, però **no en fa servir cap**.

***

# 🧩 1. Conclusió ràpida

### 🔥 \*\*El `user-service` NO utilitza Redis.

Zero cache. Zero TTL. Zero invalidació.  
Per tant, NO implementa cap patró de cache.\*\*

Només utilitza:

*   **SQLite** o MySQL (segons la variable `DATABASE_URL`)
*   **JWT local** (signats amb SECRET\_KEY)
*   **Validació directa a base de dades**

Això implica que:

*   Més càrrega va directament a la BD.
*   Cap token es guarda a Redis per invalidar-lo.
*   No hi ha cap “session store”.

Ara ho desplego pas a pas.

***

# 🧠 2. Què fa exactament el microservei?

## 📌 2.1. Registre d’usuari

*   Hash amb `generate_password_hash`
*   Guarda directament a BD
*   Retorna un **JWT**

## 📌 2.2. Login

*   Llegeix usuari directament de BD
*   Si és correcte, genera un **nou JWT**
*   No crea sessions, no guarda res a Redis

## 📌 2.3. Protecció de rutes (JWT middleware)

```python
current_user = User.query.get(data['sub'])
```

Cada petició a `/me`, `/me PUT`, `/me DELETE`:

➡️ **fa una consulta directa a la BD**

No toca cap memòria cau.

## 📌 2.4. Actualització i eliminació d’usuari

*   Modifica camp a BD (`is_active`)
*   No toca Redis, no invaliden cap token antic

***

# 🧱 3. Quin patró de cache utilitza?

👉 **Cap. Literalment cap.**

No hi ha:

*   redis import
*   connexió a "cache"
*   `get`, `set`, `setex`
*   Cache Aside
*   Write-through
*   Read-through
*   Write-back

Res.

La lògica és **BD + JWT pur**.

***

# ⚠️ 4. Limitacions de no utilitzar Redis aquí

## 🔶 4.1. Tokens no invalidables

Si un usuari fa logout, o se li desactiva el compte:

*   El token segueix essent vàlid fins que expiri.
*   No hi ha cap “token blacklist”.

Patró que falta:

### ❌ **Token Blacklist Cache (Redis)**

On guardaríem:

    blacklist:<token> = true  (amb TTL igual al token)

***

## 🔶 4.2. Overhead a la BD

Cada petició amb JWT fa:

    SELECT * FROM users WHERE id = ...

Amb cache, faries:

*   `GET user:123`  
    si no → DB → cache.

Això és **Cache Aside per usuari**, que milloraria el rendiment.

***

## 🔶 4.3. No hi ha rate limiting

Normalment:

*   `/login` hauria de tenir limitador: evitar brute force.
*   Redis és l’estàndard per això.

Patró típic:

    INCR login:ip:1
    EXPIRE login:ip:1 60

***

# 🧠 5. Quins patrons **sí** aplica el teu `user-service`?

Tot i no usar cache, sí utilitza patrons importants:

## ✔ **JWT Stateless Authentication**

Això està perfecte: cada petició porta la seva autenticació.

## ✔ **Single Source of Truth: Base de dades**

Cada validació de token busca l’usuari directament.

## ✔ **DB per consistència i control d’estat**

Especialment el camp `is_active`.

## ✔ **Lazy DB init** amb `before_request`

Evita errors en serveis petits.

***

# 🧭 6. Quins patrons de cache podries (i hauries) d’implementar?

Aquí tens millores molt recomanables:

***

## 🟦 6.1. **Cache Aside per dades de l’usuari**

Quan fas `/me`:

1.  miraries a Redis:

<!---->

    user = redis.get(f"user:{id}")

2.  si no → DB → cache

Millora rendiment per rutes molt cridades.

***

## 🟥 6.2. **Token blacklist** (important!)

Quan l’usuari es desactiva:

    SETEX blacklist:<token>, ttl, "1"

I al middleware:

    if redis.exists(f"blacklist:{token}"): block

Ara mateix això NO passa → un usuari "borrat" pot seguir usant el token.

***

## 🟩 6.3. **Rate limiting a /login**

Redis és ideal:

    INCR login_attempts:<ip>
    EXPIRE login_attempts:<ip> 60
    if attempts > 5: block

Ara mateix → l’endpoint és vulnerable a força bruta.

***

## 🟨 6.4. **Cache de consultes massives**

Si afegeixes rutes com `/users`:

→ faries cache.  
Però aquest servei no en té.

***

# 📌 7. Resum final del teu `user-service`

| Àrea                 | Estat actual                                  |
| -------------------- | --------------------------------------------- |
| Redis cache          | ❌ No utilitzat                                |
| Patró de cache       | ❌ Cap                                         |
| Patró d’autenticació | ✔ JWT pur (sense estat)                       |
| Validació d’usuari   | ✔ Sempre BD                                   |
| Missatgeria          | ❌ No                                          |
| Persistència         | ✔ SQLite / MySQL                              |
| Possibles millores   | ✔ Token blacklist, cache aside, rate limiting |

**És normal i correcte que un user-service petit comenci així**, però en producció sí que afegiries Redis per:

*   bloquejar tokens revocats
*   limitar intents de login
*   cachejar perfils d’usuari

***

Vols que t’implementi (jo mateix) una versió millorada del `user-service` amb:

*   **Redis cache**
*   **Rate limiting**
*   **Token revocation**
*   **Cache Aside per /me**

Només digues *"sí, fes-ho"* i te'l preparo.
