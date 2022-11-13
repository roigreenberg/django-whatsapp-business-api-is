import logging

from whatsapp_business_api_is.utils import format_number


class BaseMsg:
    def __init__(self, msg):
        self.number = msg['from']
        self.type = msg['type']
        self.raw_msg = msg
        self.validated_data = None


class TextMsg(BaseMsg):
    def __init__(self, msg):
        super().__init__(msg)
        self.text = msg['text']['body'].strip().replace(u'\xa0', u' ')  # sometimes a space represent by \xa0


class InteractiveMsg(BaseMsg):
    def __init__(self, msg):
        super().__init__(msg)
        self.button_reply_id = msg['interactive']['button_reply']['id']


class ButtonMsg(BaseMsg):
    def __init__(self, msg):
        super().__init__(msg)
        self.button_text = msg['button']['text']


class ContactsMsg(BaseMsg):
    class Contact:
        def __init__(self, number, name):
            self.number = number
            self.name = name

    def __init__(self, msg):
        super().__init__(msg)
        self.contacts = []
        for contact in msg['contacts']:
            if len(contact['phones']) == 1:
                number = contact['phones'][0]['wa_id'] or format_number(
                    contact['phones'][0]['phone'])  # TODO ignore non whatsapp numbers?
                self.contacts.append(
                    ContactsMsg.Contact(number, contact['name']['formatted_name']))


class ImagesMsg(BaseMsg):
    def __init__(self, msg):
        super().__init__(msg)
        self.image_id = msg['image']['id']


def msg_factory(msg):
    msg_classes = {
        'text': TextMsg,
        'interactive': InteractiveMsg,
        'button': ButtonMsg,
        'contacts': ContactsMsg,
        'image': ImagesMsg
    }
    msg_type = msg['type']
    msg_class = msg_classes.get(msg_type, BaseMsg)
    logging.info(f"Got message with {msg_type=} -> {msg_class=}")

    return msg_class(msg)
