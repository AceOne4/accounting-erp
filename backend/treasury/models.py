"""Cash counts. Vouchers need no table of their own: they are journal entries."""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from accounting.models import Account, JournalEntry
from core.models import CompanyOwned


class CashCount(CompanyOwned):
    box = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="+")
    count_date = models.DateField(_("Count date"))
    counted_total = models.DecimalField(_("Counted cash"), max_digits=16, decimal_places=2)
    book_balance = models.DecimalField(_("Book balance"), max_digits=16, decimal_places=2)
    difference = models.DecimalField(_("Difference"), max_digits=16, decimal_places=2)
    breakdown = models.JSONField(_("Breakdown"), default=dict, blank=True)
    notes = models.CharField(_("Notes"), max_length=300, blank=True)
    counted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    entry = models.ForeignKey(
        JournalEntry, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = _("Cash count")
        verbose_name_plural = _("Cash counts")
