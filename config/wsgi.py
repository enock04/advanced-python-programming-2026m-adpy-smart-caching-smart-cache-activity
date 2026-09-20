# config/wsgi.py

import os

from django.core.wsgi import get_wsgi_application


# Tell Django which settings module to use
settings_module = "config.settings"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)


# Create the WSGI application
application = get_wsgi_application()
