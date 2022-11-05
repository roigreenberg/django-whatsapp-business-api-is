import logging
from importlib.machinery import SourceFileLoader
from inspect import getmembers

from django.apps import AppConfig
from django.conf import settings


class WhatsappBusinessApiIsConfig(AppConfig):
    default_auto_field = 'django.db._models.BigAutoField'
    name = 'whatsapp_business_api_is'
    ACTIONS = {}
    VALIDATORS = {}

    def ready(self):
        from .tasks import parse_incoming_message
        settings.INCOMING_PARSER = parse_incoming_message

        for app in settings.INSTALLED_APPS:

            try:
                foo = SourceFileLoader("bot_validators", f"{app}/bot_validators.py").load_module()

                for name, func in getmembers(foo.Validators):
                    if name.startswith('_'):
                        continue
                    self.VALIDATORS[f"{app}.{name}"] = func
            except FileNotFoundError:
                pass

            try:
                foo = SourceFileLoader("bot_actions", f"{app}/bot_actions.py").load_module()

                for name, func in getmembers(foo.Actions):
                    if name.startswith('_'):
                        continue
                    if name in self.ACTIONS:
                        raise ValueError(f"duplicate key '{name}' found")
                    self.ACTIONS[name] = func
            except FileNotFoundError:
                pass

        logging.debug("\n\n[actions]\n  . " + '\n  . '.join(self.ACTIONS.keys()))
        logging.debug("\n\n[validators]\n  . " + '\n  . '.join(self.VALIDATORS.keys()))
