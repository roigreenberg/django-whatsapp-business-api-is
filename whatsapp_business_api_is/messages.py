import copy
import json
import logging
import os
import re

import requests

from whatsapp_business_api_is.conf import Conf
from whatsapp_business_api_is.models import OutgoingMessage, TYPE_MEDIA, TYPE_QUICK_REPLY
from whatsapp_business_api_is.utils import get_data, get_quick_replies_as_flat_list, run_actions, run_action, set_state, \
    is_data_exist, should_force_next

MESSAGES_URL = Conf.D360_BASE_URL + 'messages/'
MEDIA_URL = Conf.D360_BASE_URL + 'media/'

HEADERS = {
    **Conf.AUTH_HEADER,
    'Content-Type': "application/json",
}

COMPONENT_NAME_PATTERN = re.compile('(?P<type>\w+)(%(?P<index>\d))?')


def get_template_message_data(to_number, template_name, components, lang_code=None):
    language_code = lang_code or os.environ.get('TEMPLATE_LANG_CODE', 'he')
    message = {
        Conf.TO_FIELD_NAME: to_number,
        "type": "template",
        "template": {
            "language": {
                "policy": "deterministic",
                "code": language_code
            },
            "name": template_name,
        }
    }
    message['template']['components'] = components

    logging.debug(f"get_template_message_data:\n{message=}")
    return message


def get_media_message_data(to_number, media_data):
    message = {
        "recipient_type": "individual",
        Conf.TO_FIELD_NAME: to_number,
        "type": media_data['media_type'],

        media_data['media_type']: media_data['payload']
    }
    logging.debug(f"get_media_message_data:\n{message=}")
    return message


def get_text_message_data(to_number, text):
    message = {
        Conf.TO_FIELD_NAME: to_number,
        "type": "text",
        "text": {
            "body": text
        }
    }
    logging.debug(f"get_text_message_data:\n{message=}")
    return message


def get_interactive_message_data(parts, to_number):
    message = {
        "recipient_type": "individual",
        Conf.TO_FIELD_NAME: to_number,
        "type": "interactive",
        "interactive": parts
    }
    logging.debug(f"get_interactive_message_data:\n{message=}")
    return message


def create_button(id_, title):
    button = {
        "type": "reply",
        "reply": {
            "id": id_,
            "title": title
        }
    }
    return button


def send_message(user, message, is_failure=False):
    if not is_failure:
        user.failure_count = 0
    else:
        user.failure_count += 1
    user.save()

    logging.debug(f"response: {MESSAGES_URL} \nresponse: {message=} {HEADERS=}")
    res = requests.post(url=MESSAGES_URL,
                        data=json.dumps(message),
                        headers=HEADERS)

    logging.debug(f"{res=}")
    logging.debug(f"{res.text=}")
    try:
        logging.debug(f"{res.json()=}")
    except Exception:
        pass
    if not 200 <= res.status_code < 300:
        logging.error(f"API error trying to send message {json.dumps(message)}")
        raise Exception(res.json())


def send_template_message(user, wab_bot_message, components=None):
    components = components or copy.deepcopy(
        wab_bot_message.message_variables)  # we can do this because this is a parsed JSON field
    if components:
        for component in components:
            for parameter in component['parameters']:
                if variable := parameter.pop('variable', None):
                    parameter[parameter['type']] = str(get_data(user, variable))

    logging.debug(f"{components=}")
    message = get_template_message_data(user.number, wab_bot_message.template_name, components)

    if Conf.DEMO_MODE:
        logging.info(f"{'*' * 20}\n*   {message=}\n{'*' * 20}")
        text = wab_bot_message.pk
        if wab_bot_message.quick_reply:
            quick_replies = get_quick_replies_as_flat_list(wab_bot_message.quick_reply)
            text = f"{text}: [{[r[1] for r in quick_replies]}]"
        message = get_text_message_data(user.number, text)

    if message:
        send_message(user, message)


def send_media_message(user, wab_bot_message, message_text=None):
    message_text = message_text or wab_bot_message.text
    if message_text and wab_bot_message.message_variables['caption']:
        variables = {k: get_data(user, v) for k, v in
                     wab_bot_message.message_variables['caption'].items()}
        message_text = message_text.format(**variables)

    payload = wab_bot_message.message_variables['media']['payload']  # TODO make dynamic
    if message_text:
        payload['caption'] = message_text

    media_data = {
        'media_type': wab_bot_message.message_variables['media']['type'],
        'payload': payload
    }

    message = get_media_message_data(user.number, media_data)

    assert message
    send_message(user, message)


def send_interactive_message(user, wab_bot_message, message_text=None):
    message_text = message_text or wab_bot_message.text

    # we can do this because this is a parsed JSON field
    parts = copy.deepcopy(wab_bot_message.message_variables) or {}
    if body := parts.get('body'):
        variables = {k: get_data(user, v) for k, v in body.pop('variables').items()}
        body['text'] = message_text.format(**variables)
    else:
        parts['body'] = {'text': message_text}

    match wab_bot_message.type:  # there are other type that not implemented yet
        case 'quick_reply':
            parts['type'] = 'button'
            buttons = get_quick_replies_as_flat_list(wab_bot_message.quick_reply)
            parts['action'] = {
                "buttons": [create_button(id, name) for id, name in buttons]
            }

    message = get_interactive_message_data(parts, user.number)

    assert message
    send_message(user, message)


def send_text_message(user, wab_bot_message, message_text=None, is_failure=False):
    message_text = message_text or wab_bot_message.text
    if wab_bot_message.message_variables:
        variables = {k: get_data(user, v) for k, v in
                     wab_bot_message.message_variables.items()}
        message_text = message_text.format(**variables)

    message = get_text_message_data(user.number, message_text)

    assert message
    send_message(user, message, is_failure)


def send_get_help_message(user):
    logging.info(f'send get_help_message to {user}')
    get_help_message = OutgoingMessage.objects.get(key='get_help')
    send_text_message(user, get_help_message, None, True)


def send_unknown_message(user):
    if user.failure_count >= 3:
        send_get_help_message(user)
        return
    unknown_message = OutgoingMessage.objects.get(key='unknown')
    send_text_message(user, unknown_message, None, True)

    user.refresh_from_db()
    if user.state != 'initial' and user.failure_count == Conf.RESEND_ON_WRONG:
        reply_message = get_next_message(user, None, user.state)
        send_next_message(user, None, None, reply_message)


def send_error_message(user, error):
    if user.failure_count >= 3:
        send_get_help_message(user)
    elif error and error.message and hasattr(error, 'params') and \
            error.params and error.params.get('custom_message', False):
        if message := OutgoingMessage.objects.filter(key=error.message).first():
            send_text_message(user, message, None, True)
        else:
            message = get_text_message_data(user.number, error.message)
            send_message(user, message, True)
    else:
        unknown_message = OutgoingMessage.objects.get(key='wrong_format')
        send_text_message(user, unknown_message, None, True)


def get_media(media_id):
    res = requests.get(
        url=MEDIA_URL + '/' + media_id,
        headers=Conf.AUTH_HEADER
    )
    logging.info(res.__dict__)
    return res


# @next_message - override the reply, for cases like concat message
def get_next_message(user, incoming_message, next_message=None):
    next_message = next_message
    if not next_message and incoming_message:
        next_message = incoming_message.reply
    if not next_message:
        logging.error("get_next_message should get either incoming_message or next_message")
    logging.info(f'candidate next message: {next_message}')
    while not should_force_next(incoming_message) and is_data_exist(user, next_message):
        if next_message.skip_if_exists:
            next_message = OutgoingMessage.objects.get(pk=next_message.skip_if_exists['next_message'])
        else:
            next_message = next_message.responses.order_by('-is_default').first().reply
        logging.debug(f'skip to next message: {next_message}')
    logging.info(f'next message: {next_message}')
    return next_message


def send_next_message(user, msg, incoming_message, reply_message):
    if not reply_message:
        logging.error('no reply_message')
        return
    if reply_message.key == 'empty':
        logging.info(f"Nothing to send")
        return

    run_actions(user, msg, reply_message)
    user.refresh_from_db()
    message_text = None
    if reply_message.text is None and reply_message.template_name is None and reply_message.type != TYPE_MEDIA:
        logging.info("About to send method message")
        if not (message_text := run_action(f"{reply_message.key}__message", user, None, reply_message, None)):
            logging.info("Got no text to send")
            return

    if reply_message.template_name:
        send_template_message(user, reply_message)
    elif reply_message.type == TYPE_MEDIA:
        send_media_message(user, reply_message, message_text)
    elif reply_message.type in [TYPE_QUICK_REPLY]:
        send_interactive_message(user, reply_message, message_text)
    else:
        send_text_message(user, reply_message, message_text)

    set_state(user, reply_message)
    user.refresh_from_db()
    logging.info(f"Sent {reply_message.key}")

    if reply_message.next_message:
        logging.info(f"About to sent next message")
        next_message = get_next_message(user, incoming_message, reply_message.next_message)
        send_next_message(user, msg, incoming_message, next_message)
