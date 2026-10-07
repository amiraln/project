from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("groups", views.GroupViewSet, basename="group")
router.register("people", views.PersonViewSet, basename="person")
router.register("documents", views.DocumentViewSet, basename="document")
router.register("news", views.NewsViewSet, basename="news")
router.register("vacancies", views.VacancyViewSet, basename="vacancy")
router.register("faq", views.FAQViewSet, basename="faq")
router.register("staff/appeals", views.AppealStaffViewSet, basename="staff-appeal")

urlpatterns = [
    path("settings/", views.SettingsView.as_view()),
    path("pages/<slug:slug>/", views.PageView.as_view()),
    path("appeals/", views.AppealCreateView.as_view()),
    path("", include(router.urls)),
]
