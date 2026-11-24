"""Inventory models, all scoped to a company.

Stock is tracked in FIFO layers: every receipt line creates a layer with its cost,
issues consume the oldest layers first, and a transfer moves the consumed layers to the
destination warehouse with their original cost and order. StockMove is the item-card
ledger (signed quantity and value).
"""
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import get_language, gettext_lazy as _
from simple_history.models import HistoricalRecords

from accounting.models import JournalEntry, Partner
from core.models import Company, CompanyOwned

USER = settings.AUTH_USER_MODEL
CENT = Decimal("0.01")


def localized(obj):
    if (get_language() or "").startswith("en") and obj.name_en:
        return obj.name_en
    return obj.name


class NumberedMixin:
    """Gives a document a number such as RC-00007 once it has an id."""

    prefix = "DOC"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.number:
            self.number = "%s-%05d" % (self.prefix, self.pk)
            type(self).objects.filter(pk=self.pk).update(number=self.number)


class Unit(CompanyOwned):
    name = models.CharField(_("Name"), max_length=50)
    name_en = models.CharField(_("Name (English)"), max_length=50, blank=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["company", "name"], name="unit_unique_name")]

    @property
    def display_name(self):
        return localized(self)

    def __str__(self):
        return self.display_name


class Warehouse(CompanyOwned):
    code = models.CharField(_("Code"), max_length=20)
    name = models.CharField(_("Name"), max_length=100)
    name_en = models.CharField(_("Name (English)"), max_length=100, blank=True)
    is_active = models.BooleanField(_("Active"), default=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="warehouse_unique_code")
        ]

    @property
    def display_name(self):
        return localized(self)

    def __str__(self):
        return f"{self.code} - {self.display_name}"


class Product(CompanyOwned):
    code = models.CharField(_("Code"), max_length=50)
    name = models.CharField(_("Name"), max_length=200)
    name_en = models.CharField(_("Name (English)"), max_length=200, blank=True)
    description = models.TextField(_("Description"), blank=True)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT)
    tax_exempt = models.BooleanField(_("VAT exempt"), default=False)
    tax_rate = models.DecimalField(
        _("VAT rate %"), max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text=_("Leave blank to use the default rate"),
    )
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="product_unique_code")
        ]

    @property
    def display_name(self):
        return localized(self)

    def __str__(self):
        return f"{self.code} - {self.display_name}"


class StockReceipt(NumberedMixin, CompanyOwned):
    prefix = "RC"

    number = models.CharField(max_length=30, blank=True, editable=False)
    date = models.DateField(default=timezone.localdate)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="+")
    supplier = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name="+")
    supplier_invoice = models.CharField(max_length=100, blank=True)
    notes = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    journal_entry = models.ForeignKey(
        JournalEntry, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    history = HistoricalRecords()

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], name="receipt_unique_number")
        ]

    def total_cost(self):
        return sum((line.line_total() for line in self.lines.all()), Decimal("0"))

    def __str__(self):
        return self.number or "-"


class StockReceiptLine(models.Model):
    receipt = models.ForeignKey(StockReceipt, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+")
    quantity = models.DecimalField(
        max_digits=14, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))]
    )
    unit_cost = models.DecimalField(
        max_digits=16, decimal_places=4, validators=[MinValueValidator(Decimal("0"))]
    )

    def line_total(self):
        return (self.quantity * self.unit_cost).quantize(CENT, rounding=ROUND_HALF_UP)


class StockTransfer(NumberedMixin, CompanyOwned):
    prefix = "TR"

    number = models.CharField(max_length=30, blank=True, editable=False)
    date = models.DateField(default=timezone.localdate)
    from_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="transfers_out")
    to_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="transfers_in")
    notes = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], name="transfer_unique_number")
        ]

    def clean(self):
        if self.from_warehouse_id and self.from_warehouse_id == self.to_warehouse_id:
            raise ValidationError(_("The source and destination warehouses must be different"))

    def __str__(self):
        return self.number or "-"


class StockTransferLine(models.Model):
    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+")
    quantity = models.DecimalField(
        max_digits=14, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))]
    )


class StockLayer(CompanyOwned):
    """One FIFO layer: a quantity of a product with its final unit cost."""

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="layers")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="layers")
    unit_cost = models.DecimalField(max_digits=16, decimal_places=4)
    qty_in = models.DecimalField(max_digits=14, decimal_places=3)
    qty_remaining = models.DecimalField(max_digits=14, decimal_places=3)
    doc_date = models.DateField()
    # layers are consumed in this order; transferred layers keep the key
    fifo_key = models.BigIntegerField(default=0, db_index=True)
    receipt_line = models.ForeignKey(
        StockReceiptLine, null=True, blank=True, on_delete=models.CASCADE, related_name="layers"
    )
    transfer_line = models.ForeignKey(
        StockTransferLine, null=True, blank=True, on_delete=models.CASCADE, related_name="layers"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(qty_remaining__gte=0) & models.Q(qty_remaining__lte=models.F("qty_in")),
                name="layer_qty_within_bounds",
            )
        ]


class StockMove(CompanyOwned):
    class DocType(models.TextChoices):
        RECEIPT = "receipt", _("Goods receipt")
        TRANSFER_OUT = "transfer_out", _("Transfer out")
        TRANSFER_IN = "transfer_in", _("Transfer in")

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="moves")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="moves")
    date = models.DateField()
    doc_type = models.CharField(max_length=20, choices=DocType.choices)
    doc_id = models.PositiveIntegerField()
    doc_number = models.CharField(max_length=30, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)  # signed
    value = models.DecimalField(max_digits=16, decimal_places=2)  # signed
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "id"]


class LayerConsumption(models.Model):
    """Which layers (and at what cost) a stock-out took from."""

    move = models.ForeignKey(StockMove, on_delete=models.CASCADE, related_name="consumptions")
    layer = models.ForeignKey(StockLayer, on_delete=models.PROTECT, related_name="consumptions")
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=16, decimal_places=4)


class StockCount(NumberedMixin, CompanyOwned):
    prefix = "CNT"

    number = models.CharField(max_length=30, blank=True, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="+")
    counted_at = models.DateTimeField(default=timezone.now)
    counted_by = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="+")
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-counted_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], name="count_unique_number")
        ]


class StockCountLine(models.Model):
    count = models.ForeignKey(StockCount, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+")
    book_qty = models.DecimalField(max_digits=14, decimal_places=3)
    counted_qty = models.DecimalField(max_digits=14, decimal_places=3)
    difference = models.DecimalField(max_digits=14, decimal_places=3)


class InventoryLock(models.Model):
    """One row per company: who is currently using the inventory module."""

    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name="+")
    user = models.ForeignKey(USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    last_activity = models.DateTimeField(null=True, blank=True)
