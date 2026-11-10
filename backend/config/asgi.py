import os

from django.core.asgi import get_asgi_application

# Settings must be configured and apps loaded *before* importing anything that
# touches models (the JWT middleware and consumers do). runserver hides this
# because manage.py sets the variable first; daphne/uvicorn import this file directly.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django_asgi_application = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from messaging.middleware import JWTAuthMiddleware  # noqa: E402
from messaging.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_application,
        "websocket": JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
    }
)
