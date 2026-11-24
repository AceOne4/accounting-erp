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
    memberships = request.user.memberships.select_related("company")
    return Response(
        {
            "username": request.user.get_username(),
            "companies": [
                {"id": m.company_id, "name": m.company.name, "role": m.role} for m in memberships
            ],
        }
    )
