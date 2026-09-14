# Implementación — Caché de productos (Redis) e ingesta asíncrona (RabbitMQ)

Este documento explica qué se cambió en el simulador, por qué, dónde quedó el
código y cómo probarlo a mano. Está escrito para alguien que no conoce nada del
tema, así que cada idea se define la primera vez que aparece.

> Nota: `README.md` no se tocó. Todo lo nuevo está en este documento y en el
> código.

---

## 1. De qué trataba el problema

Antes de esta implementación, el simulador hacía dos cosas "de la manera simple"
que este trabajo reemplaza:

1. **Consultar un producto por su código EAN.** El endpoint
   `GET /products/{ean}` de cada tienda iba **siempre** a PostgreSQL: cada vez
   que el cajero escaneaba un producto, la tienda preguntaba a su base de datos
   el nombre y el precio. Eso funciona, pero es caro: el catálogo casi no cambia
   (mismo arroz, misma leche, mismo precio durante horas), y sin embargo se
   pagaba el costo de una consulta a la base por cada escaneo.

2. **Recibir un lote de facturas en la central.** El endpoint
   `POST /sales/batch` de la oficina central **insertaba directamente en MySQL
   dentro de la misma petición HTTP**. Quien llamaba (el forwarder de la tienda)
   se quedaba esperando a que el inserto terminara, y el peso de escribir decenas
   de facturas caía sobre el request. Además, si MySQL era lento, la tienda
   esperaba lento.

Este trabajo introduce dos piezas de infraestructura nuevas para resolverlo:
**Redis** (un caché, una memoria rápida intermedia) y **RabbitMQ** (una cola de
mensajes, una bandeja de entrada entre dos procesos).

---

## 2. Tarea 1 — Caché de productos por EAN (Redis)

### 2.1 Qué se implementó

El endpoint `GET /products/{ean}` ahora:

1. **Revisa primero el caché.** Si el producto ya está en Redis, se responde
   desde ahí y **PostgreSQL ni se entera** (un "hit" de caché).
2. **Si no está** (un "miss"), se consulta PostgreSQL, se responde el producto
   **y se guarda una copia en caché** para la próxima vez.
3. La copia caduca sola a los **300 segundos (5 minutos)**; ese tiempo es
   configurable con la variable `PRODUCT_CACHE_TTL_SECONDS`.

Qué se guarda: **el producto completo** — `{ean, name, price}` — porque la
respuesta de la API lleva los tres campos, no solo el precio. El precio se
guarda como **texto** (`"2000.00"`), no como número decimal de punto flotante,
para que los centavos no se redondeen silenciosamente al pasar por JSON.

### 2.2 Por qué se hizo así

- **Menos trabajo para PostgreSQL.** El catálogo casi no cambia, así que
  repetir la misma respuesta 50 veces no necesita 50 consultas a la base. Esto
  es justo el patrón clásico *cache-aside*: caché primero, base solo por debajo.
- **Un Redis por tienda, no uno compartido.** El proyecto se apoya en que "las
  dos tiendas nunca comparten datos" (redes separadas, volúmenes separados). Un
  caché también es dato, así que hay un Redis para la tienda 1 dentro de su red
  y otro para la tienda 2 dentro de la suya. Ningún Redis está en la red WAN.
- **El caché es una ventaja, no una dependencia.** Si Redis no responde, el
  endpoint **no falla**: se registra un aviso en el log y la consulta cae a
  PostgreSQL como antes. Romper el caché no puede romper una venta.
- **Se respeta la arquitectura de capas.** El paquete `products/` ya seguía el
  patrón `router → service → repository`. La caché entra en la **capa de
  servicio**: `service.get_product` es el único lugar que decide "¿caché o
  base?". El repositorio sigue siendo solo base de datos, y el router no sabe
  nada de Redis. El estilo copia al cliente del gateway de pagos
  (`payments/gateway_client.py`), que se inyecta como parámetro con valor por
  defecto para poder reemplazarlo en los tests.

### 2.3 Dónde quedó el código

| Archivo | Qué hace |
|---|---|
| `docker-compose.yml` | Servicios **`store-1-redis`** y **`store-2-redis`** (imagen `redis:7-alpine`), cada uno en la red de su tienda, con healthcheck y puerto de inspección `56379` / `56380`. Variable `REDIS_URL` añadida a `store-1-backend` y `store-2-backend`. |
| `backend/app/core/config.py` | Lee del entorno `REDIS_URL` y `PRODUCT_CACHE_TTL_SECONDS` (default 300). |
| `backend/app/products/cache.py` **(nuevo)** | El cliente Redis del paquete de productos: conexión *lazy* (no abre conexión hasta que hace falta), `get_cached(ean)`, `set_cached(ean, product)`, clave `product:{ean}`, serialización con el precio como texto, y degradación silenciosa si Redis falla. |
| `backend/app/products/service.py` | `get_product(session, ean, catalog_cache=cache)`: cache-first (hit sin tocar base; miss → repositorio → poblar caché). |
| `backend/app/products/tests/test_service.py` | Tests con un caché falso: miss que lee de la base y puebla el caché, EAN desconocido que no se guarda, y **hit que nunca llega al repositorio**. |
| `backend/requirements.txt` | Añade `redis==8.1.0`. |

El `router.py` de productos **no cambió**: la caché se inyecta sola en el
servicio, igual que el gateway se inyecta en `payments/service.py`.

### 2.4 Cómo probarlo a mano

```bash
make up                       # levanta todo (20 contenedores)

# 1) Consultar un producto de la tienda 1 (la primera vez es un "miss")
curl -s http://localhost:18000/products/7702001010301
#    → {"ean":"7702001010301","name":"Arroz","price":"2000.00"}

# 2) Mirar dentro de Redis que ese producto quedó guardado
make shell CONTAINER=store-1-redis
redis-cli get product:7702001010301
#    → {"ean":"7702001010301","name":"Arroz","price":"2000.00"}
redis-cli ttl product:7702001010301
#    → un número entre 299 y 300 (va contando hacia abajo; al llegar a 0 caduca)
redis-cli --scan --pattern 'product:*'   # lista las claves en caché
```

Qué deberías ver: la primera consulta no tiene nada en caché (miss), llena Redis,
y la segunda consulta al mismo EAN se responde desde ahí. Prueba otro EAN
(`7702354030014`) y repite: aparecerá su propia clave. Si esperas 5 minutos la
clave desaparece sola y la siguiente consulta vuelve a ser un miss.

---

## 3. Tarea 2 — Ingesta asíncrona de facturas (RabbitMQ)

### 3.1 Qué se implementó

El flujo "la tienda envía un lote → la central lo inserta en MySQL" ahora pasa
por una cola:

```
tienda (forwarder) ──POST /sales/batch──▶ central-api ──publica──▶ RabbitMQ
                                                                    │  (cola durable: central.invoices)
                                                                    ▼
                                  central-ingestion-worker ◀──consume──┘
                                      │  (el ÚNICO que escribe en MySQL)
                                      ▼
                                   MySQL (invoices / invoice_items)
```

1. **El endpoint ya no inserta.** Valida el lote como antes (lote vacío,
   cantidades negativas, tienda desconocida → sigue siendo un `400`), publica el
   lote en la cola **`central.invoices`** y responde **`202 Accepted`**.
2. **Un worker separado es el único que escribe.** `central-ingestion-worker`
   escucha la cola y, por cada lote, llama a la misma lógica de siempre
   (`service.ingest_batch`), que usa la constraint
   `UNIQUE (store_id, store_invoice_id)` de MySQL para absorber duplicados.
3. **La garantía de no duplicar facturas no se movió de lugar.** La constraint
   única sigue en el esquema de MySQL y sigue siendo la base de las decisiones.
   La diferencia: ahora quien inserta es el worker, y si un mensaje se
   re-entrega (porque el worker se cayó a mitad de escritura), la constraint
   simplemente lo re-absorbe como "ya lo teníamos". Eso se llama *at-least-once
   + idempotencia = efecto exactly-once*: aunque el mensaje viaje dos veces, el
   dato en la base queda una sola.

### 3.2 Por qué se hizo así

- **El request ya no espera al disco.** La API responde apenas la cola confirma
  que aceptó el lote; escribir en MySQL pasa a ser trabajo de fondo. Si la base
  se pone lenta, la tienda no se entera.
- **La durabilidad se mudó del "commit" a la cola.** La cola es **durable**
  (sobrevive a un reinicio de RabbitMQ) y el mensaje se publica **persistente**
  (escrito a disco) con confirmación del broker. Cuando la API responde `202`,
  head office *ya* se hizo cargo del lote, aunque nadie lo haya insertado aún.
- **El forwarder no necesita cambios de comportamiento.** Antes, la respuesta
  le decía "estas facturas eran nuevas y estas ya las teníamos" y él sellaba
  cada una. Ahora la respuesta le dice "ya me hice cargo de todas" (`accepted`
  = todos los números del lote) y él sella todas. La garantía anti-duplicado no
  depende de su sellado: la decide la constraint contra la que inserta el
  worker.
- **`received_at` es más honesto.** La marca de "cuándo llegó a head office" la
  pone ahora el worker **cuando escribe**, no la API cuando recibe.
- **La resiliencia se conserva.** Si RabbitMQ no responde, el endpoint devuelve
  `503`, el forwarder trata a head office como "caída" y deja el lote en la cola
  de la tienda para reintentarlo — exactamente la misma historia de antes.

### 3.3 Dónde quedó el código

| Archivo | Qué hace |
|---|---|
| `docker-compose.yml` | Servicio **`rabbitmq`** (imagen `rabbitmq:3-management`, en la red `central-net`, con panel web en el puerto `15672`) y servicio **`central-ingestion-worker`** (misma imagen que `central-api`, arranca con `python -m app.ingestion.worker`, en `central-net`, con `CENTRAL_DATABASE_URL` + `RABBITMQ_URL`). Variable `RABBITMQ_URL` y `depends_on` añadidos a `central-api`. |
| `central-api/app/core/config.py` | Lee del entorno `RABBITMQ_URL`. |
| `central-api/app/ingestion/broker.py` **(nuevo)** | El "cliente de RabbitMQ" de head office: `publish_batch(batch)` declara la cola durable `central.invoices`, publica el JSON del lote persistente y **no vuelve hasta que el broker confirma** (publisher confirms). Lanza `BrokerUnavailableError` si no lo logra. |
| `central-api/app/ingestion/service.py` | Nueva función `enqueue_batch(batch)`: valida el lote (igual que antes) y lo publica. Devuelve `accepted` = todos los números del lote, `duplicates` = `[]`. `ingest_batch` (el que escribe) **no cambió**: lo usa el worker. |
| `central-api/app/ingestion/router.py` | `POST /sales/batch` ahora responde **`202 Accepted`**, mapea errores: `400` (lote inválido / tienda desconocida) y `503` (la cola no aceptó). |
| `central-api/app/ingestion/worker.py` **(nuevo)** | El consumidor: lee de `central.invoices`, reconstruye el `BatchRequest`, llama `service.ingest_batch` dentro de una sesión, hace `ack` **después del commit**; si algo falla, `nack` con re-entrega; si el mensaje ni siquiera se puede leer, lo descarta para no envenenar la cola. |
| `central-api/app/core/database.py` | Añade `session_scope()` (mismo patrón que el forwarder `sync`), para que el worker —que no tiene HTTP— pueda abrir y cerrar sesiones. |
| `central-api/requirements.txt` | Añade `pika==1.4.4` (librería de AMQP para publicar/consumir). |
| `central-api/app/ingestion/schemas.py` | Docstring de `BatchResponse` actualizado: `accepted` significa "en cola de head office", duplicados se deciden más abajo. |
| `sync/app/consolidation_tests.py` | Tests adaptados a lo asíncrono: las aserciones contra el reporte central ahora **esperan (polling)** a que el worker escriba; el test de idempotencia envía un lote mezclado (una factura ya-tenida + una nueva) y comprueba que solo la nueva cuenta. |
| `scripts/resilience_test.sh` | El conteo central se lee en bucle hasta alcanzar el esperado, porque el worker escribe un instante después de que head office "drena" la cola de la tienda. |

### 3.4 Cómo probarlo a mano

```bash
make up

# 1) Ver el panel de RabbitMQ (usuario central / clave central_password)
#    Abrir http://localhost:15672  →  verás la cola "central.invoices" (empty)

# 2) Hacer una venta en la tienda 1 (como en el README):
#    abrir http://localhost:8081, agregar 7702001010301 y pagar.

# 3) Ver al worker consumir
make logs CONTAINER=central-ingestion-worker
#    → "Batch from store-1: 1 accepted, 0 already held"

# 4) Lo mismo pero llamando a la API directamente. Ojo con el 202:
curl -i -X POST http://localhost:18100/sales/batch \
  -H "Content-Type: application/json" \
  -d '{"store_id":"store-1","invoices":[{"store_invoice_id":999,"register_id":"store-1-register-1","sold_at":"2026-09-13T10:00:00","total":"2000.00","items":[{"ean":"7702001010301","product_name":"Arroz","quantity":1,"unit_price":"2000.00","subtotal":"2000.00"}]}]}'
#    → HTTP/1.1 202 Accepted

# 5) Idempotencia: repetir el MISMO curl. El 202 vuelve a salir,
#    pero en MySQL solo hay una factura con store_invoice_id=999:
make shell CONTAINER=central-mysql
mysql -u central -pcentral_password central
SELECT store_id, store_invoice_id, register_id, total FROM invoices
WHERE store_invoice_id = 999;
#    → 1 fila, no 2.     (y el worker loguea "0 accepted, 1 already held")

# 6) Caída de RabbitMQ (resiliencia): parar la cola
docker compose stop rabbitmq
curl -i -X POST http://localhost:18100/sales/batch -H "Content-Type: application/json" -d '{"store_id":"store-1","invoices":[]}'
#    → el lote vacío da 400; con un lote válido daría 503 (la cola no aceptó).
#    El forwarder de la tienda verá "Head office unreachable", no sellará nada
#    y reintentará después.
docker compose start rabbitmq
```

### 3.5 El test completo de la suite

```bash
make test            # unit + integración + consolidación + resiliencia
make test-unit       # solo los tests unitarios dentro de los contenedores
```

---

## 4. Resumen de lo nuevo en el sistema

| Servicio nuevo | Imagen | Red | Para qué |
|---|---|---|---|
| `store-1-redis` | `redis:7-alpine` | `store-1-net` | Caché de productos de la tienda 1 |
| `store-2-redis` | `redis:7-alpine` | `store-2-net` | Caché de productos de la tienda 2 |
| `rabbitmq` | `rabbitmq:3-management` | `central-net` | Cola `central.invoices` de ingesta |
| `central-ingestion-worker` | `central-api` (misma imagen) | `central-net` | El único proceso que escribe en MySQL |

Puertos nuevos publicados al host (para inspección): `56379` y `56380` (Redis de
cada tienda) y `15672` (panel de RabbitMQ). Nada de esto está en `wan-net`: las
tiendas no pueden alcanzar ni el caché de la otra ni la cola central.