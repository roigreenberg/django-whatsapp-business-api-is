#!/usr/bin/env python
# makemigrations.py

from django.core.management import call_command

from boot_django import boot_django

boot_django()
call_command("makemigrations")
