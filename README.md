# Upande CRM

Standalone custom CRM dashboard for Upande, served at `/crm`.

A single-page React app (under `frontend/`, built into `upande_crm/public/frontend/`)
backed by whitelisted endpoints in `upande_crm/api/crm.py`. Access is gated to
sales/CRM roles. Extracted from `customer_portal` into its own app.

## Layout

- `upande_crm/api/crm.py` — `crm_dashboard_*`, `crm_mail_data`, `crm_search`,
  `crm_send_email`, `get_csrf_token` whitelisted methods.
- `upande_crm/www/crm.{html,py}` — the `/crm` route + server boot context.
- `frontend/` — Vite + React source (single build area).

## Develop

```bash
cd frontend
yarn install
yarn build   # → upande_crm/public/frontend + www/crm.html
```
