from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("management/", include("accounts.urls")),
    path("", include("requests_app.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "Zoomart — ხარჯებისა და მოთხოვნების ადმინისტრირება"
admin.site.site_title = "Zoomart ადმინი"
admin.site.index_title = "სისტემის კონფიგურაცია"
