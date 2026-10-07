from rest_framework.permissions import DjangoModelPermissions


class StaffModelPermissions(DjangoModelPermissions):
    """Только сотрудники (is_staff) с нужными правами из админки, включая право «просмотр»."""

    perms_map = {
        **DjangoModelPermissions.perms_map,
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "HEAD": ["%(app_label)s.view_%(model_name)s"],
    }

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff) and super().has_permission(request, view)
