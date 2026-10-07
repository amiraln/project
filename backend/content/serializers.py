from rest_framework import serializers

from .models import FAQ, Appeal, Document, Group, News, NewsPhoto, Page, Person, SiteSettings, Vacancy


class SiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        exclude = ["id"]


class PageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Page
        fields = ["slug", "title_kk", "title_ru", "body_kk", "body_ru", "updated_at"]


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        exclude = ["order"]


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        exclude = ["order", "is_published", "show_photo"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not instance.show_photo:
            data["photo"] = None  # без согласия фото не отдаём вовсе
        return data


class DocumentSerializer(serializers.ModelSerializer):
    extension = serializers.SerializerMethodField()
    size = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ["id", "title_kk", "title_ru", "category", "language", "file", "extension", "size",
                  "published_at", "updated_at"]

    def get_extension(self, obj):
        return obj.file.name.rsplit(".", 1)[-1].lower() if obj.file else None

    def get_size(self, obj):
        try:
            return obj.file.size
        except (OSError, ValueError):
            return None


class NewsPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsPhoto
        fields = ["id", "image", "alt_kk", "alt_ru"]


class NewsListSerializer(serializers.ModelSerializer):
    class Meta:
        model = News
        fields = ["id", "kind", "title_kk", "title_ru", "summary_kk", "summary_ru", "cover",
                  "cover_alt_kk", "cover_alt_ru", "event_date", "published_at"]


class NewsDetailSerializer(NewsListSerializer):
    photos = NewsPhotoSerializer(many=True, read_only=True)

    class Meta(NewsListSerializer.Meta):
        fields = NewsListSerializer.Meta.fields + ["body_kk", "body_ru", "photos"]


class VacancySerializer(serializers.ModelSerializer):
    class Meta:
        model = Vacancy
        exclude = ["order", "is_active"]


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        exclude = ["order", "is_published"]


class AppealCreateSerializer(serializers.ModelSerializer):
    # Ловушка для ботов: поле скрыто от людей, боты его заполняют
    website = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Appeal
        fields = ["full_name", "contact", "subject", "message", "lang", "consent", "website"]

    def validate_consent(self, value):
        if value is not True:
            raise serializers.ValidationError("consent_required")
        return value

    def validate_lang(self, value):
        return value if value in ("kk", "ru") else "ru"

    def validate(self, attrs):
        if attrs.pop("website", ""):
            raise serializers.ValidationError("spam")
        return attrs


class AppealStaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appeal
        fields = ["id", "full_name", "contact", "subject", "message", "lang", "status", "staff_note",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "full_name", "contact", "subject", "message", "lang", "created_at", "updated_at"]
