from django.urls import path
from rest_framework.routers import DefaultRouter

from . import api

router = DefaultRouter(trailing_slash=True)
router.include_root_view = False
router.register("accounts", api.AccountViewSet, basename="account")
router.register("partners", api.PartnerViewSet, basename="partner")
router.register("journal-entries", api.JournalEntryViewSet, basename="journal-entry")

urlpatterns = [
    path("reports/trial-balance/", api.TrialBalanceView.as_view(), name="report-trial-balance"),
    path("reports/general-ledger/", api.GeneralLedgerView.as_view(), name="report-general-ledger"),
    path("reports/partner-statement/", api.PartnerStatementView.as_view(), name="report-partner-statement"),
    *router.urls,
]
