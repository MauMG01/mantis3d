# Backend de licencias MANTIS

API FastAPI que gestiona autenticación, suscripciones Stripe y límites Demo/Pro.

## Arranque local

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edita claves Stripe
uvicorn app.main:app --reload --port 8000
```

Health check: http://127.0.0.1:8000/health

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/auth/register` | Crear cuenta |
| POST | `/auth/login` | Obtener JWT |
| GET | `/me/subscription` | Plan actual + uso |
| POST | `/usage/conversion` | Contar conversión Demo |
| POST | `/billing/checkout` | Stripe Checkout → Pro |
| POST | `/billing/portal` | Portal de cliente Stripe |
| POST | `/billing/webhooks/stripe` | Webhooks Stripe |

## Stripe

1. Crea un producto **MANTIS Pro** (suscripción).
2. Copia el `price_...` a `STRIPE_PRICE_ID_PRO`.
3. Configura el webhook apuntando a `/billing/webhooks/stripe` con eventos:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`

## Conectar la app desktop

```bash
export MANTIS_API_URL=http://127.0.0.1:8000
# Desarrollo sin Stripe:
export MANTIS_PLAN=demo   # o pro
```

O en el PC del usuario: `~/.mantis3d/config.json` → `{"api_url": "https://..."}`.

Despliegue en internet: ver **[DEPLOY.md](DEPLOY.md)** (Render + Stripe webhook).
