"""HTTPS reviewer deployment; local development keeps using config.settings."""
import os
from .settings import *

DEBUG = False
hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if hostname:
    ALLOWED_HOSTS = [hostname]
    CSRF_TRUSTED_ORIGINS = [f"https://{hostname}"]
elif not os.environ.get("DJANGO_ALLOWED_HOSTS"):
    raise RuntimeError("Set DJANGO_ALLOWED_HOSTS to the exact review hostname.")
if not os.environ.get("DJANGO_SECRET_KEY"):
    raise RuntimeError("Set a persistent DJANGO_SECRET_KEY for hosting.")
if os.environ.get("DATABASE_URL"):
    import dj_database_url
    DATABASES = {"default": dj_database_url.config(conn_max_age=60, ssl_require=True)}
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True

if hostname:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
