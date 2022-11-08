import json
import logging

from django.db.transaction import non_atomic_requests
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from whatsapp_business_api_is.apps import WhatsappBusinessApiIsConfig


@csrf_exempt
@require_POST
@non_atomic_requests
def webhook(request):
    jsondata = request.body
    data = json.loads(jsondata)

    logging.info("Data received from Webhook is: ", data)

    if "messages" not in data:
        return HttpResponse("No messages.", content_type="text/plain")

    parser = WhatsappBusinessApiIsConfig.incoming_parser
    for message in data["messages"]:
        logging.info("message received")
        logging.debug(message)
        parser.delay(message)
        logging.info("task called")

    return HttpResponse("Message received okay.", content_type="text/plain")