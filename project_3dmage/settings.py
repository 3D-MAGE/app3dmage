from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Ambiente: Produzione o Sviluppo ---
IS_PRODUCTION = 'PYTHONANYWHERE_DOMAIN' in os.environ


if 'PYTHONANYWHERE_DOMAIN' in os.environ:
    # --- PythonAnywhere ---
    SECRET_KEY = os.environ.get('SECRET_KEY', 'unsafe-default-key')
    DEBUG = False
    PA_DOMAIN = os.environ.get('PYTHONANYWHERE_DOMAIN')
    ALLOWED_HOSTS = [PA_DOMAIN, f"{PA_DOMAIN}.pythonanywhere.com"]
    CSRF_TRUSTED_ORIGINS = [f"https://{PA_DOMAIN}.pythonanywhere.com"]

else:
    # --- Locale ---
    SECRET_KEY = 'django-insecure-ctq!%_ci$qoua%4&8re4v*(dkvtlz$o+(s#*v9()_t7a9ivg5#'
    DEBUG = True
    ALLOWED_HOSTS = []
    CSRF_TRUSTED_ORIGINS = []

# --- App e Middleware ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'app_3dmage_management',
    'debug_toolbar',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

ROOT_URLCONF = 'project_3dmage.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'project_3dmage.wsgi.application'

# --- Database ---
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600
    )
}

# validation ---
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- Internationalization ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# --- Static files ---
STATIC_URL = 'static/'
STATICFILES_DIRS = []
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# --- Default primary key field type ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Debug Toolbar ---
INTERNAL_IPS = ["127.0.0.1"]

# --- Redirects ---
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
