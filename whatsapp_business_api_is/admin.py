from django.contrib import admin

from whatsapp_business_api_is.models import WaUser

base_exclude = ['created', 'updated']


class WaUserAdmin(admin.ModelAdmin):
    exclude = base_exclude
    list_display = ['name', 'number', 'email', 'state', 'opt_in', 'created', 'updated', ]
    ordering = ['-updated']


admin.site.register(WaUser, WaUserAdmin)
