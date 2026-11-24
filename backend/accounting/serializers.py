from decimal import Decimal

from rest_framework import serializers

from core.api import CompanyPrimaryKeyRelatedField, django_to_drf
from django.core.exceptions import ValidationError as DjangoValidationError

from . import services
from .models import Account, JournalEntry, JournalLine, Partner

MONEY = {"max_digits": 18, "decimal_places": 2}


class AccountSerializer(serializers.ModelSerializer):
    parent = CompanyPrimaryKeyRelatedField(
        queryset=Account.objects.all(), allow_null=True, required=False
    )

    class Meta:
        model = Account
        fields = ["id", "code", "name", "name_en", "type", "parent", "is_leaf", "requires_partner"]

    def validate(self, attrs):
        company = self.context["request"].company
        code = attrs.get("code", getattr(self.instance, "code", None))
        clash = Account.objects.filter(company=company, code=code)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError({"code": "An account with this code already exists"})

        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        if parent is not None:
            if parent.is_leaf:
                raise serializers.ValidationError({"parent": "The parent must be a non-leaf account"})
            if self.instance and parent.pk == self.instance.pk:
                raise serializers.ValidationError({"parent": "An account cannot be its own parent"})

        if self.instance:
            is_leaf = attrs.get("is_leaf", self.instance.is_leaf)
            if is_leaf and self.instance.children.exists():
                raise serializers.ValidationError(
                    {"is_leaf": "An account with sub-accounts cannot accept entries"}
                )
            if not is_leaf and self.instance.journalline_set.exists():
                raise serializers.ValidationError(
                    {"is_leaf": "An account that already has entries must stay a leaf"}
                )
        return attrs


class PartnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partner
        fields = ["id", "name", "kind", "tax_id", "phone", "is_active"]


class JournalLineSerializer(serializers.ModelSerializer):
    account = CompanyPrimaryKeyRelatedField(queryset=Account.objects.all())
    partner = CompanyPrimaryKeyRelatedField(
        queryset=Partner.objects.all(), allow_null=True, required=False
    )
    debit = serializers.DecimalField(**MONEY, required=False, default=Decimal("0"))
    credit = serializers.DecimalField(**MONEY, required=False, default=Decimal("0"))

    class Meta:
        model = JournalLine
        fields = ["id", "account", "partner", "debit", "credit", "memo"]
        read_only_fields = ["id"]


class JournalEntrySerializer(serializers.ModelSerializer):
    lines = JournalLineSerializer(many=True, allow_empty=False)
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    posted_by = serializers.CharField(source="posted_by.username", read_only=True, default=None)
    total_debit = serializers.DecimalField(**MONEY, read_only=True)
    total_credit = serializers.DecimalField(**MONEY, read_only=True)
    missing_partner_lines = serializers.IntegerField(read_only=True)

    class Meta:
        model = JournalEntry
        fields = [
            "id",
            "date",
            "description",
            "status",
            "is_ai_generated",
            "created_by",
            "created_at",
            "posted_by",
            "posted_at",
            "total_debit",
            "total_credit",
            "missing_partner_lines",
            "lines",
        ]
        read_only_fields = ["status", "is_ai_generated", "created_at", "posted_at"]

    @staticmethod
    def _line_inputs(lines):
        return [
            services.LineInput(
                account=line["account"],
                debit=line["debit"],
                credit=line["credit"],
                partner=line.get("partner"),
                memo=line.get("memo", ""),
            )
            for line in lines
        ]

    def create(self, validated_data):
        request = self.context["request"]
        try:
            return services.create_entry(
                company=request.company,
                user=request.user,
                date=validated_data["date"],
                description=validated_data["description"],
                lines=self._line_inputs(validated_data["lines"]),
            )
        except DjangoValidationError as exc:
            raise django_to_drf(exc)

    def update(self, instance, validated_data):
        try:
            return services.update_entry(
                entry=instance,
                date=validated_data["date"],
                description=validated_data["description"],
                lines=self._line_inputs(validated_data["lines"]),
            )
        except DjangoValidationError as exc:
            raise django_to_drf(exc)


# ---------- query parameters and report responses (documented in the OpenAPI schema) ----------


class EntryFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["draft", "posted"], required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    incomplete = serializers.BooleanField(required=False)
    q = serializers.CharField(required=False)


class TrialBalanceParams(serializers.Serializer):
    as_of = serializers.DateField(required=False)


class GeneralLedgerParams(serializers.Serializer):
    account = serializers.IntegerField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    status = serializers.ChoiceField(choices=["posted", "all", "draft"], default="posted")


class PartnerStatementParams(serializers.Serializer):
    partner = serializers.IntegerField()
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    status = serializers.ChoiceField(choices=["all", "posted", "draft"], default="all")


class BalanceSerializer(serializers.Serializer):
    amount = serializers.DecimalField(**MONEY)
    side = serializers.ChoiceField(choices=["debit", "credit", ""], allow_blank=True)


class AccountBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()
    name_en = serializers.CharField(allow_blank=True)


class PartnerBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class TrialBalanceRowSerializer(serializers.Serializer):
    account_id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()
    name_en = serializers.CharField(allow_blank=True)
    debit = serializers.DecimalField(**MONEY)
    credit = serializers.DecimalField(**MONEY)
    balance_debit = serializers.DecimalField(**MONEY)
    balance_credit = serializers.DecimalField(**MONEY)


class TrialBalanceSerializer(serializers.Serializer):
    rows = TrialBalanceRowSerializer(many=True)
    total_debit = serializers.DecimalField(**MONEY)
    total_credit = serializers.DecimalField(**MONEY)
    total_balance_debit = serializers.DecimalField(**MONEY)
    total_balance_credit = serializers.DecimalField(**MONEY)
    is_balanced = serializers.BooleanField()


class LedgerRowSerializer(serializers.Serializer):
    date = serializers.DateField()
    entry_id = serializers.IntegerField()
    status = serializers.CharField()
    description = serializers.CharField()
    memo = serializers.CharField(allow_blank=True)
    partner = PartnerBriefSerializer(allow_null=True)
    sub_account = AccountBriefSerializer(allow_null=True)
    debit = serializers.DecimalField(**MONEY)
    credit = serializers.DecimalField(**MONEY)
    balance = BalanceSerializer()


class LedgerSerializer(serializers.Serializer):
    account = AccountBriefSerializer()
    is_parent = serializers.BooleanField()
    opening = BalanceSerializer()
    rows = LedgerRowSerializer(many=True)
    total_debit = serializers.DecimalField(**MONEY)
    total_credit = serializers.DecimalField(**MONEY)
    closing = BalanceSerializer()


class GeneralLedgerSerializer(serializers.Serializer):
    ledgers = LedgerSerializer(many=True)


class StatementRowSerializer(serializers.Serializer):
    date = serializers.DateField()
    entry_id = serializers.IntegerField()
    status = serializers.CharField()
    description = serializers.CharField()
    account = AccountBriefSerializer()
    memo = serializers.CharField(allow_blank=True)
    debit = serializers.DecimalField(**MONEY)
    credit = serializers.DecimalField(**MONEY)
    balance_posted = BalanceSerializer()
    balance_all = BalanceSerializer()


class StatementPartnerSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    kind = serializers.CharField()


class PartnerStatementSerializer(serializers.Serializer):
    partner = StatementPartnerSerializer()
    rows = StatementRowSerializer(many=True)
    opening_posted = BalanceSerializer()
    opening_all = BalanceSerializer()
    posted_debit = serializers.DecimalField(**MONEY)
    posted_credit = serializers.DecimalField(**MONEY)
    draft_debit = serializers.DecimalField(**MONEY)
    draft_credit = serializers.DecimalField(**MONEY)
    closing_posted = BalanceSerializer()
    closing_all = BalanceSerializer()
    draft_net = BalanceSerializer()
    has_draft = serializers.BooleanField()
    incomplete_entries = serializers.IntegerField()
