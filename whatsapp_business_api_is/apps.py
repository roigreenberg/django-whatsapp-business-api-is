import logging
from inspect import getmembers

from django.apps import AppConfig
from django.conf import settings
from django.utils.module_loading import import_string


class WhatsappBusinessApiIsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'whatsapp_business_api_is'
    FUNCTIONS = {}
    VALIDATORS = {}

    def ready(self):
        from .tasks import parse_incoming_message
        settings.INCOMING_PARSER = parse_incoming_message

        for app in settings.INSTALLED_APPS:

            try:
                validators = import_string(f"{app}.bot_validators.Validators")

                for name, func in getmembers(validators):
                    if name.startswith('_'):
                        continue
                    self.VALIDATORS[f"{app}.{name}"] = func
            except ImportError:
                pass

            try:
                functions = import_string(f"{app}.bot_functions.Functions")

                for name, func in getmembers(functions):
                    if name.startswith('_'):
                        continue
                    if name in self.FUNCTIONS:
                        raise ValueError(f"duplicate key '{name}' found")
                    self.FUNCTIONS[name] = func
            except ImportError:
                pass

        logging.debug("\n\n[Functions]\n  . " + '\n  . '.join(self.FUNCTIONS.keys()))
        logging.debug("\n\n[validators]\n  . " + '\n  . '.join(self.VALIDATORS.keys()))
