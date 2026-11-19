# ADR-08 · Plataforma de despliegue: Railway

Fecha: 18-nov-2026. Precios y límites consultados ese mismo día en las páginas que se citan abajo.

## Estado

**Aceptada** (18-nov-2026). El MVP corre en https://radica-pqrs.up.railway.app desde el PR #48 (issue #20).

## Contexto

La sustentación del Módulo 6 (19-nov-2026) se hace con la aplicación desplegada en una URL pública. Radica son 4 servicios en `docker-compose.yml`, y el despliegue debía conservarlos sin cambiar `src/` ni romper Compose en local:

- `db`: PostgreSQL 16 con sus datos en un volumen (ADR-07).
- `api`: corre las migraciones y luego uvicorn.
- `trabajador`: la misma imagen con `radica-trabajador`. No recibe tráfico; revisa la cola cada 5 s (ADR-04).
- `web`: nginx sirve la interfaz y lleva la API al mismo origen, así que la API no necesita CORS ni dominio propio.

Restricciones: el presupuesto es el de un proyecto de curso (sin tarjeta, si se puede), solo se usan datos sintéticos y el plazo para desplegar era de un día.

## Decisión

Railway, con un proyecto `radica` de 4 servicios iguales a los de Compose. Solo `web` tiene dominio público; `api` y `db` se alcanzan por la red privada. La configuración está en el README, sección «Despliegue».

Razones:

| # | Razón | Dónde se comprueba |
| --- | --- | --- |
| 1 | Construye los mismos Dockerfile del repositorio. Solo hizo falta un Dockerfile aparte para la interfaz, porque Railway no pasa el contexto «contrato» de Compose | `Dockerfile`, `web/Dockerfile.railway`; registro de construcción de `web` en Railway (44 pruebas de Vitest dentro de la imagen) |
| 2 | Los servicios no se duermen en la prueba ni en Hobby. El trabajador, que no recibe tráfico, sigue tomando la cola | [Free plan](https://docs.railway.com/pricing/free-plan): «Services sleep when idle» es «No» para la prueba; log del trabajador: «revisa las pendientes cada 5 s» |
| 3 | Red privada con DNS interno (`api.railway.internal`, `db.railway.internal`). La API y la base no se publican, como en Compose | [Private networking](https://docs.railway.com/networking/private-networking/how-it-works); `RADICA_API_URL` y `RADICA_RESOLVER` del servicio `web` |
| 4 | PostgreSQL 16 con la misma imagen de Compose (`postgres:16.15-trixie`) y un volumen persistente | `railway service list`: imagen y volumen `db-volume` en `/var/lib/postgresql/data` |
| 5 | Despliega desde GitHub en cada push, y solo cuando pasa el CI («Wait for CI») | Disparadores de despliegue de `api`, `trabajador` y `web` con `checkSuites: true` |
| 6 | El crédito de prueba (USD 5 por 30 días, sin tarjeta) alcanza para la sustentación. En la primera hora con los 4 servicios el consumo fue de USD 0,0014 | [Pricing](https://railway.com/pricing); `railway usage` |

## Alternativas

Precios y límites del 18-nov-2026, tomados de las páginas de cada proveedor. No se desplegó en Render ni en Fly.io.

| Necesidad de Radica | Railway | Render | Fly.io |
| --- | --- | --- | --- |
| Gratis sin tarjeta | Prueba de USD 5 por 30 días, con 5 servicios por proyecto. Después, plan Free con USD 1 al mes y 3 servicios por proyecto | Plan Hobby de USD 0, pero los *background workers* y los *private services* no tienen instancia gratis | Prueba de USD 1, sin tarjeta; las facturas menores de USD 5 no se cobran |
| Trabajador siempre encendido | Sí (prueba y Hobby); en Free se duerme | Solo pagando: desde USD 7 al mes (0,5 CPU, 512 MB) | Sí: una máquina `shared-cpu-1x` de 256 MB cuesta USD 2,19 al mes |
| `web` sin dormirse | Sí (prueba y Hobby) | La instancia gratis se duerme a los 15 minutos sin tráfico y tarda cerca de un minuto en despertar | Sí |
| PostgreSQL con datos persistentes | Imagen propia con volumen | La base gratis vence a los 30 días y tiene 1 GB; la de pago, desde USD 6 al mes | Postgres administrado desde USD 38 al mes, o una máquina propia con un volumen (USD 0,15 por GB al mes) |
| API solo por red privada | Sí | Una web service gratis no recibe tráfico de la red privada: la API tendría que ser un *private service* pagado | No se revisó |
| Configuración | Panel y CLI; el README la documenta | Infraestructura como código (Blueprint) | `flyctl` y `fly.toml` |

Fuentes: [railway.com/pricing](https://railway.com/pricing), [docs.railway.com/pricing/free-plan](https://docs.railway.com/pricing/free-plan), [render.com/pricing](https://render.com/pricing), [render.com/docs/free](https://render.com/docs/free) y [fly.io/pricing](https://fly.io/pricing).

1. **Render.** A favor: una web service gratis serviría para `web` y su Blueprint deja la configuración en el repositorio. En contra: el trabajador y la API privada exigen instancias de pago (con tarjeta), la base gratis vence a los 30 días y la interfaz gratis se duerme, así que la primera visita de la sustentación tardaría cerca de un minuto.
2. **Fly.io.** A favor: es barato por máquina y no duerme los servicios. En contra: la prueba es de USD 1, así que el despliegue se pagaría desde el primer día; el Postgres administrado empieza en USD 38 al mes, y la alternativa es mantener PostgreSQL en una máquina propia con su volumen.

## Consecuencias

Ventajas:

- El despliegue usa los mismos Dockerfile y el mismo orden que Compose: las migraciones corren al arrancar la API.
- Solo `web` está expuesta, por HTTPS con el certificado de Railway. Cierra la diferencia «HTTPS entre las personas y Radica» de `docs/arquitectura.md`.
- Ningún secreto está en el repositorio. La contraseña de la base y las llaves de cifrado y HMAC se generaron nuevas para Railway, y `IA_API_KEY` se pegó en el panel.

Costos:

- La prueba termina a los 30 días (el 13-dic-2026, según el panel del 18-nov-2026) o al gastar USD 5. Después los servicios se detienen. Para mantenerlos hay que pasar a Hobby (USD 5 al mes), porque el plan Free solo admite 3 servicios por proyecto y duerme el trabajador.
- La configuración de los servicios vive en Railway, no en el repositorio. Su configuración como código (`railway.json`) está obsoleta: deja de leerse el 1-dic-2026, y los servicios nuevos ya no pueden usarla. Su reemplazo (`.railway/railway.ts`) agregaría una dependencia de npm. Por eso el README documenta cada ajuste.
- nginx usa `[fd12::10]` como DNS interno de Railway. La documentación oficial no lo da: sale de respuestas del personal de Railway en su foro.
- La URL está abierta: no hay autenticación (#22). La interfaz muestra un aviso de datos sintéticos, y la clave de Anthropic tiene un límite de gasto de USD 5 en la consola de Anthropic (#37).
- Los servicios corren en la región `sfo` (Estados Unidos). Hoy solo se usan datos sintéticos; con datos reales habría que revisar dónde se guardan.
