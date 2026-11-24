from django.urls import path
from rest_framework.routers import DefaultRouter

from . import users_api, views

router = DefaultRouter(trailing_slash=True)
router.include_root_view = False
router.register("users", users_api.MemberViewSet, basename="member")

urlpatterns = [
    path("health/", views.health, name="health"),
    path("me/", views.me, name="me"),
    path("auth/csrf/", views.CsrfView.as_view(), name="auth-csrf"),
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/token/", views.TokenView.as_view(), name="auth-token"),
    path("auth/token/revoke/", views.TokenRevokeView.as_view(), name="auth-token-revoke"),
    path("auth/password/", views.PasswordChangeView.as_view(), name="auth-password"),
    path("auth/logout/", views.LogoutView.as_view(), name="auth-logout"),
    *router.urls,
]
