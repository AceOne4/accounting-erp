from django.urls import path
from rest_framework.routers import DefaultRouter

from . import api

router = DefaultRouter(trailing_slash=True)
router.include_root_view = False
router.register("inventory/units", api.UnitViewSet, basename="unit")
router.register("inventory/warehouses", api.WarehouseViewSet, basename="warehouse")
router.register("inventory/products", api.ProductViewSet, basename="product")
router.register("inventory/receipts", api.ReceiptViewSet, basename="receipt")
router.register("inventory/transfers", api.TransferViewSet, basename="transfer")
router.register("inventory/counts", api.CountViewSet, basename="stock-count")

urlpatterns = [
    path("inventory/reports/stock-levels/", api.StockLevelsView.as_view(), name="stock-levels"),
    path("inventory/reports/item-card/", api.ItemCardView.as_view(), name="item-card"),
    path("inventory/lock/", api.LockView.as_view(), name="inventory-lock"),
    path("inventory/lock/release/", api.LockReleaseView.as_view(), name="inventory-lock-release"),
    path("inventory/lock/force-release/", api.LockForceReleaseView.as_view(), name="inventory-lock-force"),
    *router.urls,
]
