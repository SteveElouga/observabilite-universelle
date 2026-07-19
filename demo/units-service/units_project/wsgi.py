"""Point d'entrée WSGI pour units-service."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "units_project.settings")

application = get_wsgi_application()
