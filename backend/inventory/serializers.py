from decimal import Decimal

from django.utils.translation import gettext as _
from rest_framework import serializers

from accounting.models import Partner
from core.api import CompanyPrimaryKeyRelatedField, django_to_drf
from django.core.exceptions import ValidationError as DjangoValidationError

from . import services
from .models import (
    Product, StockCount, StockCountLine, StockMove, StockReceipt, StockReceiptLine,
    StockTransfer, StockTransferLine, Unit, Warehouse,
)

MONEY = {"max_digits": 18, "decimal_places": 2}
QTY = {"max_digits": 14, "decimal_places": 3}
COST = {"max_digits": 16, "decimal_places": 4}


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ["id", "name", "name_en"]

    def validate_name(self, value):
        clash = Unit.objects.filter(company=self.context["request"].company, name=value)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(_("A unit with this name already exists"))
        return value


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ["id", "code", "name", "name_en", "is_active"]

    def validate_code(self, value):
        clash = Warehouse.objects.filter(company=self.context["request"].company, code=value)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(_("A warehouse with this code already exists"))
        return value


class ProductSerializer(serializers.ModelSerializer):
    unit = CompanyPrimaryKeyRelatedField(queryset=Unit.objects.all())

    class Meta:
        model = Product
        fields = [
            "id", "code", "name", "name_en", "description", "unit", "tax_exempt",
            "tax_rate", "is_active",
        ]

    def validate(self, attrs):
        company = self.context["request"].company
        code = attrs.get("code", getattr(self.instance, "code", None))
        clash = Product.objects.filter(company=company, code=code)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
            # the code and unit cannot change once the product has movements
            if StockMove.objects.filter(product=self.instance).exists():
                for field in ("code", "unit"):
                    if field in attrs and attrs[field] != getattr(self.instance, field):
                        raise serializers.ValidationError(
                            {field: _("Cannot be changed once the product has stock movements")}
                        )
        if clash.exists():
            raise serializers.ValidationError({"code": _("A product with this code already exists")})
        return attrs


# --------------------------------------------------------------- receipts
class ReceiptLineSerializer(serializers.ModelSerializer):
    product = CompanyPrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.DecimalField(**QTY)
    unit_cost = serializers.DecimalField(**COST)
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = StockReceiptLine
        fields = ["id", "product", "quantity", "unit_cost", "line_total"]

    def get_line_total(self, obj) -> str:
        return str(obj.line_total())


class ReceiptSerializer(serializers.ModelSerializer):
    warehouse = CompanyPrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    supplier = CompanyPrimaryKeyRelatedField(queryset=Partner.objects.all())
    lines = ReceiptLineSerializer(many=True)
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    journal_entry = serializers.PrimaryKeyRelatedField(read_only=True)
    journal_entry_status = serializers.CharField(source="journal_entry.status", read_only=True, default=None)
    total_cost = serializers.SerializerMethodField()
    locked_reason = serializers.SerializerMethodField()

    class Meta:
        model = StockReceipt
        fields = [
            "id", "number", "date", "warehouse", "supplier", "supplier_invoice", "notes",
            "lines", "total_cost", "journal_entry", "journal_entry_status", "locked_reason",
            "created_by", "created_at",
        ]
        read_only_fields = ["number", "created_at"]

    def get_total_cost(self, obj) -> str:
        return str(obj.total_cost())

    def get_locked_reason(self, obj) -> str:
        return str(services.receipt_lock_reason(obj))

    @staticmethod
    def _inputs(lines):
        return [
            services.ReceiptLineInput(l["product"], l["quantity"], l["unit_cost"]) for l in lines
        ]

    def create(self, validated):
        request = self.context["request"]
        try:
            return services.create_receipt(
                company=request.company, user=request.user, date=validated["date"],
                warehouse=validated["warehouse"], supplier=validated["supplier"],
                lines=self._inputs(validated["lines"]),
                supplier_invoice=validated.get("supplier_invoice", ""),
                notes=validated.get("notes", ""),
            )
        except DjangoValidationError as error:
            raise django_to_drf(error)

    def update(self, instance, validated):
        try:
            return services.update_receipt(
                receipt=instance, date=validated["date"], warehouse=validated["warehouse"],
                supplier=validated["supplier"], lines=self._inputs(validated["lines"]),
                supplier_invoice=validated.get("supplier_invoice", ""),
                notes=validated.get("notes", ""),
            )
        except DjangoValidationError as error:
            raise django_to_drf(error)


# -------------------------------------------------------------- transfers
class TransferLineSerializer(serializers.ModelSerializer):
    product = CompanyPrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.DecimalField(**QTY)

    class Meta:
        model = StockTransferLine
        fields = ["id", "product", "quantity"]


class TransferSerializer(serializers.ModelSerializer):
    from_warehouse = CompanyPrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    to_warehouse = CompanyPrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    lines = TransferLineSerializer(many=True)
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    locked_reason = serializers.SerializerMethodField()

    class Meta:
        model = StockTransfer
        fields = [
            "id", "number", "date", "from_warehouse", "to_warehouse", "notes", "lines",
            "locked_reason", "created_by", "created_at",
        ]
        read_only_fields = ["number", "created_at"]

    def get_locked_reason(self, obj) -> str:
        return str(services.transfer_lock_reason(obj))

    def create(self, validated):
        request = self.context["request"]
        try:
            return services.create_transfer(
                company=request.company, user=request.user, date=validated["date"],
                from_warehouse=validated["from_warehouse"], to_warehouse=validated["to_warehouse"],
                lines=[services.TransferLineInput(l["product"], l["quantity"]) for l in validated["lines"]],
                notes=validated.get("notes", ""),
            )
        except DjangoValidationError as error:
            raise django_to_drf(error)


# ----------------------------------------------------------------- counts
class CountLineSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)

    class Meta:
        model = StockCountLine
        fields = ["id", "product", "product_code", "book_qty", "counted_qty", "difference"]


class CountSerializer(serializers.ModelSerializer):
    lines = CountLineSerializer(many=True, read_only=True)
    counted_by = serializers.CharField(source="counted_by.username", read_only=True)

    class Meta:
        model = StockCount
        fields = ["id", "number", "warehouse", "counted_at", "counted_by", "notes", "lines"]
        read_only_fields = fields


class CountInputLineSerializer(serializers.Serializer):
    product = CompanyPrimaryKeyRelatedField(queryset=Product.objects.all())
    counted_qty = serializers.DecimalField(min_value=Decimal("0"), **QTY)


class CountCreateSerializer(serializers.Serializer):
    warehouse = CompanyPrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    notes = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    lines = CountInputLineSerializer(many=True)


# ---------------------------------------------------------------- reports
class StockLevelRowSerializer(serializers.Serializer):
    product = serializers.IntegerField()
    product_code = serializers.CharField()
    product_name = serializers.CharField()
    unit = serializers.CharField()
    warehouse = serializers.IntegerField()
    warehouse_code = serializers.CharField()
    qty = serializers.DecimalField(**QTY)
    value = serializers.DecimalField(**MONEY)
    avg_cost = serializers.DecimalField(**COST)


class LedgerComparisonSerializer(serializers.Serializer):
    posted = serializers.DecimalField(**MONEY)
    all = serializers.DecimalField(**MONEY)
    difference = serializers.DecimalField(**MONEY)


class StockLevelsSerializer(serializers.Serializer):
    rows = StockLevelRowSerializer(many=True)
    total_value = serializers.DecimalField(**MONEY)
    stock_total = serializers.DecimalField(**MONEY)
    ledger = LedgerComparisonSerializer(allow_null=True)


class StockLevelsParams(serializers.Serializer):
    warehouse = serializers.IntegerField(required=False)
    q = serializers.CharField(required=False, allow_blank=True)


class ItemCardParams(serializers.Serializer):
    product = serializers.IntegerField()
    warehouse = serializers.IntegerField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)


class ItemCardRowSerializer(serializers.Serializer):
    date = serializers.DateField()
    doc_type = serializers.CharField()
    doc_id = serializers.IntegerField()
    doc_number = serializers.CharField()
    warehouse = serializers.IntegerField()
    qty_in = serializers.DecimalField(allow_null=True, **QTY)
    qty_out = serializers.DecimalField(allow_null=True, **QTY)
    value = serializers.DecimalField(**MONEY)
    balance_qty = serializers.DecimalField(**QTY)
    balance_value = serializers.DecimalField(**MONEY)


class ItemCardSerializer(serializers.Serializer):
    opening_qty = serializers.DecimalField(**QTY)
    opening_value = serializers.DecimalField(**MONEY)
    rows = ItemCardRowSerializer(many=True)


class LockStatusSerializer(serializers.Serializer):
    locked = serializers.BooleanField()
    held_by_me = serializers.BooleanField()
    holder = serializers.CharField(allow_null=True)
    minutes_left = serializers.IntegerField()
