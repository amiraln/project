from django.urls import path

from . import views

app_name = "medjournal"

urlpatterns = [
    path("", views.index, name="index"),
    path("<slug:slug>/", views.journal_list, name="list"),
    path("<slug:slug>/print/", views.journal_print, name="print"),
    path("<slug:slug>/word/", views.journal_word, name="word"),
    path("<slug:slug>/print/period/", views.journal_period, name="print_period"),
    path("<slug:slug>/add/", views.record_edit, name="add"),
    path("<slug:slug>/fill-all/", views.fill_all, name="fill_all"),
    path("<slug:slug>/bulk/", views.bulk, name="bulk"),
    path("<slug:slug>/<int:pk>/", views.record_edit, name="edit"),
    path("<slug:slug>/<int:pk>/delete/", views.record_delete, name="delete"),
    path("<slug:slug>/<int:pk>/print/", views.record_print, name="record_print"),
    path("<slug:slug>/<int:pk>/word/", views.record_word, name="record_word"),
]
