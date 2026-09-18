from django.urls import path

from . import views

urlpatterns = [
    path("team/", views.team_list, name="team_list"),
    path("team/new/", views.person_create, name="person_create"),
    path("team/<int:pk>/edit/", views.person_edit, name="person_edit"),
    path("team/<int:pk>/toggle-active/", views.person_toggle_active, name="person_toggle_active"),
    path("departments/new/", views.department_create, name="department_create"),
    path("departments/<int:pk>/edit/", views.department_edit, name="department_edit"),
]
