from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Company, Membership


@admin.register(Company)
class CompanyAdmin(SimpleHistoryAdmin):
    list_display = ("name", "base_currency", "is_active")


@admin.register(Membership)
class MembershipAdmin(SimpleHistoryAdmin):
    list_display = ("user", "company", "role")
    list_filter = ("company", "role")
