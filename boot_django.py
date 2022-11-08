# boot_django.py
#
# This file sets up and configures Django. It's used by scripts that need to
# execute as if running in a Django server.
import os

import django
from django.conf import settings

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "whatsapp_business_api_is"))


def boot_django():
    REDIS_URL=os.environ.get("REDIS_URL", "redis://redis:6379")
    settings.configure(
        BASE_DIR=BASE_DIR,
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
            }
        },
        REDIS_URL=REDIS_URL,
        CELERY_BROKER_URL=REDIS_URL,
        CELERY_RESULT_BACKEND=REDIS_URL,
        WAB_IS={
            "D360_BASE_URL": os.environ.get("D360_BASE_URL", "https://waba-sandbox.360dialog.io/v1/"),
            "D360_API_KEY": os.environ.get("D360_API_KEY", ""),
            "DEBUG": True,
        },
        INSTALLED_APPS=(
            "whatsapp_business_api_is",
        ),
        TIME_ZONE="UTC",
        USE_TZ=True,
    )
    django.setup()
