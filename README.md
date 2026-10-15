# Showcase Store API

A Django REST Framework ecommerce project for learning and portfolio demos. It includes JWT registration/login, a browsable product catalog, filtering and pagination, customer profiles, nested product reviews, user-owned carts, and checkout with inventory checks and order history.

This is a development showcase. The included credentials and local settings are for demos only; do not deploy them as-is.

## Quick start

Requires Python 3.10 or newer.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

By default, SQLite uses `showcase.sqlite3`, so the historical `db.sqlite3` is preserved. The `.env` file is optional for local development. Settings read the environment directly; PowerShell can set values with `$env:DJANGO_SECRET_KEY = "..."` before starting Django. The committed example key and demo credentials are not secrets.

Open the [API docs](http://127.0.0.1:8000/api/docs/) or Django admin at [admin](http://127.0.0.1:8000/admin/). Demo admin credentials: `demo-admin` / `Demo-admin-123!`; demo customer: `demo-customer` / `Demo-customer-123!`.

## API tour

- Public catalog: `GET /store/products/`, `GET /store/collections/`
- Product filters: `?collection_id=1`, `?unit_price__lt=30`, `?unit_price__gt=10`
- Search and ordering: `?search=canvas`, `?ordering=-unit_price`
- Registration: `POST /auth/users/`
- Get JWT: `POST /auth/jwt/create/` with username and password; send `Authorization: Bearer <access>` on authenticated routes.
- Refresh JWT: `POST /auth/jwt/refresh/`; rotation/blacklisting are enabled locally.
- Profile: `GET|PUT /store/customers/me/`
- Shipping address: `GET|PUT /store/customers/address/`
- Cart: `POST /store/carts/`, then use `/store/carts/{uuid}/items/` to add products and `GET /store/carts/{uuid}/` to view it.
- Checkout: `POST /store/orders/` with `{"cart_id":"<uuid>"}`. Checkout validates stock, reduces inventory, creates order item price snapshots, and consumes the cart in one transaction.
- Order history: `GET /store/orders/` returns only the signed-in user's orders; staff can review all orders.
- Reviews: `/store/products/{product_id}/reviews/`

Admin users can create/update catalog data. Product inventory may be set to zero; negative stock is invalid. Prices are represented as decimal strings in API responses.
Cart quantities are positive and capped at 100 per product line.

## Development commands

```powershell
python manage.py test
python manage.py check
python manage.py makemigrations --check
python manage.py seed_demo
```

Set `DATABASE_ENGINE=django.db.backends.mysql` and `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT` to run against MySQL. SQLite remains the default and is enough for the showcase.

## Scope notes

Guest carts, payment-provider integration, shipping, email verification, and a frontend are not included. Checkout is a functional local demo flow; it is not a payment system. Demo passwords and the fallback secret key are intentionally convenient and must be replaced for any shared or deployed environment.
