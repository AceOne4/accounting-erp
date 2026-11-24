from core.permissions import capabilities_for
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

HealthSerializer = inline_serializer("Health", {"status": serializers.CharField()})

CompanyRoleSerializer = inline_serializer(
    "CompanyRole",
    {
        "id": serializers.IntegerField(),
        "name": serializers.CharField(),
        "role": serializers.CharField(),
        "capabilities": serializers.ListField(child=serializers.CharField()),
    },
    many=True,
)

MeSerializer = inline_serializer(
    "Me",
    {"username": serializers.CharField(), "companies": CompanyRoleSerializer},
)


@extend_schema(responses=HealthSerializer, auth=[])
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok"})


@extend_schema(responses=MeSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(_me_payload(request.user))


# ------------------------------------------------------------------- session auth
from django.contrib.auth import authenticate, login, logout  # noqa: E402
from django.middleware.csrf import get_token  # noqa: E402
from django.utils.decorators import method_decorator  # noqa: E402
from django.utils.translation import gettext as _  # noqa: E402
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie  # noqa: E402
from rest_framework.exceptions import AuthenticationFailed  # noqa: E402
from rest_framework.views import APIView  # noqa: E402

CsrfSerializer = inline_serializer("CsrfToken", {"csrfToken": serializers.CharField()})


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


def _me_payload(user):
    memberships = user.memberships.select_related("company")
    return {
        "username": user.get_username(),
        "companies": [
            {
                "id": m.company_id,
                "name": m.company.name,
                "role": m.role,
                "capabilities": sorted(capabilities_for(m.role)),
            }
            for m in memberships
        ],
    }


class CsrfView(APIView):
    """GET: sets the csrftoken cookie. The client sends it back as X-CSRFToken."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(responses=CsrfSerializer, auth=[])
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response({"csrfToken": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    """POST: start a session. Rate limited; wrong credentials give one generic error."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses=MeSerializer, auth=[])
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request, **serializer.validated_data)
        if user is None or not user.is_active:
            raise AuthenticationFailed(_("Wrong username or password"))
        login(request, user)
        return Response(_me_payload(user))


class LogoutView(APIView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request)
        return Response(status=204)
