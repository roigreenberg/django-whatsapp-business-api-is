import logging
from inspect import getmembers

from django.apps import AppConfig
from django.conf import settings
from django.utils.module_loading import import_string

from whatsapp_business_api_is.conf import Conf


class WhatsappBusinessApiIsConfig(AppConfig):
    """
    # General configuration for Whatsapp Business Api Infrastructure

    ## incoming_parser
    ### a function loaded from `Conf.INCOMING_PARSER`.
    The `incoming_parser` receive the raw msg object as received from Whatsapp webhook
    By default it uses `whatsapp_business_api_is.tasks.parse_incoming_message`

    ## set_state
    ### a function to run when the user state is changed

    ## FUNCTIONS
    ### a flat dictionary for all methods of `Functions` class defined in `bot_functions.py` of all registered apps
    Those functions can be used by the messages objects by name.
    Each function name must be unique.

    The signature for all functions must be `user, msg, msg_obj=None, data=None`
    @user - the WaUser object
    @msg - the received user message (instance of `BaseMsg`, depend on the received message)
    @msg_obj - can be either OutgoingMessage or IncomingMessage
    @data - the action's data as defined in the msg_obj

    Example:

    An IncomingMessage object:
    ```
    - model: whatsapp_business_api_is.IncomingMessage
      pk: incoming_example
      fields:
        reply: outgoing_example
        type: user_start
        pattern: "example"
        actions:
          function1:
    ```
    An OutgoingMessage object:
    ```
    - model: whatsapp_business_api_is.IncomingMessage
      pk: outgoing_example
        fields:
          type: text
          text: |
            Hello
          actions:
            function2:
              field: "example"
    ```
    functions objects:
    ```
    #app1/bot_functions.py

    class Functions:
        @staticmethod
        def function1(user, msg, msg_obj=None, data=None):
            pass
    ```
    ```
    #app2/bot_functions.py

    class Functions:
        @staticmethod
        def function2(user, msg, msg_obj=None, data=None):
            pass
    ```

    When a user with the number 1234 will send "example", first we run `function1` with:
    ```
    user=WaUser(number='12345')
    msg=TextMsg(text="example")
    msg_obj=IncomingMessage(pk="incoming_example")
    data=None
    ```
    Then before sending `outgoing_example` we run `function2` with:
    ```
    user=WaUser(number='12345')
    msg=TextMsg(text="example")
    msg_obj=OutgoingMessage(pk="outgoing_example")
    data={ field: "example" }
    ```

    ## VALIDATORS
    ### a flat dictionary for all methods of `Validators` class defined in `bot_validators.py` of all registered apps
    Those functions can be used by the messages objects by name.
    Unlike FUNCTIONS, VALIDATORS are saved with the app label {app}.{validator}

    The signature for all validators must be `user, msg, msg_obj, validation_message=''`
    @user - the WaUser object
    @msg - the received user message (instance of `BaseMsg`, depend on the received message)
    @msg_obj - can be either OutgoingMessage or IncomingMessage
    @validation_message - custom text to be sent to the user in case of validation e

    In case of validation error the method should call `raise ValidationError(validation_message, params={'custom_message': True})`
    The validators are called by `whatsapp_business_api_is.utils.validate_value`.

    If there is no validation message, the bot will send `OutgoingMessage(pk="wrong_format")` message.
    """
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
