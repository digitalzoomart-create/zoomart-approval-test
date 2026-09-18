from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("requests/", views.request_list, name="request_list"),
    path("requests/export/", views.request_list_export, name="request_list_export"),
    path("requests/new/", views.request_create, name="request_create"),
    path("requests/<int:pk>/", views.request_detail, name="request_detail"),
    path("requests/<int:pk>/edit/", views.request_edit, name="request_edit"),
    path("requests/<int:pk>/submit/", views.request_submit, name="request_submit"),
    path("requests/<int:pk>/cancel/", views.request_cancel, name="request_cancel"),
    path("requests/<int:pk>/approve/", views.request_approve, name="request_approve"),
    path("requests/<int:pk>/reject/", views.request_reject, name="request_reject"),
    path("requests/<int:pk>/request-info/", views.request_more_info, name="request_more_info"),
    path("requests/<int:pk>/complete/", views.request_complete, name="request_complete"),
    path("requests/<int:pk>/attachments/<int:att_id>/download/", views.attachment_download, name="attachment_download"),
    path("requests/<int:pk>/finance/purchase-in-progress/", views.finance_mark_purchase_in_progress, name="finance_purchase_in_progress"),
    path("requests/<int:pk>/finance/purchased/", views.finance_mark_purchased, name="finance_purchased"),
    path("requests/<int:pk>/finance/paid/", views.finance_mark_paid, name="finance_paid"),
]
