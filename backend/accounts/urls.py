from django.urls import path

from .views import (
    ExpertApplicationView,
    TwoFactorLoginView,
    TwoFactorView,
    LoginView,
    LogoutView,
    MeView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RefreshView,
    RegisterView,
)


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshView.as_view(), name="refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("password/change/", PasswordChangeView.as_view(), name="password-change"),
    path("expert-application/", ExpertApplicationView.as_view(), name="expert-application"),
    path("2fa/", TwoFactorView.as_view(), name="two-factor"),
    path("2fa/verify/", TwoFactorLoginView.as_view(), name="two-factor-verify"),
    path("2fa/<str:step>/", TwoFactorView.as_view(), name="two-factor-step"),
]
