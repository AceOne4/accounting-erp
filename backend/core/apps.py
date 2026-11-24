from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        from core import openapi  # noqa: F401  (registers the schema extension)
