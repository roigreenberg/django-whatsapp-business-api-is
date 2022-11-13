import logging

from celery import shared_task
from django.core.exceptions import ValidationError

from whatsapp_business_api_is.apps import WhatsappBusinessApiIsConfig
from whatsapp_business_api_is.messages import send_error_message, \
    send_unknown_message, \
    send_text_message, \
    send_template_message, \
    send_media_message, \
    send_interactive_message
from whatsapp_business_api_is.models import TYPE_QUICK_REPLY, TYPE_MEDIA, WaUser, OutgoingMessage
from whatsapp_business_api_is.user_msg import msg_factory
from whatsapp_business_api_is.utils import get_start_message, \
    validate_value, \
    run_actions, \
    run_action, \
    get_data, \
    get_quick_replies_as_flat_list


def set_state(user, state):
    user.state = state
    user.save(update_fields=['state'])

    WhatsappBusinessApiIsConfig.set_state(user)

    logging.info(f"Set {state=} to {user=}")


def is_data_exist(user, message):
    try:
        if message.skip_if_exists:
            logging.debug(f"use skip_if_exists")
            data = message.skip_if_exists
        else:
            if not message.responses.exists():
                return False
            data = message.responses.first().actions.get('save_data')
            if not data or data.get('do_not_skip', False):
                logging.debug(f"Do not skip - {'No save_data' if not data else 'do_not_skip'}")
                return False
        logging.info(f'{data=}')
        value = get_data(user, data)
        logging.info(f"Found {value=}")
        if value is None:
            return False
        if 'ManyRelatedManager' in str(type(value)):
            logging.debug(f"{value.exists()=}")
            return value.exists()

        if 'value' in data:
            logging.debug(f"{value} == {data['value']}")
            return value == data['value']

        return value
    except Exception as e:
        logging.debug(f"Not found {e=}")
        return False


def should_force_next(incoming_message):
    if not incoming_message:
        return False
    logging.debug(f"{incoming_message.force_next=}")
    return incoming_message.force_next


# @next_message - override the reply, for cases like concat message
def get_next_message(user, incoming_message, next_message=None):
    next_message = next_message or incoming_message.reply
    logging.info(f'candidate next message: {next_message}')
    while not should_force_next(incoming_message) and is_data_exist(user, next_message):
        if next_message.skip_if_exists:
            next_message = OutgoingMessage.objects.get(pk=next_message.skip_if_exists['next_message'])
        else:
            next_message = next_message.responses.order_by('-is_default').first().reply
        logging.debug(f'skip to next message: {next_message}')
    logging.info(f'next message: {next_message}')
    return next_message


@shared_task
def async_send_message(user_id, msg, incoming_message_id, reply_message_id):
    logging.info(f"About to send {reply_message_id} to {user_id}")
    user = WaUser.objects.filter(number=user_id).first()
    incoming_message = OutgoingMessage.objects.filter(pk=incoming_message_id).first()

    reply_message = get_next_message(user,
                                     None,
                                     next_message=OutgoingMessage.objects.get(pk=reply_message_id))

    send_next_message(user, msg, incoming_message, reply_message)


@shared_task
def parse_incoming_message(raw_msg):
    reply_message = None
    incoming_message = None
    msg = msg_factory(raw_msg)
    msg_type = msg.type
    logging.debug(f'{msg.__dict__=}')
    ignore_validation = False

    user, _ = WaUser.objects.get_or_create(number=msg.number)

    if msg_type == 'text' and (incoming_message := get_start_message(msg.text)):

        logging.info(f"Start message")

        reply_message = incoming_message.reply
    elif msg_type == 'text' and msg.text == '*':
        reply_message = get_next_message(user, None, user.state)
        ignore_validation = True
    else:
        current_state = user.state
        logging.info(f"{current_state=}")
        logging.debug(f"{current_state.responses.all()=} {current_state.responses.exists()=}")
        if user.state == 'initial' or not current_state.responses.exists():
            send_unknown_message(user)
            return

        button_key = ''
        match current_state.type:

            case 'quick_reply':
                if msg_type == 'interactive':
                    button_key = msg.button_reply_id
                else:
                    button_text = ''
                    if msg_type == 'button':
                        button_text = msg.button_text

                    elif msg_type == 'text':
                        button_text = msg.text

                    for button_key, button_pattern in get_quick_replies_as_flat_list(current_state.quick_reply):
                        if button_pattern == button_text:
                            break
                    else:
                        send_unknown_message(user)
                        return

                logging.debug(f"{button_key=}")
                incoming_message = current_state.responses.filter(key=button_key).first()
            case 'choices':
                msg_text = msg.text if hasattr(msg, 'text') else None
                incoming_message = None
                choice_key_prefix = f"{current_state.key}_resp_"
                logging.debug(f'{choice_key_prefix=}')
                if msg_text:
                    incoming_message = current_state.responses.filter(key__startswith=choice_key_prefix,
                                                                      pattern=msg_text).first()
                if not incoming_message:
                    incoming_message = current_state.responses.filter(key=f"{choice_key_prefix}_default_choice").first()
            case 'text':
                incoming_message = current_state.responses.first()
            case _:
                incoming_message = current_state.responses.first()
        logging.info(f"{incoming_message=}")
        if not incoming_message:
            logging.info(f"No message found")
            send_unknown_message(user)

    try:
        if not ignore_validation:
            validate_value(user, msg, incoming_message)
        run_actions(user, msg, incoming_message)
    except ValidationError as e:
        logging.error(f"{e.message=}")
        send_error_message(user, e)
        return

    if not reply_message:
        reply_message = get_next_message(user, incoming_message)

    send_next_message(user, msg, incoming_message, reply_message)


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
