from django.contrib import admin
from django.utils import timezone
from .models import BookCopy, Loan

admin.site.site_header = "Library borrowing tracker"
admin.site.site_title = "Library tracker"
admin.site.index_title = "Librarian workspace"


@admin.register(BookCopy)
class BookCopyAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "copy_number", "availability"]
    search_fields = ["title", "author", "copy_number"]

    @admin.display(description="Availability")
    def availability(self, obj):
        return "On loan" if obj.loans.filter(returned_at__isnull=True).exists() else "Available"

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ["book", "borrower", "due_date", "status", "issued_by", "returned_at", "returned_by"]
    list_filter = ["returned_at", "due_date"]
    search_fields = ["book__title", "book__copy_number", "borrower__username"]
    readonly_fields = ["issued_at", "issued_by", "returned_at", "returned_by"]
    actions = ["record_returns"]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ["book", "borrower", "due_date", *self.readonly_fields]
        return self.readonly_fields

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "borrower":
            from django.contrib.auth import get_user_model
            kwargs["queryset"] = get_user_model().objects.filter(is_active=True, is_staff=False)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.issued_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Record return of selected books", permissions=["change"])
    def record_returns(self, request, queryset):
        count = queryset.filter(returned_at__isnull=True).update(
            returned_at=timezone.now(), returned_by=request.user)
        self.message_user(request, f"Recorded {count} return(s).")

    def has_delete_permission(self, request, obj=None):
        return False
