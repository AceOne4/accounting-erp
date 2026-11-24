"""Accounting models, all scoped to a company.

Posted journal entries are immutable: the model refuses to save or delete a posted
entry or any of its lines. Every change goes through accounting.services.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import get_language, gettext_lazy as _
from simple_history.models import HistoricalRecords

from core.models import CompanyOwned


class Account(CompanyOwned):
    class Type(models.TextChoices):
        ASSET = "asset", _("Assets")
        LIABILITY = "liability", _("Liabilities")
        EQUITY = "equity", _("Equity")
        REVENUE = "revenue", _("Revenue")
        EXPENSE = "expense", _("Expenses")

    code = models.CharField(_("Code"), max_length=20)
    name = models.CharField(_("Account name"), max_length=200)
    name_en = models.CharField(_("Account name (English)"), max_length=200, blank=True)
    type = models.CharField(_("Type"), max_length=20, choices=Type.choices)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
        verbose_name=_("Parent account"),
    )
    is_leaf = models.BooleanField(_("Leaf account (accepts entries)"), default=True)
    requires_partner = models.BooleanField(
        _("Requires customer/supplier"),
        default=False,
        help_text=_("Enable for receivable and payable accounts"),
    )
    history = HistoricalRecords()

    class Meta:
        ordering = ["code"]
        verbose_name = _("Account")
        verbose_name_plural = _("Chart of accounts")
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="account_code_unique_per_company")
        ]

    @property
    def display_name(self):
        """English name when English is active, otherwise the main name."""
        if (get_language() or "").startswith("en") and self.name_en:
            return self.name_en
        return self.name

    def clean(self):
        if self.parent_id:
            if self.parent_id == self.pk:
                raise ValidationError(_("An account cannot be its own parent"))
            if self.parent.company_id != self.company_id:
                raise ValidationError(_("The parent account belongs to another company"))
            if self.parent.is_leaf:
                raise ValidationError(_("The parent must be a non-leaf account"))

    def __str__(self):
        return f"{self.code} - {self.display_name}"


class Partner(CompanyOwned):
    class Kind(models.TextChoices):
        CUSTOMER = "customer", _("Customer")
        SUPPLIER = "supplier", _("Supplier")
        BOTH = "both", _("Customer and supplier")

    name = models.CharField(_("Name"), max_length=200)
    kind = models.CharField(_("Type"), max_length=10, choices=Kind.choices)
    tax_id = models.CharField(_("Tax ID"), max_length=30, blank=True)
    phone = models.CharField(_("Phone"), max_length=30, blank=True)
    is_active = models.BooleanField(_("Active"), default=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["name"]
        verbose_name = _("Customer / Supplier")
        verbose_name_plural = _("Customers and suppliers")

    def __str__(self):
        return f"{self.name} ({self.get_kind_display()})"


class JournalEntry(CompanyOwned):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        POSTED = "posted", _("Posted")

    date = models.DateField(_("Date"))
    description = models.CharField(_("Description"), max_length=500)
    status = models.CharField(
        _("Status"), max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("Created by"),
    )
    is_ai_generated = models.BooleanField(_("AI generated"), default=False)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    posted_at = models.DateTimeField(_("Posted at"), null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("Posted by"),
    )
    history = HistoricalRecords()

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = _("Journal entry")
        verbose_name_plural = _("Journal entries")
        indexes = [
            models.Index(fields=["company", "date"]),
            models.Index(fields=["company", "status"]),
        ]

    def _stored_status(self):
        if not self.pk:
            return None
        return type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()

    def save(self, *args, **kwargs):
        # draft -> posted is allowed (the stored row is still a draft); anything
        # on an already posted entry is not.
        if self._stored_status() == self.Status.POSTED:
            raise ValidationError(_("Posted entries cannot be changed"))
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self._stored_status() == self.Status.POSTED:
            raise ValidationError(_("Posted entries cannot be deleted"))
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.date} - {self.description}"


class JournalLine(models.Model):
    entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name=_("Entry"),
    )
    account = models.ForeignKey(Account, on_delete=models.PROTECT, verbose_name=_("Account"))
    partner = models.ForeignKey(
        Partner,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        verbose_name=_("Customer / Supplier"),
    )
    debit = models.DecimalField(_("Debit"), max_digits=16, decimal_places=2, default=0)
    credit = models.DecimalField(_("Credit"), max_digits=16, decimal_places=2, default=0)
    memo = models.CharField(_("Notes"), max_length=300, blank=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["id"]
        verbose_name = _("Journal line")
        verbose_name_plural = _("Journal lines")
        constraints = [
            models.CheckConstraint(
                condition=Q(debit__gte=0) & Q(credit__gte=0), name="line_amounts_not_negative"
            ),
            models.CheckConstraint(
                condition=Q(debit=0) | Q(credit=0), name="line_debit_or_credit_not_both"
            ),
            models.CheckConstraint(
                condition=Q(debit__gt=0) | Q(credit__gt=0), name="line_has_a_value"
            ),
        ]

    def _entry_is_posted(self):
        return JournalEntry.objects.filter(
            pk=self.entry_id, status=JournalEntry.Status.POSTED
        ).exists()

    def save(self, *args, **kwargs):
        if self._entry_is_posted():
            raise ValidationError(_("Lines of a posted entry cannot be changed"))
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self._entry_is_posted():
            raise ValidationError(_("Lines of a posted entry cannot be deleted"))
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.account.code} | {self.debit} | {self.credit}"
