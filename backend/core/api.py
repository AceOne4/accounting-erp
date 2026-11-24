"""Shared API plumbing: company context, capability checks, error mapping."""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import ProtectedError
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ParseError, PermissionDenied
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .permissions import capabilities_for

COMPANY_HEADER = "X-Company-Id"


def resolve_membership(request):
    """The membership for the company named by X-Company-Id.

    With exactly one membership the header is optional. The user can only ever
    act in a company they belong to; anything else is a 403.
    """
    memberships = list(
        request.user.memberships.select_related("company").filter(company__is_active=True)
    )
    raw = request.headers.get(COMPANY_HEADER)
    if raw:
        if not raw.isdigit():
            raise ParseError(_("%(header)s must be a number") % {"header": COMPANY_HEADER})
        found = next((m for m in memberships if m.company_id == int(raw)), None)
        if found is None:
            raise PermissionDenied(_("You do not have access to this company"))
        return found
    if not memberships:
        raise PermissionDenied(_("You do not have access to any company"))
    if len(memberships) > 1:
        raise ParseError(_("%(header)s header is required") % {"header": COMPANY_HEADER})
    return memberships[0]


class CompanyCapability(BasePermission):
    """Resolves the company, then checks the view's required capability.

    Sets request.membership and request.company for the view to use.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        membership = resolve_membership(request)
        request.membership = membership
        request.company = membership.company
        needed = view.get_required_capability()
        return needed is not None and needed in capabilities_for(membership.role)


class CapabilityMixin:
    """Add to views. Set `capability` (APIView) or `capability_by_action` (ViewSet)."""

    permission_classes = [IsAuthenticated, CompanyCapability]
    capability: str | None = None
    capability_by_action: dict[str, str] = {}

    def get_required_capability(self):
        if self.capability:
            return self.capability
        action = getattr(self, "action", None) or self.request.method.lower()
        return self.capability_by_action.get(action)


class CompanyPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """Only accepts objects that belong to the request's company."""

    def get_queryset(self):
        queryset = super().get_queryset()
        company = getattr(self.context.get("request"), "company", None)
        if company is None:
            return queryset.none()
        return queryset.filter(company=company)


def django_to_drf(exc: DjangoValidationError) -> serializers.ValidationError:
    if hasattr(exc, "error_dict"):
        return serializers.ValidationError(
            {key: [str(m) for m in msgs] for key, msgs in exc.message_dict.items()}
        )
    return serializers.ValidationError([str(m) for m in exc.messages])


def exception_handler(exc, context):
    """Services raise Django errors; the API reports them as 400 / 409."""
    if isinstance(exc, DjangoValidationError):
        exc = django_to_drf(exc)
    elif isinstance(exc, ProtectedError):
        return Response(
            {"detail": _("This record is used elsewhere and cannot be deleted")}, status=409
        )
    return drf_exception_handler(exc, context)
