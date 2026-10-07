from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import generics, mixins, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import serializers as s
from .models import FAQ, Appeal, Document, Group, News, Page, Person, SiteSettings, Vacancy
from .permissions import StaffModelPermissions


class SettingsView(APIView):
    def get(self, request):
        return Response(s.SiteSettingsSerializer(SiteSettings.load(), context={"request": request}).data)


class PageView(generics.RetrieveAPIView):
    queryset = Page.objects.all()
    serializer_class = s.PageSerializer
    lookup_field = "slug"


class GroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Group.objects.all()
    serializer_class = s.GroupSerializer


class PersonViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = s.PersonSerializer

    def get_queryset(self):
        qs = Person.objects.filter(is_published=True)
        kind = self.request.query_params.get("kind")
        return qs.filter(kind=kind) if kind else qs


class DocumentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = s.DocumentSerializer

    def get_queryset(self):
        qs = Document.objects.filter(is_published=True)
        cats = self.request.query_params.get("category")
        return qs.filter(category__in=cats.split(",")) if cats else qs


class NewsPagination(PageNumberPagination):
    page_size = 9
    page_size_query_param = "page_size"
    max_page_size = 9

    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        response.data["pages"] = self.page.paginator.num_pages
        return response


class NewsViewSet(viewsets.ReadOnlyModelViewSet):
    pagination_class = NewsPagination

    def get_queryset(self):
        qs = News.objects.filter(is_published=True, published_at__lte=timezone.now())
        if self.action == "retrieve":
            return qs.prefetch_related("photos")
        kind = self.request.query_params.get("kind")
        return qs.filter(kind=kind) if kind else qs

    def get_serializer_class(self):
        return s.NewsDetailSerializer if self.action == "retrieve" else s.NewsListSerializer


class VacancyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Vacancy.objects.filter(is_active=True)
    serializer_class = s.VacancySerializer


class FAQViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = s.FAQSerializer

    def get_queryset(self):
        qs = FAQ.objects.filter(is_published=True)
        section = self.request.query_params.get("section")
        return qs.filter(section=section) if section else qs


@method_decorator(csrf_protect, name="dispatch")
class AppealCreateView(generics.CreateAPIView):
    serializer_class = s.AppealCreateSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "appeals"

    def create(self, request, *args, **kwargs):
        super().create(request, *args, **kwargs)
        return Response({"ok": True}, status=201)  # не возвращаем персональные данные обратно


class AppealStaffViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = s.AppealStaffSerializer
    permission_classes = [StaffModelPermissions]
    http_method_names = ["get", "patch", "head", "options"]
    queryset = Appeal.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        status = self.request.query_params.get("status")
        return qs.filter(status__in=status.split(",")) if status else qs
