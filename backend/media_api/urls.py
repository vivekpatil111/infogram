from django.urls import path

from .views import LocalUploadView, PresignUploadView


urlpatterns = [
    path("presign/", PresignUploadView.as_view(), name="media-presign"),
    path("local-upload/<path:object_key>/", LocalUploadView.as_view(), name="media-local-upload"),
]
