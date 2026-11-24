"""User and role management for one company (capability users.manage).

A company admin can create new users, change roles, reset passwords of users that belong
to this company only, and remove memberships. Adding an existing user of another company
is not offered here (that would let one company probe another's usernames); use the
Django admin for that.
"""
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .api import CapabilityMixin
from .models import Membership

User = get_user_model()
ROLE_CHOICES = Membership.Role.choices


def _validate_password(value, user=None):
    try:
        password_validation.validate_password(value, user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages))
    return value


class MemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "username", "first_name", "role", "is_active"]
        read_only_fields = ["id"]


class MemberCreateSerializer(serializers.Serializer):
    username = serializers.RegexField(r"^[\w.@+-]+$", max_length=150)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    role = serializers.ChoiceField(choices=ROLE_CHOICES)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(_("This username is already taken"))
        return value

    def validate(self, attrs):
        _validate_password(attrs["password"], User(username=attrs["username"]))
        return attrs


class RoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=ROLE_CHOICES)


class PasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class MemberViewSet(
    CapabilityMixin, mixins.ListModelMixin, mixins.CreateModelMixin,
    mixins.DestroyModelMixin, viewsets.GenericViewSet,
):
    serializer_class = MemberSerializer
    pagination_class = None
    capability = "users.manage"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Membership.objects.none()
        return Membership.objects.filter(company=self.request.company).select_related("user").order_by("user__username")

    def _guard_self(self, membership):
        if membership.user_id == self.request.user.pk:
            raise ValidationError(_("You cannot change or remove your own access"))

    @extend_schema(request=MemberCreateSerializer, responses={201: MemberSerializer})
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        data = MemberCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        user = User.objects.create_user(
            username=v["username"], password=v["password"], first_name=v["first_name"]
        )
        membership = Membership.objects.create(user=user, company=request.company, role=v["role"])
        return Response(MemberSerializer(membership).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=RoleSerializer, responses=MemberSerializer)
    @action(detail=True, methods=["post"], url_path="role")
    def set_role(self, request, pk=None):
        membership = self.get_object()
        self._guard_self(membership)
        data = RoleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        membership.role = data.validated_data["role"]
        membership.save(update_fields=["role"])
        return Response(MemberSerializer(membership).data)

    @extend_schema(request=PasswordSerializer, responses={204: None})
    @action(detail=True, methods=["post"], url_path="password")
    def set_password(self, request, pk=None):
        membership = self.get_object()
        user = membership.user
        if user.is_superuser or Membership.objects.filter(user=user).exclude(company=request.company).exists():
            raise ValidationError(
                _("This user also has access elsewhere; their password cannot be reset here")
            )
        data = PasswordSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        _validate_password(data.validated_data["password"], user)
        user.set_password(data.validated_data["password"])
        user.save(update_fields=["password"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance):
        self._guard_self(instance)
        instance.delete()
