from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api import CapabilityMixin, PageSizePagination, django_to_drf
from core.permissions import capabilities_for

from . import services
from .models import (
    InventoryLock, Product, StockCount, StockMove, StockReceipt, StockTransfer, Unit, Warehouse,
)
from .serializers import (
    CountCreateSerializer, CountSerializer, ItemCardParams, ItemCardSerializer,
    LockStatusSerializer, ProductSerializer, ReceiptSerializer, StockLevelsParams,
    StockLevelsSerializer, TransferSerializer, UnitSerializer, WarehouseSerializer,
)


class Locked(APIException):
    status_code = 423
    default_detail = "The inventory module is in use by another user"
    default_code = "inventory_locked"

    def __init__(self, holder, minutes_left):
        super().__init__(f"The inventory module is in use by {holder}")
        self.holder = holder
        self.minutes_left = minutes_left


class InventoryLockMixin:
    """Only one user per company works in the inventory module at a time (15 minutes
    idle frees it). Users with inventory.override_lock are never turned away."""

    lock_exempt = False

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)  # authentication, company, capability
        if self.lock_exempt:
            return
        holder = services.acquire_lock(request.company, request.user)
        if holder is not None and "inventory.override_lock" not in capabilities_for(
            request.membership.role
        ):
            name = holder.user.get_full_name() or holder.user.username
            raise Locked(name, services.lock_minutes_left(holder))

    def handle_exception(self, exc):
        if isinstance(exc, Locked):
            return Response(
                {"detail": str(exc.detail), "holder": exc.holder, "minutes_left": exc.minutes_left},
                status=exc.status_code,
            )
        return super().handle_exception(exc)


class InventoryViewSet(InventoryLockMixin, CapabilityMixin, viewsets.GenericViewSet):
    model = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.model.objects.none()
        return self.model.objects.filter(company=self.request.company)



class SaveInCompany:
    """List before the create mixin so the new record gets the request's company."""

    def perform_create(self, serializer):
        serializer.save(company=self.request.company)


class UnitViewSet(
    SaveInCompany, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
    mixins.UpdateModelMixin, InventoryViewSet,
):
    model = Unit
    serializer_class = UnitSerializer
    pagination_class = None
    http_method_names = ["get", "post", "put", "head", "options"]
    capability_by_action = {
        "list": "inventory.view", "retrieve": "inventory.view",
        "create": "inventory.master", "update": "inventory.master",
    }


class WarehouseViewSet(
    SaveInCompany, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
    mixins.UpdateModelMixin, InventoryViewSet,
):
    model = Warehouse
    serializer_class = WarehouseSerializer
    pagination_class = None
    http_method_names = ["get", "post", "put", "head", "options"]
    capability_by_action = {
        "list": "inventory.view", "retrieve": "inventory.view",
        "create": "inventory.master", "update": "inventory.master",
    }


class ProductViewSet(
    SaveInCompany, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
    mixins.UpdateModelMixin, mixins.DestroyModelMixin, InventoryViewSet,
):
    model = Product
    serializer_class = ProductSerializer
    pagination_class = PageSizePagination
    http_method_names = ["get", "post", "put", "delete", "head", "options"]
    capability_by_action = {
        "list": "inventory.view", "retrieve": "inventory.view",
        "create": "inventory.master", "update": "inventory.master",
        "destroy": "inventory.master_delete",
    }

    def get_queryset(self):
        queryset = super().get_queryset().select_related("unit")
        if getattr(self, "swagger_fake_view", False):
            return queryset
        term = (self.request.query_params.get("q") or "").strip()
        if term:
            queryset = queryset.filter(
                Q(code__icontains=term) | Q(name__icontains=term) | Q(name_en__icontains=term)
            )
        if self.request.query_params.get("active") == "1":
            queryset = queryset.filter(is_active=True)
        return queryset


class ReceiptViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
    mixins.UpdateModelMixin, mixins.DestroyModelMixin, InventoryViewSet,
):
    model = StockReceipt
    serializer_class = ReceiptSerializer
    http_method_names = ["get", "post", "put", "delete", "head", "options"]
    capability_by_action = {
        "list": "inventory.view", "retrieve": "inventory.view",
        "create": "inventory.receipt", "update": "inventory.receipt",
        "destroy": "inventory.receipt_delete",
    }

    def get_queryset(self):
        return super().get_queryset().select_related(
            "created_by", "journal_entry"
        ).prefetch_related("lines")

    def perform_create(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        services.delete_receipt(receipt=instance)


class TransferViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
    mixins.DestroyModelMixin, InventoryViewSet,
):
    model = StockTransfer
    serializer_class = TransferSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]
    capability_by_action = {
        "list": "inventory.view", "retrieve": "inventory.view",
        "create": "inventory.transfer", "destroy": "inventory.transfer_delete",
    }

    def get_queryset(self):
        return super().get_queryset().select_related("created_by").prefetch_related("lines")

    def perform_create(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        services.delete_transfer(transfer=instance)


class CountViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, InventoryViewSet
):
    model = StockCount
    serializer_class = CountSerializer
    capability_by_action = {
        "list": "inventory.view", "retrieve": "inventory.view", "create": "inventory.count",
    }

    def get_queryset(self):
        return super().get_queryset().select_related("counted_by").prefetch_related("lines__product")

    @extend_schema(request=CountCreateSerializer, responses={201: CountSerializer})
    def create(self, request, *args, **kwargs):
        serializer = CountCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        count = services.create_count(
            company=request.company, user=request.user, warehouse=data["warehouse"],
            quantities=[(l["product"], l["counted_qty"]) for l in data["lines"]],
            notes=data["notes"],
        )
        return Response(CountSerializer(count).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------- reports
class StockLevelsView(InventoryLockMixin, CapabilityMixin, APIView):
    capability = "inventory.view"

    @extend_schema(parameters=[StockLevelsParams], responses=StockLevelsSerializer)
    def get(self, request):
        params = StockLevelsParams(data=request.query_params)
        params.is_valid(raise_exception=True)
        warehouse = None
        if "warehouse" in params.validated_data:
            warehouse = get_object_or_404(
                Warehouse, pk=params.validated_data["warehouse"], company=request.company
            )
        report = services.stock_levels(
            request.company, warehouse=warehouse, q=params.validated_data.get("q", "").strip()
        )
        rows = [
            {
                "product": r["product"].pk, "product_code": r["product"].code,
                "product_name": r["product"].display_name, "unit": r["product"].unit.display_name,
                "warehouse": r["warehouse"].pk, "warehouse_code": r["warehouse"].code,
                "qty": r["qty"], "value": r["value"], "avg_cost": r["avg"],
            }
            for r in report["rows"]
        ]
        return Response(StockLevelsSerializer({**report, "rows": rows}).data)


class ItemCardView(InventoryLockMixin, CapabilityMixin, APIView):
    capability = "inventory.view"

    @extend_schema(parameters=[ItemCardParams], responses=ItemCardSerializer)
    def get(self, request):
        params = ItemCardParams(data=request.query_params)
        params.is_valid(raise_exception=True)
        data = params.validated_data
        product = get_object_or_404(Product, pk=data["product"], company=request.company)
        warehouse = None
        if "warehouse" in data:
            warehouse = get_object_or_404(Warehouse, pk=data["warehouse"], company=request.company)
        card = services.item_card(
            request.company, product, warehouse, data.get("date_from"), data.get("date_to")
        )
        rows = []
        for r in card["rows"]:
            move = r["move"]
            rows.append(
                {
                    "date": move.date, "doc_type": move.doc_type, "doc_id": move.doc_id,
                    "doc_number": move.doc_number, "warehouse": move.warehouse_id,
                    "qty_in": move.quantity if move.quantity > 0 else None,
                    "qty_out": -move.quantity if move.quantity < 0 else None,
                    "value": move.value, "balance_qty": r["run_q"], "balance_value": r["run_v"],
                }
            )
        return Response(
            ItemCardSerializer(
                {"opening_qty": card["opening_qty"], "opening_value": card["opening_value"], "rows": rows}
            ).data
        )


# ------------------------------------------------------------------- lock
def _lock_status(request):
    lock = services.active_lock(request.company)
    if lock is None:
        return {"locked": False, "held_by_me": False, "holder": None, "minutes_left": 0}
    return {
        "locked": True,
        "held_by_me": lock.user_id == request.user.pk,
        "holder": lock.user.get_full_name() or lock.user.username,
        "minutes_left": services.lock_minutes_left(lock),
    }


class LockView(CapabilityMixin, APIView):
    """GET: who holds the inventory lock. Does not take it."""

    capability = "inventory.view"

    @extend_schema(responses=LockStatusSerializer)
    def get(self, request):
        return Response(LockStatusSerializer(_lock_status(request)).data)


class LockReleaseView(CapabilityMixin, APIView):
    """POST: leave the inventory module and free the lock (your own lock only)."""

    capability = "inventory.view"

    @extend_schema(request=None, responses=LockStatusSerializer)
    def post(self, request):
        services.release_lock(request.company, request.user)
        return Response(LockStatusSerializer(_lock_status(request)).data)


class LockForceReleaseView(CapabilityMixin, APIView):
    """POST: free the lock whoever holds it."""

    capability = "inventory.override_lock"

    @extend_schema(request=None, responses=LockStatusSerializer)
    def post(self, request):
        services.release_lock(request.company)
        return Response(LockStatusSerializer(_lock_status(request)).data)
