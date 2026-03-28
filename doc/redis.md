[Tornar al README](../README.md)


Com funciona **Redis**, però en el context del projecte **ShopMicro**, és a dir, un sistema de microserveis amb Docker Compose on hi ha aquest contenidor:

    shopmicro-cache-1   redis:7-alpine   ...   Up 2 hours (healthy)   6379/tcp


***

# 🧠 **Què és Redis?**

Redis és una **base de dades en memòria**, super ràpida, utilitzada sobretot per:

*   *cache* (guardar respostes que calcularíem un altre cop)
*   *sessions*
*   *rate limiting*
*   *message queues lleugeres*
*   *key/value store* molt simple

Funciona totalment a RAM → per això és **ultra ràpid** (microsegons o mil·lisegons).

***

# 📦 **1. Com funciona internament (vista simple)**

Redis és un servidor que:

*   escolta al port **6379**
*   guarda les dades **en RAM**
*   utilitza un model **key → value**
*   pot guardar cadenes, llistes, sets, hashes, etc.

Exemple:

    SET product:123 '{"name":"Keyboard","price":49.99}'
    GET product:123

🚀 Tot això passa **en RAM**, sense discos → velocitat enorme.

***

# 🔌 **2. Com funciona al teu Docker Compose**

Dins la xarxa interna de Docker Compose, el servei Redis queda així:

    Nom DNS: cache
    Port: 6379

Això vol dir que qualsevol microservei pot fer:

```python
redis = Redis(host="cache", port=6379)
```

i connectar-se directament.

💡 *La màgia de Docker Compose: el nom del servei és el host DNS.*

***

# 🛠️ **3. Quin paper fa Redis en el projecte ShopMicro**

En aquest tipus d’arquitectura **Redis s’utilitza normalment per:**

### ✔ Cachejar respostes

Exemple: `product-service` pot guardar:

    product:123 → dades del producte

Així, quan el producte es demana moltes vegades, es recupera de Redis en lloc de fer consultes a MySQL.

### ✔ Guardar sessions de l’usuari

Si tens un "login" al `user-service`, es pot guardar:

    session:token ➜ id_usuari

Així tots els microserveis poden validar l’usuari.

### ✔ Cache de tokens JWT (revocació)

És molt habitual fer:

    blacklist:jwt:abc123 → true

### ✔ Rate limiting (limitar peticions)

Es pot fer:

    INCR rate:user:109
    EXPIRE rate:user:109 60

***

# ⚙️ **4. Com funciona Redis a nivell de comandaments**

*   És single-thread, però extremadament ràpid.
*   Guarda tot en un **diccionari en memòria** (com un `dict` de Python).
*   Quan rep una comanda, la processa i envia la resposta via TCP.

### Exemple seqüència:

1.  El `product-service` fa:
        GET product:23
2.  Si existeix en RAM → resposta immediata.
3.  Si no existeix:
    *   el servei consulta MySQL
    *   guarda a Redis:
            SET product:23 {...} EX 60
        (EX 60 = caduca en 60 segons)

Això és el patró de **cache write-through**.

***

# 🔒 **5. Persistència: Redis no és només RAM**

Però Redis **pot opcionalment guardar dades al disc**:

*   RDB (snapshots)
*   AOF (Append Only File)

Depèn de si ho has configurat.  
Per defecte, en un contenidor docker de Redis sense volums, **tota la informació es perd** si el contenidor para.

***

# 🧭 **6. Funcionament dins d’una arquitectura de microserveis**

Redis actua com:

                     ┌──────────────┐
                     │ product DB   │ (MySQL)
                     └──────┬───────┘
                            │
                   misses   │   hits
                            ▼
           ┌──────────────────────────┐
           │          Redis           │
           └───────────┬─────────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │ product-service      │
            └──────────────────────┘

***

# 📌 **7. Com es vincula això amb aquest cas real**

Tens:

    shopmicro-cache-1   redis:7-alpine   healthy

⇒ Redis està llest i acceptant connexions.

Segurament algun d’aquests microserveis:

*   **product-service**
*   **order-service**
*   **user-service**
*   **notification-service**

fa servir Redis com a:

*   cache
*   emmagatzematge temporal
*   suport per peticions repetides

***

**Els dissenys (patterns)** de *cache* més importants, com funcionen, quan es fan servir i els seus avantatges/inconvenients.  
Aquests són patrons habituals en sistemes com aquest *ShopMicro*, especialment si un microservei usa Redis per millorar el rendiment.

***

# 🧠 **0. Conceptes bàsics **

Quan un servei fa servir cache, pot produir **cache hits** (ja existeix a la cache) o **cache misses** (no hi és i s’ha d’anar a la base de dades).

La cache pot:

*   **Escriure’s** automàticament quan es modifica la base de dades
*   **Llegir-se** abans de la base de dades
*   **Caducar** amb TTLs (time-to-live)

***

# ⭐ **1. Cache Aside (Lazy Loading)**

*(El patró més comú i segur — segurament el que tens al projecte)*

## 🔍 Com funciona

1.  El servei primer mira a Redis:
        GET product:123
2.  Si **no hi és**:
    *   Fa la consulta a la base de dades
    *   Desa el resultat a Redis:

    <!---->

        SET product:123 {...} EX 60
3.  Retorna la resposta al client.

## ✔ Avantatges

*   Només es cachegen dades que realment es consulten.
*   Consum de memòria més baix.
*   Simple de mantenir.

## ✖ Inconvenients

*   El primer accés sempre és lent (cache miss).
*   Cache pot quedar desactualitzada si no s’invalida bé.

***

# ⭐ **2. Write‑Through Cache**

*(Escriu a la cache **i** a la base de dades sempre a la vegada)*

## 🔍 Com funciona

Quan el servei **modifica** dades:

1.  Escriu a Redis:
        SET product:123 {...}
2.  Escriu a MySQL:
        UPDATE products SET ...

La cache **sempre està sincronitzada** amb la base de dades.

## ✔ Avantatges

*   La cache mai té dades “velles”.
*   Ideal per a lectures freqüents.

## ✖ Inconvenients

*   Escriure és més lent (doble operació).
*   Augmenta el consum de RAM.

***

# ⭐ **3. Write‑Behind (Write‑Back)**

*(Escriu **només a Redis** i deixa que la BD es vagi actualitzant després)*

## 🔍 Com funciona

1.  El servei escriu a Redis:
        SET order:88 {...}
2.  Redis manté una cua de canvis.
3.  Passats uns segons, Redis (o un worker) desarà els canvis a MySQL.

## ✔ Avantatges

*   Extremadament ràpid (escritures a RAM).
*   Ideal per càrregues molt altes.

## ✖ Inconvenients

*   Si Redis cau → **es poden perdre dades recent escrites**.
*   Sincronització més complexa.

No es recomana per a dades molt crítiques.

***

# ⭐ **4. Read‑Through Cache**

*(El servei no accedeix mai directament a la base de dades)*  
La cache encarrega de recuperar i carregar dades quan cal.

## 🔍 Com funciona

El microservei fa:

    GET product:123

Si no hi és, és la pròpia capa de cache qui:

*   fa la consulta a la BD,
*   i desa la resposta a Redis,
*   i retorna el resultat.

És com Cache Aside però **la lògica està encapsulada** en un middleware.

## ✔ Avantatges

*   Simplifica el microservei.
*   Consistent i ràpid.

## ✖ Inconvenients

*   Requereix llibreries o middleware especial.
*   Afegim complexitat fora del codi.

***

# ⭐ **5. Write‑Around**

*(Similar a Cache Aside però quan escrius NO actualitzes la cache)*

## 🔍 Com funciona

Quan escrius:

*   Escrius a BD
*   **No** escrius a la cache
*   La cache només s’actualitza quan hi hagi una lectura

## ✔ Avantatges

*   Evita dades poc usades a la cache.
*   Bo quan hi ha moltes escriutres però poques lectures.

## ✖ Inconvenients

*   Misses freqüents després d’escriure.
*   Cache pot quedar desactualitzada fins la propera lectura.

***

# ⭐ **6. Cache Amb TTL (expiració)**

*(Usat juntament amb qualsevol dels altres patrons)*

Cada entrada de cache té un temps de vida:

    SET user:123 {...} EX 120   # 2 minuts

Quan el TTL s’esgota → Redis l’esborra.

## ✔ Avantatges

*   Evita tenir dades antigues.
*   Bona estratègia per cachejar dades que canvien sovint.

## ✖ Inconvenients

*   Un munt d’expiracions simultànies → “cache stampede” (tots els clients van a la BD alhora).

***

# ⭐ **7. Cache Stampede i Solucions**

Problema:  
Quan una cache expira i mil clients fan la mateixa petició →  
**tots van a la BD** → col·lapse.

### Solucions:

*   **Locking / Mutex**: només un procés actualitza la cache.
*   **TTL aleatori**: es reparteixen les expiracions.
*   **Background refreshing**: actualitzacions proactives.

***

# 🧠 Quin patró uses (probablement) a ShopMicro?

Sense veure el codi, però en microserveis Python + Redis + MySQL:

➡️ **Cache Aside amb TTL**  
És el patró més usat: simple, segur i eficient.


[Tornar al README](../README.md)
