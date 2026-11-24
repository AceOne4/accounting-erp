from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounting.models import JournalEntry
from core.api import CapabilityMixin
from core.permissions import capabilities_for

from . import services
from .models import CashCount
from .serializers import (
    CashCountCreateSerializer,
    CashCountSerializer,
    TreasuryOverviewSerializer,
    VoucherResultSerializer,
    VoucherSerializer,
)


def _can(request, capability):
    return capability in capabilities_for(request.membership.role)


class OverviewView(CapabilityMixin, APIView):
    capability = "treasury.view"

    @extend_schema(responses=TreasuryOverviewSerializer)
    def get(self, request):
        company = request.company
        accounts = services.treasury_accounts(company)
        boxes = []
        for code in (services.EXPENSES_BOX, services.COLLECTIONS_BOX, services.BANK):
            figures = services.box_figures(company, accounts[code])
            boxes.append(
                {
                    "account": figures["account"].pk,
                    "code": code,
                    "name": figures["account"].display_name,
                    "posted": figures["posted"],
                    "pending": figures["pending"],
                    "book": figures["book"],
                }
            )
        box_ids = [accounts[services.EXPENSES_BOX].pk, accounts[services.COLLECTIONS_BOX].pk]
        recent = (
            JournalEntry.objects.filter(company=company, lines__account_id__in=box_ids)
            .distinct()
            .order_by("-date", "-id")[:15]
        )
        data = {
            "boxes": boxes,
            "recent_entries": [
                {"id": e.pk, "date": e.date, "description": e.description, "status": e.status}
                for e in recent
            ],
            "denominations": [str(d) for d in services.DENOMINATIONS],
        }
        return Response(TreasuryOverviewSerializer(data).data)


class VoucherView(CapabilityMixin, APIView):
    capability = "treasury.voucher"

    @extend_schema(request=VoucherSerializer, responses={201: VoucherResultSerializer})
    def post(self, request):
        serializer = VoucherSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["post_now"] and not _can(request, "journal.post"):
            raise PermissionDenied("You are not allowed to post entries")
        entry, posted, post_error = services.create_voucher(
            company=request.company,
            user=request.user,
            kind=data["kind"],
            date=data["date"],
            amount=data["amount"],
            partner=data.get("partner"),
            expense_account=data.get("expense_account"),
            reference=data["reference"],
            note=data["note"],
            post_now=data["post_now"],
        )
        result = {"entry_id": entry.pk, "posted": posted, "post_error": post_error}
        return Response(VoucherResultSerializer(result).data, status=status.HTTP_201_CREATED)


class CashCountViewSet(
    CapabilityMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = CashCountSerializer
    capability_by_action = {
        "list": "treasury.view",
        "retrieve": "treasury.view",
        "create": "treasury.count",
    }

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return CashCount.objects.none()
        return CashCount.objects.filter(company=self.request.company).select_related(
            "box", "counted_by"
        )

    @extend_schema(request=CashCountCreateSerializer, responses={201: CashCountSerializer})
    def create(self, request, *args, **kwargs):
        serializer = CashCountCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["adjust"] and not _can(request, "journal.create"):
            raise PermissionDenied("You are not allowed to create adjustment entries")
        count = services.record_cash_count(
            company=request.company,
            user=request.user,
            box=data["box"],
            count_date=data.get("count_date") or timezone.localdate(),
            quantities=data["quantities"],
            notes=data["notes"],
            adjust=data["adjust"],
        )
        return Response(CashCountSerializer(count).data, status=status.HTTP_201_CREATED)
