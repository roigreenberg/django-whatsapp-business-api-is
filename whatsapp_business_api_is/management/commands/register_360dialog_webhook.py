import os
import urllib.parse

from django.core.management.base import BaseCommand

REGISTER_URL = 'https://waba.360dialog.io/v1/configs/webhook'


class Command(BaseCommand):
    help = 'register API KEY to 360 Dialog'

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            '--server_url',
            help='Server url',
        )

    def handle(self, *args, **options):
        import requests
        import json

        server_url = options['server_url'] or os.environ.get('SERVER_URL')
        webhook_url = urllib.parse.urljoin(server_url, "/wab-is/webhook")

        payload = json.dumps({
            "url": webhook_url
        })
        headers = {
            'D360-API-KEY': os.environ.get('D360_API_KEY'),
            'Content-Type': 'application/json'
        }

        print(f"{payload=}")
        print(f"{headers=}")

        response = requests.request("POST", REGISTER_URL, headers=headers, data=payload)

        print(response.text)
