# Despliegue del backend MANTIS (Render + Stripe test)

Objetivo: una URL HTTPS pública (p. ej. `https://mantis-licensing.onrender.com`) para login, Pro y webhooks de Stripe desde Mac y Windows.

## 1. Subir el código a GitHub

Si aún no tienes repo remoto:

```bash
cd conversor3D
git add backend/Dockerfile backend/render.yaml backend/app/config.py backend/requirements.txt
git commit -m "Add Render deployment for licensing API"
# Crea repo en GitHub y:
git remote add origin https://github.com/TU_USUARIO/conversor3D.git
git push -u origin main
```

## 2. Crear cuenta en Render

1. [render.com](https://render.com) → Sign up (GitHub).
2. **New** → **Blueprint** (o crea a mano Web Service + PostgreSQL).

### Opción A — Blueprint (recomendada)

1. Conecta el repo de GitHub.
2. **Root Directory**: `backend`
3. Render detecta `render.yaml` y crea:
   - PostgreSQL `mantis-db` (free)
   - Web `mantis-licensing` (Docker, free)
4. Tras el primer deploy, copia la URL del servicio (sin `/health`).

### Opción B — Manual

**PostgreSQL**

- New → PostgreSQL → Free → nombre `mantis-db`.

**Web Service**

- New → Web Service → repo → **Root Directory** `backend`
- Runtime: **Docker**
- Plan: Free
- Health check path: `/health`

Variables de entorno (Environment):

| Variable | Valor |
|----------|--------|
| `SECRET_KEY` | Genera una clave larga aleatoria |
| `DATABASE_URL` | Internal Database URL del Postgres (Render la da) |
| `STRIPE_SECRET_KEY` | `sk_test_...` del Dashboard Stripe |
| `STRIPE_PRICE_ID_PRO` | `price_...` de MANTIS Pro |
| `STRIPE_WEBHOOK_SECRET` | Lo creas en el paso 3 |
| `FRONTEND_SUCCESS_URL` | `https://TU-SERVICIO.onrender.com/health` |
| `FRONTEND_CANCEL_URL` | `https://TU-SERVICIO.onrender.com/health` |
| `RESEND_API_KEY` | API key de [resend.com](https://resend.com) (recuperar contraseña) |
| `EMAIL_FROM` | Remitente verificado, p. ej. `MANTIS 3D <noreply@tudominio.com>` |
| `RESET_CODE_EXPIRE_MINUTES` | Opcional (por defecto `15`) |

Sin `RESEND_API_KEY` el código de reset solo aparece en los **logs** de Render (útil en pruebas locales; en producción configúralo).

### Recuperar contraseña (flujo en la app)

1. Login → **¿Olvidaste tu contraseña?**
2. Email → **Enviar código**
3. El usuario recibe un código de 6 dígitos
4. Introduce código + nueva contraseña → **Actualizar contraseña**

Endpoints: `POST /auth/forgot-password` y `POST /auth/reset-password`.

Deploy. Cuando esté **Live**, prueba:

`https://TU-SERVICIO.onrender.com/health` → `{"status":"ok",...}`

## 3. Webhook Stripe (producción / test remoto)

Ya **no** uses `stripe listen` local. En Stripe (modo **Test**):

1. **Developers** → **Webhooks** → **Add endpoint**
2. URL: `https://TU-SERVICIO.onrender.com/billing/webhooks/stripe`
3. Eventos:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. Copia **Signing secret** (`whsec_...`) → variable `STRIPE_WEBHOOK_SECRET` en Render → **Redeploy**.

## 4. Conectar la app desktop

### Sin recompilar (rápido en Windows)

Crea el archivo:

`C:\Users\TU_USUARIO\.mantis3d\config.json`

```json
{
  "api_url": "https://TU-SERVICIO.onrender.com"
}
```

Reinicia MANTIS 3D. Deberían activarse **Iniciar sesión** y **Mejorar a Pro**.

### Build de producción (Mac / Windows)

Antes de PyInstaller, crea `packaging/mantis_api_url.txt` con una sola línea:

```
https://TU-SERVICIO.onrender.com
```

Inclúyelo en el spec (ya preparado) y vuelve a empaquetar.

## 5. Notas

- **Plan free de Render**: el servicio duerme tras inactividad; la primera petición puede tardar ~30–60 s (despertar).
- **SQLite no** en Render: usa Postgres (el blueprint ya lo configura).
- **No subas** `.env` con claves a GitHub.
- Para venta real: cambia Stripe a **Live** y repite keys + webhook con `sk_live_...`.

## Comprobar desde terminal

```bash
curl https://TU-SERVICIO.onrender.com/health
```

Registro de prueba:

```bash
curl -X POST https://TU-SERVICIO.onrender.com/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}'
```
