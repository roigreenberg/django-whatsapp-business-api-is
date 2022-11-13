import logging
import re
from datetime import timedelta, time

from dateutil.parser import parse
from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from whatsapp_business_api_is.apps import WhatsappBusinessApiIsConfig
from whatsapp_business_api_is.conf import Conf
from whatsapp_business_api_is.models import TYPE_USER_START, IncomingMessage, WaUser

UUID_PATTERN = re.compile('id:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
TIME_PATTERN = re.compile('^(?P<hours>1[0-9]|2[0-3]|0?[0-9])\D?(?P<minutes>[1-5][0-9]|0?[0-9])$')
DATE_PATTERN = re.compile('^(3[01]|[12][0-9]|0?[1-9])[/.-](1[0-2]|0?[1-9])[/.-](?:20)?[0-9]{2}$')


def get_user(number):
    try:
        user = WaUser.objects.filter(number=number).first()
        logging.info(f'Got {user=}')
    except ObjectDoesNotExist:
        user = None
    return user


def get_start_message(pattern):
    start_message = IncomingMessage.objects.filter(type=TYPE_USER_START,
                                                     pattern=pattern).first()
    return start_message


def get_date(msg_text):
    if not DATE_PATTERN.match(msg_text):
        raise ValidationError('Wrong date format')
    date = parse(msg_text, dayfirst=True)
    return date.date()


def get_time(msg_text):
    m = TIME_PATTERN.match(msg_text)
    return time(int(m.group('hours')), int(m.group('minutes')))


def validate_value(user, msg, msg_obj: 'IncomingMessage'):
    msg_text = ''
    try:
        match msg_obj.type:
            case 'text':
                msg_text = msg.text
                value = msg_text
            case 'date':
                msg_text = msg.text
                value = get_date(msg_text)
            case 'time':
                msg_text = msg.text
                value = get_time(msg_text)
            case 'number':
                msg_text = msg.text
                value = float(msg_text) if '.' in msg_text else int(msg_text)
            case 'quick_reply':
                value = msg_obj.key  # validation happens before
            case 'choices':  # TODO better validation
                value = msg.text if hasattr(msg, 'text') else msg
            case _:
                value = msg
        msg.validated_value = value
    except Exception as e:
        raise ValidationError(f'{msg_text} is not in the correct format for {msg_obj.type}: {e}')

    if msg_obj.validators:
        for validator in msg_obj.validators:
            logging.info(f"run validation: {validator}")
            WhatsappBusinessApiIsConfig.VALIDATORS[validator['name']](user, msg, msg_obj, validator.get('message', ''))


def format_number(number):
    number = re.sub('\D', '', number)

    if number.startswith('0'):
        number = Conf.DEFAULT_NUMBER_PREFIX + number[1:]
    return number


def reschedule_from_shabbat(date):
    # TODO move to parameters
    # isoweekday() method to get the weekday of a given date as an integer, where Monday is 1 and Sunday is 7
    if date.isoweekday() == 5 and date.time() > time(16, 0):
        date += timedelta(days=1)
    if date.isoweekday() == 6 and date.time() < time(21, 0):
        date = date.replace(hour=21, minute=0)
    return date


def reschedule_from_midnight(date):
    # TODO move to parameters
    if time(23, 00) <= date.time():
        return date.replace(day=date.day + 1, hour=8, minute=0)
    elif date.time() < time(8, 0):
        return date.replace(hour=8, minute=0)
    else:
        return date


def parse_filter(row_filters, user):
    filters = {}
    try:
        for k, v in row_filters.items():
            if isinstance(v, str):
                row_filter = v.split('#')
                match row_filter[0]:
                    case 'current_user':
                        obj = user
                    case _:
                        obj = row_filter[0]
                for key in row_filter[1:]:
                    obj = getattr(obj, key)
                filters[k] = obj
            else:
                filters[k] = v
    except Exception as e:
        logging.error(f" Failed to parse filter: {e}")

    return filters


def _get_object(user, data):
    model = apps.get_model(*data['model'])
    filters = parse_filter(data['filter'], user)
    obj = model.objects.filter(**filters).first()
    logging.debug(f"Object found: {model=} {filters=} {obj=}")
    return obj


def run_action(action, user, msg, wab_bot_message, data):
    if action_func := WhatsappBusinessApiIsConfig.FUNCTIONS.get(action, None):
        res = action_func(user, msg, wab_bot_message, data)
        user.refresh_from_db()
        return res
    else:
        logging.info(f"Action '{action}' not found")
    return None


def run_actions(user, msg, wab_bot_message):
    if not wab_bot_message:
        return
    actions = {wab_bot_message.key: None}

    if wab_bot_message.actions:
        actions.update(wab_bot_message.actions)

    for action, data in actions.items():
        logging.info(f'About to run action: {action}')
        run_action(action, user, msg, wab_bot_message, data)


def get_data(user, data):
    obj = None
    if 'model' in data:
        obj = _get_object(user, data)
    if 'action' in data:
        obj = run_action(data.get('action'), user, None, None, data)
    res = getattr(obj, data['field'], None) if 'field' in data else obj

    logging.info(f"{res=}")

    return res


def set_data(user, data, msg):
    obj = None
    if 'model' in data:
        obj = _get_object(user, data)
    if 'action' in data:
        obj = run_action(data.get('action'), user, msg, None, data)

    if 'field' in data:
        value = data.get('value', msg.validated_value)

        logging.info(f"About to save data: {obj=} {data['field']=} {value=}")
        setattr(obj, data['field'], value)
        obj.save(update_fields=[data['field']])


def get_quick_replies_as_flat_list(quick_reply):
    return [list(reply.items())[0] for reply in quick_reply]
