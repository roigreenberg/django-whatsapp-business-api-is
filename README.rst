============================================
Django Whatsapp Business Api Infrastructure
============================================

django-whatsapp-business-api-is is a Django app to help you build your Whatsapp Business bot

Detailed documentation is in the "docs" directory.

Quick start
-----------

1. Add "django-whatsapp-business-api-is" to your INSTALLED_APPS setting like this::

    INSTALLED_APPS = [
        ...
        'django-whatsapp-business-api-is',
    ]

2. Include the polls URLconf in your project urls.py like this::

    path('wab-is/', include('whatsapp_business_api_is.urls')),

3. Run ``python manage.py migrate`` to create the models.