from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("me/", views.me, name="me"),
    path("auth/csrf/", views.CsrfView.as_view(), name="auth-csrf"),
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/logout/", views.LogoutView.as_view(), name="auth-logout"),
]
