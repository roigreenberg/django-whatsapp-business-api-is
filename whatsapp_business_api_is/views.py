import json
import logging

from django.conf import settings
from django.db.transaction import non_atomic_requests
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


@csrf_exempt
@require_POST
@non_atomic_requests
def webhook(request):
    jsondata = request.body
    data = json.loads(jsondata)

    logging.info("Data received from Webhook is: ", data)

    if "messages" not in data:
        return HttpResponse("No messages.", content_type="text/plain")

    parser = settings.INCOMING_PARSER
    for message in data["messages"]:
        logging.info("message received")
        logging.debug(message)
        parser.delay(message)
        logging.info("task called")

    return HttpResponse("Message received okay.", content_type="text/plain")