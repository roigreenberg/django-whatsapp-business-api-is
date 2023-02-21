import logging

from celery import shared_task
from django.core.exceptions import ValidationError

from whatsapp_business_api_is.messages import send_error_message, \
    send_unknown_message, get_next_message, send_next_message
from whatsapp_business_api_is.models import WaUser, OutgoingMessage
from whatsapp_business_api_is.user_msg import msg_factory
from whatsapp_business_api_is.utils import get_start_message, \
    validate_value, \
    run_actions, \
    get_quick_replies_as_flat_list


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

    if user.disable_bot:
        logging.debug(f'Bot is disabled for {user}')
        return
    if msg_type == 'text' and (incoming_message := get_start_message(msg.text)):

        logging.info(f"Start message")

        reply_message = incoming_message.reply
    elif user.state == 'initial':
        if initial_welcome_message := OutgoingMessage.objects.filter(key='initial_welcome_message').first():
            logging.info(f"Unknown message from new user")
            send_next_message(user, None, None, initial_welcome_message)
        else:
            send_unknown_message(user)
        return
    elif msg_type == 'text' and msg.text == '*':
        reply_message = get_next_message(user, None, user.state)
        ignore_validation = True
    elif (msg_type == 'button' and msg.button_payload == "wab_is_do_nothing") or \
            (msg_type == "interactive" and msg.button_reply_id == "wab_is_do_nothing"):
        return
    else:
        current_state = user.state
        logging.info(f"{current_state=}")
        logging.debug(f"{current_state.responses.all()=} {current_state.responses.exists()=}")
        if not current_state.responses.exists():
            if no_waiting_response_message := OutgoingMessage.objects.filter(key='no_waiting_response_message').first():
                logging.info(f"No waiting response")
                send_next_message(user, None, None, no_waiting_response_message)
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
            return

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
