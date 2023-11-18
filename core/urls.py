from django.urls import include, path

from core import views

urlpatterns = [
    path("", views.index, name="index"),
    path("login/", views.login, name="login"),
    path("callback", views.oauth_callback, name="callback"),
    path("logout/", views.logout, name="logout"),
    path("tenants/", views.tenants, name="tenants"),
    path("export_token/", views.export_token, name="export_token"),
    path(
        "create_contact_person",
        views.create_contact_person,
        name="create_contact_person",
    ),
    path(
        "create_multiple_contacts",
        views.create_multiple_contacts,
        name="create_multiple_contacts",
    ),
    path("get_invoices/", views.get_invoices, name="get_invoices"),
    path("refresh_token/", views.refresh_token, name="refresh_token"),
]
