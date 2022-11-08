import logging
from inspect import getmembers

from django.apps import AppConfig
from django.conf import settings
from django.utils.module_loading import import_string

from whatsapp_business_api_is.conf import Conf


class WhatsappBusinessApiIsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'whatsapp_business_api_is'
    FUNCTIONS = {}
    VALIDATORS = {}
    incoming_parser = None
    set_state = None

    def ready(self):
        try:
            WhatsappBusinessApiIsConfig.incoming_parser = import_string(Conf.INCOMING_PARSER)
            assert callable(WhatsappBusinessApiIsConfig.incoming_parser)
        except AssertionError:
            raise ValueError(f'Conf.INCOMING_PARSER is not a function. Got: {Conf.INCOMING_PARSER}')

        if Conf.SET_STATE:
            try:
                WhatsappBusinessApiIsConfig.set_state = import_string(Conf.SET_STATE)
                assert callable(WhatsappBusinessApiIsConfig.set_state)
            except AssertionError:
                raise ValueError(f'Conf.SET_STATE is not a function. Got: {Conf.SET_STATE}')

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
