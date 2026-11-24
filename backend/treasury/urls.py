from django.urls import path
from rest_framework.routers import DefaultRouter

from . import api

router = DefaultRouter(trailing_slash=True)
router.include_root_view = False
router.register("treasury/cash-counts", api.CashCountViewSet, basename="cash-count")

urlpatterns = [
    path("treasury/overview/", api.OverviewView.as_view(), name="treasury-overview"),
    path("treasury/vouchers/", api.VoucherView.as_view(), name="treasury-voucher"),
    *router.urls,
]
