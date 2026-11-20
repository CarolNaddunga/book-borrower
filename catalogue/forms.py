from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from .models import BookCopy, Loan


class BookCopyForm(forms.ModelForm):
    class Meta:
        model = BookCopy
        fields = ["title", "author", "copy_number"]
        help_texts = {"copy_number": "A unique identifier for this physical copy, for example LIB-001."}


class IssueLoanForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = ["book", "borrower", "due_date"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["book"].queryset = BookCopy.objects.exclude(pk__in=Loan.objects.filter(returned_at__isnull=True).values("book_id"))
        self.fields["borrower"].queryset = get_user_model().objects.filter(is_active=True, is_staff=False)
        self.fields["due_date"].widget.attrs["min"] = timezone.localdate().isoformat()


class BorrowerCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ["username", "first_name", "last_name"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
        return user
