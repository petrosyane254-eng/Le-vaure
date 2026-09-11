from pathlib import Path
import os

from dotenv import load_dotenv
from django.urls import reverse_lazy


# =========================================================
# BASE DIRECTORY
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

load_dotenv(BASE_DIR / ".env")


# =========================================================
# DJANGO BASIC SETTINGS
# =========================================================

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "scorpion-dev-key-change-before-production",
)

DEBUG = os.getenv("DEBUG", "1") == "1"


# =========================================================
# ALLOWED HOSTS
# =========================================================

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "[::1]",
    "southward.store",
    "www.southward.store",
    "southward-store.onrender.com",
    "levaure.store",
    "www.levaure.store",
]

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = DEFAULT_ALLOWED_HOSTS + [
        "levaure.store",
        "www.levaure.store",
        "xn--levaur-gva.store",
        "www.xn--levaur-gva.store",
    ]


# =========================================================
# CSRF
# =========================================================

CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "https://levaure.store",
    "https://www.levaure.store",
    "https://xn--levaur-gva.store",
    "https://www.xn--levaur-gva.store",
]

CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"

if DEBUG:
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
else:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True

# =========================================================
# INSTALLED APPS
# =========================================================

INSTALLED_APPS = [
    "unfold",

    "django.contrib.sitemaps",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "storages",
    "django.contrib.humanize",

    "shop",
]


# =========================================================
# MIDDLEWARE
# =========================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",

    # Must stay after SessionMiddleware.
    "django.middleware.locale.LocaleMiddleware",

    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",

    "shop.middleware.SiteAccessMiddleware",

    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =========================================================
# URL CONFIG
# =========================================================

ROOT_URLCONF = "scorpion.urls"


# =========================================================
# TEMPLATES
# =========================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",

        "DIRS": [
            BASE_DIR / "templates",
        ],

        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",

                "shop.context_processors.shop_context",
            ],
        },
    },
]


# =========================================================
# WSGI
# =========================================================

WSGI_APPLICATION = "scorpion.wsgi.application"


# =========================================================
# DATABASE
# =========================================================

DB_ENGINE = os.getenv(
    "DB_ENGINE",
    "django.db.backends.sqlite3",
)

if DB_ENGINE == "django.db.backends.postgresql":

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "scorpion"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }

else:

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


if DEBUG:
    DATABASES["default"].setdefault(
        "CONN_MAX_AGE",
        0,
    )
else:
    DATABASES["default"].setdefault(
        "CONN_MAX_AGE",
        60,
    )


# =========================================================
# PASSWORD VALIDATION
# =========================================================

AUTH_PASSWORD_VALIDATORS = []


# =========================================================
# LANGUAGE / TIMEZONE
# =========================================================

LANGUAGE_CODE = "en"

LANGUAGES = [
    ("en", "English"),
    ("hy", "Հայերեն"),
    ("de", "Deutsch"),
    ("ru", "Русский"),
    ("fr", "Français"),
]

LOCALE_PATHS = [
    BASE_DIR / "locale",
]

USE_I18N = True

USE_TZ = True

APPEND_SLASH = True


# =========================================================
# LANGUAGE COOKIE
# =========================================================

LANGUAGE_COOKIE_NAME = "django_language"

LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 365

LANGUAGE_COOKIE_SAMESITE = "Lax"



# =========================================================
# STATIC FILES
# =========================================================

STATIC_URL = "static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_STORAGE = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
)


# =========================================================
# MEDIA FILES
# =========================================================

MEDIA_URL = "media/"

MEDIA_ROOT = BASE_DIR / "media"


# =========================================================
# GOOGLE CLOUD STORAGE
# =========================================================

GS_BUCKET_NAME = os.getenv(
    "GS_BUCKET_NAME",
    "",
).strip()

if GS_BUCKET_NAME:

    GS_PROJECT_ID = os.getenv(
        "GS_PROJECT_ID",
        "",
    ).strip()

    GS_DEFAULT_ACL = os.getenv(
        "GS_DEFAULT_ACL",
        "publicRead",
    )

    GS_QUERYSTRING_AUTH = (
        os.getenv(
            "GS_QUERYSTRING_AUTH",
            "0",
        )
        == "1"
    )

    STORAGES = {
        "default": {
            "BACKEND": (
                "storages.backends.gcloud.GoogleCloudStorage"
            ),
        },

        "staticfiles": {
            "BACKEND": (
                "whitenoise.storage."
                "CompressedManifestStaticFilesStorage"
            ),
        },
    }

else:

    STORAGES = {
        "default": {
            "BACKEND": (
                "django.core.files.storage.FileSystemStorage"
            ),
        },

        "staticfiles": {
            "BACKEND": (
                "whitenoise.storage."
                "CompressedManifestStaticFilesStorage"
            ),
        },
    }


# =========================================================
# PRODUCTION SECURITY
# =========================================================

if not DEBUG:

    SECURE_PROXY_SSL_HEADER = (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )

    SESSION_COOKIE_SECURE = True

    CSRF_COOKIE_SECURE = True

    SECURE_SSL_REDIRECT = True

    SECURE_HSTS_SECONDS = 31536000

    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

    SECURE_HSTS_PRELOAD = True

    SECURE_CONTENT_TYPE_NOSNIFF = True

    SECURE_REFERRER_POLICY = "same-origin"


# =========================================================
# DEFAULT PRIMARY KEY
# =========================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# =========================================================
# LOGIN / LOGOUT
# =========================================================

LOGIN_URL = "/login/"

LOGIN_REDIRECT_URL = "/"

LOGOUT_REDIRECT_URL = "/"


# =========================================================
# RESEND EMAIL
# =========================================================

RESEND_API_KEY = os.getenv(
    "RESEND_API_KEY",
    "",
).strip()

RESEND_FROM_EMAIL = os.getenv(
    "RESEND_FROM_EMAIL",
    "LE VAURÉ <onboarding@resend.dev>",
).strip()

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    RESEND_FROM_EMAIL,
).strip()

EMAIL_TIMEOUT = int(
    os.getenv(
        "EMAIL_TIMEOUT",
        "10",
    )
)


# =========================================================
# SMTP EMAIL
# =========================================================

EMAIL_HOST = os.getenv(
    "EMAIL_HOST",
    "smtp.gmail.com",
)

EMAIL_PORT = int(
    os.getenv(
        "EMAIL_PORT",
        "587",
    )
)

EMAIL_USE_TLS = (
    os.getenv(
        "EMAIL_USE_TLS",
        "1",
    )
    == "1"
)

EMAIL_HOST_USER = os.getenv(
    "EMAIL_HOST_USER",
    "",
)

EMAIL_HOST_PASSWORD = os.getenv(
    "EMAIL_HOST_PASSWORD",
    "",
)


# =========================================================
# EMAIL BACKEND
# =========================================================
#
# Resend verification code can call Resend API directly.
#
# Django send_mail() will use SMTP only if SMTP username/password
# are configured. Otherwise local development uses console backend.
# =========================================================

if os.getenv(
    "SCORPION_EMAIL_BACKEND",
    "",
).lower() == "console":

    EMAIL_BACKEND = (
        "django.core.mail.backends.console.EmailBackend"
    )

elif EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:

    EMAIL_BACKEND = (
        "django.core.mail.backends.smtp.EmailBackend"
    )

else:

    EMAIL_BACKEND = (
        "django.core.mail.backends.console.EmailBackend"
    )


# =========================================================
# EMAIL VERIFICATION
# =========================================================

SCORPION_VERIFICATION_MINUTES = int(
    os.getenv(
        "SCORPION_VERIFICATION_MINUTES",
        "10",
    )
)


# =========================================================
# CEO ORDER NOTIFICATION
# =========================================================

CEO_ORDER_NOTIFICATION_EMAIL = os.getenv(
    "CEO_ORDER_NOTIFICATION_EMAIL",
    "",
).strip()


# =========================================================
# PRINTIFY
# =========================================================

PRINTIFY_API_TOKEN = os.getenv(
    "PRINTIFY_API_TOKEN",
    "",
).strip()


# =========================================================
# STRIPE
# =========================================================

STRIPE_PUBLISHABLE_KEY = os.getenv(
    "STRIPE_PUBLISHABLE_KEY",
    "",
).strip()

STRIPE_SECRET_KEY = os.getenv(
    "STRIPE_SECRET_KEY",
    "",
).strip()

STRIPE_WEBHOOK_SECRET = os.getenv(
    "STRIPE_WEBHOOK_SECRET",
    "",
).strip()


# =========================================================
# UNFOLD
# =========================================================

UNFOLD = {
    "SITE_TITLE": "LE VAURÉ Admin",

    "SITE_HEADER": "LE VAURÉ ADMIN",

    "SITE_SUBHEADER": "Store Control Center",

    "SITE_SYMBOL": "shopping_bag",

    "SHOW_HISTORY": True,

    "SHOW_VIEW_ON_SITE": True,

    "SIDEBAR": {
        "show_search": True,

        "show_all_applications": False,

        "navigation": [
            {
                "title": "Store",

                "separator": True,

                "items": [
                    {
                        "title": "Dashboard",

                        "icon": "dashboard",

                        "link": reverse_lazy(
                            "admin:index"
                        ),
                    },

                    {
                        "title": "My Products",

                        "icon": "inventory_2",

                        "link": reverse_lazy(
                            "admin:shop_product_changelist"
                        ),
                    },

                    {
                        "title": "Categories",

                        "icon": "category",

                        "link": reverse_lazy(
                            "admin:shop_category_changelist"
                        ),
                    },
                ],
            },

            {
                "title": "Orders",

                "separator": True,

                "items": [
                    {
                        "title": "Orders",

                        "icon": "shopping_cart",

                        "link": reverse_lazy(
                            "admin:shop_order_changelist"
                        ),
                    },

                    {
                        "title": "Order Items",

                        "icon": "receipt_long",

                        "link": reverse_lazy(
                            "admin:shop_orderitem_changelist"
                        ),
                    },
                ],
            },

            {
                "title": "Customers",

                "separator": True,

                "items": [
                    {
                        "title": "Users",

                        "icon": "group",

                        "link": reverse_lazy(
                            "admin:auth_user_changelist"
                        ),
                    },

                    {
                        "title": "Wishlists",

                        "icon": "favorite",

                        "link": reverse_lazy(
                            "admin:shop_wishlist_changelist"
                        ),
                    },

                    {
                        "title": "Email Verifications",

                        "icon": "verified_user",

                        "link": reverse_lazy(
                            "admin:shop_emailverification_changelist"
                        ),
                    },
                ],
            },
        ],
    },
}