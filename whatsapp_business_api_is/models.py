from django.db import models
from django.db.models.signals import post_save

from whatsapp_business_api_is.conf import Conf

# Create your models here.
TYPE_USER_START = 'user_start'
TYPE_QUICK_REPLY = 'quick_reply'
TYPE_CALL_TO_ACTION = 'call_to_action'
TYPE_TEXT = 'text'
TYPE_MEDIA = 'media'
TYPE_NUMBER = 'number'
TYPE_CHOICES = 'choices'
TYPE_GENERIC = 'generic'
MESSAGE_TYPES = [
    (TYPE_USER_START, TYPE_USER_START),
    (TYPE_QUICK_REPLY, TYPE_QUICK_REPLY),
    (TYPE_CALL_TO_ACTION, TYPE_CALL_TO_ACTION),
    (TYPE_TEXT, TYPE_TEXT),
    (TYPE_MEDIA, TYPE_MEDIA),
    (TYPE_NUMBER, TYPE_NUMBER),
    (TYPE_CHOICES, TYPE_CHOICES),
    (TYPE_GENERIC, TYPE_GENERIC)
]


class OutgoingMessage(models.Model):
    DEFAULT_STATE = 'initial'

    key = models.CharField(primary_key=True, max_length=100)
    type = models.TextField(choices=MESSAGE_TYPES, default=TYPE_TEXT)
    template_name = models.TextField(default=None, null=True)
    message_variables = models.JSONField(default=None, null=True)
    quick_reply = models.JSONField(default=None, null=True)
    choices = models.JSONField(default=None, null=True)
    text = models.CharField(null=True, db_index=True, max_length=500)
    variable = models.CharField(null=True, max_length=250)
    actions = models.JSONField(default=None, null=True)
    next_message = models.ForeignKey('self', default=None, null=True, on_delete=models.CASCADE)
    skip_if_exists = models.JSONField(default=None, null=True)

    def __unicode__(self):
        return u'{0}'.format(self.key)


class IncomingMessage(models.Model):
    key = models.CharField(primary_key=True, max_length=100)
    type = models.TextField(choices=MESSAGE_TYPES, default=TYPE_USER_START)
    pattern = models.CharField(null=True, db_index=True, max_length=250)
    actions = models.JSONField(default=None, null=True)
    message = models.ForeignKey(OutgoingMessage, null=True, on_delete=models.CASCADE, related_name='responses')
    reply = models.ForeignKey(OutgoingMessage, null=True, on_delete=models.CASCADE)
    force_next = models.BooleanField(default=False)
    is_default = models.BooleanField(
        default=False)  # relevant only for message with multiple responses and skip_if_exists.
    validators = models.JSONField(default=None, null=True)

    def __unicode__(self):
        return u'{0}'.format(self.key)


class WaUser(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    name = models.TextField(blank=True)
    number = models.CharField(primary_key=True, max_length=13)
    email = models.EmailField(null=True)
    state = models.ForeignKey(OutgoingMessage, on_delete=models.CASCADE, default=OutgoingMessage.DEFAULT_STATE)
    opt_in = models.BooleanField(default=False)

    def __unicode__(self):
        return u'{}'.format(self.number)


def outgoing_message_post_save(sender, instance, *args, **kwargs):
    message = instance
    if message.template_name and '%%env%%' in message.template_name:
        message.template_name = message.template_name.replace('%%env%%', Conf.ENV)
        message.save()
        return

    if message.type == TYPE_CHOICES and message.choices:
        for choice, reply_data in message.choices.items():
            reply_key = reply_data.pop('reply_key')
            if 'pattern' not in reply_data:
                reply_data['pattern'] = choice
            IncomingMessage.objects.update_or_create(
                key=f"{message.key}_resp_{choice}",
                defaults={
                    **reply_data,
                    'type': TYPE_CHOICES,
                    'message': message,
                    'reply': OutgoingMessage.objects.get_or_create(key=reply_key)[0]
                }
            )


post_save.connect(outgoing_message_post_save, sender=OutgoingMessage)

