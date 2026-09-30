"""WSGI config for healtrip project."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "healtrip.settings")

application = get_wsgi_application()
