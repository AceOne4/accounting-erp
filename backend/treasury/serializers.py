from rest_framework import serializers

from accounting.models import Account, Partner
from core.api import CompanyPrimaryKeyRelatedField

from . import services
from .models import CashCount

MONEY = {"max_digits": 18, "decimal_places": 2}


class VoucherSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=list(services.KINDS))
    date = serializers.DateField()
    amount = serializers.DecimalField(**MONEY)
    partner = CompanyPrimaryKeyRelatedField(
        queryset=Partner.objects.filter(is_active=True), required=False, allow_null=True
    )
    expense_account = CompanyPrimaryKeyRelatedField(
        queryset=Account.objects.filter(type=Account.Type.EXPENSE, is_leaf=True),
        required=False, allow_null=True,
    )
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    post_now = serializers.BooleanField(required=False, default=False)


class VoucherResultSerializer(serializers.Serializer):
    entry_id = serializers.IntegerField()
    posted = serializers.BooleanField()
    post_error = serializers.CharField(allow_blank=True)


class BoxFiguresSerializer(serializers.Serializer):
    account = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()
    posted = serializers.DecimalField(**MONEY)
    pending = serializers.DecimalField(**MONEY)
    book = serializers.DecimalField(**MONEY)


class RecentEntrySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    date = serializers.DateField()
    description = serializers.CharField()
    status = serializers.CharField()


class TreasuryOverviewSerializer(serializers.Serializer):
    boxes = BoxFiguresSerializer(many=True)
    recent_entries = RecentEntrySerializer(many=True)
    denominations = serializers.ListField(child=serializers.CharField())


class CashCountSerializer(serializers.ModelSerializer):
    box = serializers.PrimaryKeyRelatedField(read_only=True)
    box_code = serializers.CharField(source="box.code", read_only=True)
    counted_by = serializers.CharField(source="counted_by.username", read_only=True)
    entry = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = CashCount
        fields = [
            "id", "box", "box_code", "count_date", "counted_total", "book_balance",
            "difference", "breakdown", "notes", "counted_by", "entry", "created_at",
        ]
        read_only_fields = fields


class CashCountCreateSerializer(serializers.Serializer):
    box = CompanyPrimaryKeyRelatedField(queryset=Account.objects.all())
    count_date = serializers.DateField(required=False)
    quantities = serializers.DictField(
        child=serializers.IntegerField(min_value=0),
        help_text="Quantity per denomination, e.g. {'200': 3, '0.5': 4}",
    )
    notes = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    adjust = serializers.BooleanField(required=False, default=False)
