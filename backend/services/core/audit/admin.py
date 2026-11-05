from django.contrib import admin
from django.http import HttpResponse
import csv
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'resource_type', 'resource_id')
    list_filter = ('action', 'resource_type', 'timestamp')
    search_fields = ('user__email', 'resource_type')
    actions = ['export_as_csv']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def export_as_csv(self, request, queryset):
        meta = self.model._meta
        field_names = [f.name for f in meta.fields]

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=audit_logs.csv'
        writer = csv.writer(response)

        writer.writerow(field_names)
        for obj in queryset:
            row = [getattr(obj, f) for f in field_names]
            writer.writerow(row)
        return response

    export_as_csv.short_description = 'Export selected as CSV'
