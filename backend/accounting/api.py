from decimal import Decimal

from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api import CapabilityMixin

from . import reports, services
from .models import Account, JournalEntry, Partner
from .serializers import (
    AccountSerializer,
    EntryFilterSerializer,
    GeneralLedgerParams,
    GeneralLedgerSerializer,
    JournalEntrySerializer,
    PartnerSerializer,
    PartnerStatementParams,
    PartnerStatementSerializer,
    TrialBalanceParams,
    TrialBalanceSerializer,
)

ZERO_MONEY = Value(Decimal("0"), output_field=DecimalField(max_digits=18, decimal_places=2))


class AccountViewSet(CapabilityMixin, viewsets.ModelViewSet):
    serializer_class = AccountSerializer
    pagination_class = None
    http_method_names = ["get", "post", "put", "head", "options"]
    capability_by_action = {
        "list": "account.view",
        "retrieve": "account.view",
        "create": "account.manage",
        "update": "account.manage",
    }

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # schema generation has no company
            return Account.objects.none()
        return Account.objects.filter(company=self.request.company).select_related("parent")

    def perform_create(self, serializer):
        serializer.save(company=self.request.company)


class PartnerViewSet(CapabilityMixin, viewsets.ModelViewSet):
    serializer_class = PartnerSerializer
    pagination_class = None
    http_method_names = ["get", "post", "put", "delete", "head", "options"]
    capability_by_action = {
        "list": "partner.view",
        "retrieve": "partner.view",
        "create": "partner.edit",
        "update": "partner.edit",
        "destroy": "partner.delete",
    }

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Partner.objects.none()
        return Partner.objects.filter(company=self.request.company)

    def perform_create(self, serializer):
        serializer.save(company=self.request.company)


@extend_schema_view(list=extend_schema(parameters=[EntryFilterSerializer]))
class JournalEntryViewSet(CapabilityMixin, viewsets.ModelViewSet):
    serializer_class = JournalEntrySerializer
    http_method_names = ["get", "post", "put", "delete", "head", "options"]
    capability_by_action = {
        "list": "journal.view",
        "retrieve": "journal.view",
        "create": "journal.create",
        "update": "journal.edit",
        "destroy": "journal.delete",
        "post": "journal.post",
    }

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return JournalEntry.objects.none()
        queryset = (
            JournalEntry.objects.filter(company=self.request.company)
            .select_related("created_by", "posted_by")
            .prefetch_related("lines")
            .annotate(
                total_debit=Coalesce(Sum("lines__debit"), ZERO_MONEY),
                total_credit=Coalesce(Sum("lines__credit"), ZERO_MONEY),
                missing_partner_lines=Count(
                    "lines",
                    filter=Q(lines__account__requires_partner=True, lines__partner__isnull=True),
                ),
            )
            .order_by("-date", "-id")  # aggregates drop Meta.ordering, pages need a stable order
        )
        if self.action != "list":
            return queryset

        filters = EntryFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        params = filters.validated_data
        if "status" in params:
            queryset = queryset.filter(status=params["status"])
        if "date_from" in params:
            queryset = queryset.filter(date__gte=params["date_from"])
        if "date_to" in params:
            queryset = queryset.filter(date__lte=params["date_to"])
        if params.get("incomplete"):
            queryset = queryset.filter(missing_partner_lines__gt=0)
        if params.get("q"):
            queryset = queryset.filter(description__icontains=params["q"])
        return queryset

    def _fresh(self, pk):
        return self.get_serializer(self.get_queryset().get(pk=pk)).data

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = serializer.save()
        return Response(self._fresh(entry.pk), status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        entry = self.get_object()
        serializer = self.get_serializer(entry, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(self._fresh(entry.pk))

    def perform_destroy(self, instance):
        services.delete_entry(entry=instance)

    @extend_schema(request=None, responses=JournalEntrySerializer)
    @action(detail=True, methods=["post"])
    def post(self, request, pk=None):
        entry = self.get_object()
        services.post_entry(entry=entry, user=request.user)
        return Response(self._fresh(entry.pk))


# ---------- reports ----------


def _params(serializer_class, request):
    params = serializer_class(data=request.query_params)
    params.is_valid(raise_exception=True)
    return params.validated_data


class TrialBalanceView(CapabilityMixin, APIView):
    capability = "reports.view"

    @extend_schema(parameters=[TrialBalanceParams], responses=TrialBalanceSerializer)
    def get(self, request):
        params = _params(TrialBalanceParams, request)
        data = reports.trial_balance(request.company, as_of=params.get("as_of"))
        return Response(TrialBalanceSerializer(data).data)


class GeneralLedgerView(CapabilityMixin, APIView):
    capability = "reports.view"

    @extend_schema(parameters=[GeneralLedgerParams], responses=GeneralLedgerSerializer)
    def get(self, request):
        params = _params(GeneralLedgerParams, request)
        account = None
        if "account" in params:
            account = get_object_or_404(Account, pk=params["account"], company=request.company)
        data = reports.general_ledger(
            request.company,
            account=account,
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
            status=params["status"],
        )
        return Response(GeneralLedgerSerializer(data).data)


class PartnerStatementView(CapabilityMixin, APIView):
    capability = "reports.view"

    @extend_schema(parameters=[PartnerStatementParams], responses=PartnerStatementSerializer)
    def get(self, request):
        params = _params(PartnerStatementParams, request)
        partner = get_object_or_404(Partner, pk=params["partner"], company=request.company)
        if params.get("date_from") and params.get("date_to") and params["date_from"] > params["date_to"]:
            raise ValidationError({"date_to": "The end date is before the start date"})
        data = reports.partner_statement(
            request.company,
            partner,
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
            status=params["status"],
        )
        return Response(PartnerStatementSerializer(data).data)
