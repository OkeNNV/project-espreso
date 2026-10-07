"""Налаштування для локальної розробки."""
import os

from .base import *  # noqa: F401,F403

DEBUG = True

SECRET_KEY = os.getenv(
    'SECRET_KEY',
    'django-insecure-#xj2_l7!umguqbh5a=v7%9u490nzy*dn)u-+#!438%oc7y=q_e',
)

ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
