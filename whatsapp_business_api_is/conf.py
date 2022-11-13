from django.conf import settings


class Conf:
    """
    Configuration class
    """

    try:
        conf = settings.WAB_IS
    except AttributeError:
        conf = {}

    DEBUG = conf.get("debug", False)

    ENV = conf.get("env", "production")

    DEMO_MODE = conf.get("demo_mode", False)

    D360_BASE_URL = conf.get("d360_base_url", "https://waba-sandbox.360dialog.io/v1/")

    D360_API_KEY = conf.get("d360_api_key", "")

    AUTH_HEADER = conf.get("auth_header", {'D360-API-KEY': D360_API_KEY, })

    TO_FIELD_NAME = conf.get("to_field_name", "to")

    INCOMING_PARSER = conf.get("incoming_parser", "whatsapp_business_api_is.tasks.parse_incoming_message")

    SET_STATE = conf.get("set_state", None)

    DEFAULT_NUMBER_PREFIX = conf.get("default_number_prefix", "972")

    TEMPLATE_LANG_CODE = conf.get("template_lang_code", "he")
