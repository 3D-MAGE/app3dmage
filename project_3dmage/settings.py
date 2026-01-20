from pathlib import Path
import os
import dj_database_url
import dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Carica il file .env solo se esiste
dotenv.load_dotenv(BASE_DIR / '.env', override=True)

# --- Ambiente: Produzione o Sviluppo ---
IS_PRODUCTION = 'PYTHONANYWHERE_DOMAIN' in os.environ

if IS_PRODUCTION:
    # --- Produzione su PythonAnywhere ---
    SECRET_KEY = os.environ.get('SECRET_KEY', 'unsafe-default-key')
    DEBUG = False
    DOMAIN = os.environ.get('PYTHONANYWHERE_DOMAIN')
    ALLOWED_HOSTS = [DOMAIN, f"{DOMAIN}.pythonanywhere.com"]
    CSRF_TRUSTED_ORIGINS = [f"https://{DOMAIN}.pythonanywhere.com"]
else:
    # --- Locale ---
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-insecure-key')
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
]

if not IS_PRODUCTION:
    INSTALLED_APPS.append('debug_toolbar')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

if not IS_PRODUCTION:
    MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')

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

# Override the default SQLite configuration to add OPTIONS if it's SQLite
if DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
    DATABASES['default'].setdefault('OPTIONS', {})
    DATABASES['default']['OPTIONS']['timeout'] = 20 # Aumentato per ridurre i lock su Google Drive


# --- Password Validation ---
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- Static files ---
STATIC_URL = 'static/'
STATICFILES_DIRS = []
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# --- Locale ---
# --- Locale ---
LANGUAGE_CODE = 'it'
TIME_ZONE = 'Europe/Rome'
USE_I18N = True
USE_L10N = False  # Disabilitato per forzare i formati qui sotto
USE_TZ = True

# Formati Data
DATE_FORMAT = 'd/m/Y' 
DATETIME_FORMAT = 'd/m/Y H:i'
SHORT_DATE_FORMAT = 'd/m/Y'
SHORT_DATETIME_FORMAT = 'd/m/Y H:i'
DATE_INPUT_FORMATS = ['%d/%m/%Y', '%Y-%m-%d']
DATETIME_INPUT_FORMATS = ['%d/%m/%Y %H:%M', '%Y-%m-%d %H:%M']

# --- Chiavi primarie e autenticazione ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

INTERNAL_IPS = ['127.0.0.1'] if not IS_PRODUCTION else []

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'project_dashboard'
# --- Media files (Uploads) ---
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
