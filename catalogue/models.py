from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class BookCopy(models.Model):
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=150)
    copy_number = models.CharField(max_length=30, unique=True)

    class Meta:
        ordering = ["title", "copy_number"]
        verbose_name_plural = "book copies"
        permissions = [("manage_borrowers", "Can create and view borrower accounts")]

    def __str__(self):
        return f"{self.title} ({self.copy_number})"


class Loan(models.Model):
    book = models.ForeignKey(BookCopy, on_delete=models.PROTECT, related_name="loans")
    borrower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                 related_name="borrowed_loans")
    issued_at = models.DateTimeField(default=timezone.now, editable=False)
    due_date = models.DateField()
    returned_at = models.DateTimeField(null=True, blank=True, editable=False)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                  related_name="issued_loans", editable=False)
    returned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="received_loans", null=True, blank=True,
                                    editable=False)

    class Meta:
        ordering = ["-issued_at"]
        constraints = [
            models.UniqueConstraint(fields=["book"], condition=models.Q(returned_at__isnull=True),
                                    name="one_active_loan_per_copy"),
        ]

    def clean(self):
        if self.book_id and self.returned_at is None:
            active = Loan.objects.filter(book_id=self.book_id, returned_at__isnull=True)
            if self.pk:
                active = active.exclude(pk=self.pk)
            if active.exists():
                raise ValidationError({"book": "This copy is already on loan. Record its return first."})
        if self.due_date and self.issued_at:
            if self.due_date < timezone.localdate(self.issued_at):
                raise ValidationError({"due_date": "The due date cannot be before the issue date."})
        if self.borrower_id and (self.borrower.is_staff or not self.borrower.is_active):
            raise ValidationError({"borrower": "Choose an active borrower account."})

    @property
    def status(self):
        if self.returned_at:
            return "Returned"
        return "Overdue" if self.due_date < timezone.localdate() else "On loan"

    def __str__(self):
        return f"{self.book} - {self.borrower}"
