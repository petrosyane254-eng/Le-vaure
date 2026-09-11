# LE VAURÉ — Django Shop

Ready for PyCharm.

## First run (Windows)
Open this entire folder in PyCharm. The Django module uses the existing
`.venv`, root `shop/manage.py`, and `scorpion.settings`. If the project was already
open while its `.idea` configuration was restored, reopen it to load the module.

In the project-root PowerShell terminal:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py check
python manage.py runserver
```

If activation is unavailable, use `.\.venv\Scripts\python.exe` in place of
`python`. For a new database, run `python manage.py migrate` and optionally
`python manage.py createsuperuser` before starting. Existing databases should
be backed up before applying pending migrations. Do not regenerate migrations
or seed products as part of ordinary startup.

Shop: http://127.0.0.1:8000/
Admin: http://127.0.0.1:8000/southward-control-7x9/

Private shop access remains controlled by Site Access settings in the admin.
The language selectors POST to Django's `set_language` endpoint and persist
EN/HY/DE/RU/FR in the `django_language` cookie. After editing `.po` translations,
run `python manage.py compilemessages` (requires GNU gettext).

## Admin can manage
- Products
- Product prices
- Stock
- Product images
- Categories
- Featured/active products
- Orders and order statuses
- Users (Django Users section)

Checkout uses Stripe when configured. Use test credentials for local testing.


## Email verification

Registration now requires a real email address and a 6-digit verification code.
A new account stays inactive until the code is entered successfully.

### Zero-config test mode
By default Django prints the verification email in the PyCharm Terminal.
This lets you test immediately without an email password.

### Send real email with Gmail SMTP (PowerShell)
Use a Gmail **App Password** (not your normal Gmail password).

```powershell
$env:SCORPION_EMAIL_BACKEND="smtp"
$env:EMAIL_HOST="smtp.gmail.com"
$env:EMAIL_PORT="587"
$env:EMAIL_USE_TLS="1"
$env:EMAIL_HOST_USER="yourgmail@gmail.com"
$env:EMAIL_HOST_PASSWORD="YOUR_GMAIL_APP_PASSWORD"
$env:DEFAULT_FROM_EMAIL="Scorpion Style <yourgmail@gmail.com>"
py manage.py runserver
```

Environment variables disappear after that terminal session, so your password is not stored in the project.

For a production shop, prefer a transactional provider such as Resend, Brevo, SendGrid, Postmark or Amazon SES rather than a personal Gmail account.

## Google Cloud deployment

This project is prepared for Google Cloud Run with PostgreSQL and optional Google Cloud Storage for media.

### What is already in the repo

- `Dockerfile` for Cloud Run container deployment
- PostgreSQL support in `scorpion/settings.py`
- WhiteNoise static serving
- Optional Google Cloud Storage media backend
- `southward.store` allowed/trusted host defaults

### Typical setup

1. Create a Google Cloud project and enable Cloud Run, Cloud SQL, Artifact Registry, Cloud Build, Secret Manager, and Cloud Storage.
2. Create a PostgreSQL Cloud SQL instance and database.
3. Create a Cloud Storage bucket for user-uploaded media, if you want media persisted outside the container.
4. Set production environment variables from `.env`.
5. Build and deploy the container image to Cloud Run.
6. Map `southward.store` and `www.southward.store` to the Cloud Run service.

### Required production env vars

- `SECRET_KEY`
- `DEBUG=0`
- `ALLOWED_HOSTS=southward.store,www.southward.store`
- `CSRF_TRUSTED_ORIGINS=https://southward.store,https://www.southward.store`
- `DB_ENGINE=django.db.backends.postgresql`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`

Optional but recommended:

- `GS_BUCKET_NAME`
- `GS_PROJECT_ID`
- `PRINTIFY_API_TOKEN`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `STRIPE_SECRET_KEY`

### Static and media behavior

- Static files are collected into the container build/runtime using `collectstatic`.
- Media uploads can stay local for testing, but for production use `GS_BUCKET_NAME` so uploads survive container restarts.

### Domain mapping

Map `southward.store` to the deployed Cloud Run service, then add the DNS records Cloud Run gives you at your registrar.
For production, use the Google Cloud domain mapping or a load balancer-based setup rather than depending on the local development server.

## LE VAURÉ redesign package

This package keeps the existing Django models, views, cart, checkout, Stripe/Printify integration and database structure, while replacing the storefront presentation with the LE VAURÉ editorial / quiet-luxury visual system.

### Run locally
1. Create/activate a virtual environment.
2. `pip install -r requirements.txt`
3. Copy `.env` to `.env` and fill your real secrets/settings.
4. `python manage.py migrate`
5. `python manage.py runserver`
6. Open `http://127.0.0.1:8000/`.

### Production domain
The example environment supports `levaure.store` and the IDN form `levauré.store` (punycode: `xn--levaur-gva.store`). Use the exact domain you actually purchase in your deployment/DNS settings.

### Before launch
Create/verify the mailbox `support@levaure.store` or replace it in the legal/account templates with your real support email. Never commit `.env` or payment/API secrets.


## LE VAURÉ Editorial V2
The storefront has been visually unified around the approved ivory / deep-green editorial direction. Updated surfaces include Home, Shop, Product, Wishlist, Account Center, Login, Register, Verify Email, Cart, Checkout, Order Success, global header, benefits, newsletter and footer. Core Django URLs, models, forms, cart/checkout and database behavior were intentionally preserved.

## Final editorial storefront pass
- Shop / collection page redesigned to match the LE VAURÉ editorial homepage.
- Product cards, search, sort, category navigation and empty states use the same ivory/deep-green design system.
- Storefront locale catalogs included for English, Armenian, German, Russian and French (`locale/*/LC_MESSAGES`).
- Demo Scorpion product names were rebranded to LE VAURÉ in the bundled development database and seed command.
- Existing Django cart, checkout, account, wishlist and payment logic remains in place.
