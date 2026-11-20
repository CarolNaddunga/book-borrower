from functools import wraps
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST, require_safe
from .forms import BookCopyForm, IssueLoanForm, BorrowerCreationForm
from .models import BookCopy, Loan


def librarian_required(*permissions):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_staff or not request.user.has_perms(permissions):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


@login_required
@require_safe
def my_loans(request):
    if request.user.is_staff:
        return redirect("dashboard")
    loans = Loan.objects.filter(borrower=request.user).select_related("book")
    active = loans.filter(returned_at__isnull=True)
    return render(request, "catalogue/my_loans.html", {"loans": loans,
        "active_count": active.count(),
        "overdue_count": active.filter(due_date__lt=timezone.localdate()).count(),
        "returned_count": loans.filter(returned_at__isnull=False).count(),
    })


@login_required
@require_safe
def loan_detail(request, pk):
    loan = Loan.objects.select_related("book").filter(pk=pk, borrower=request.user).first()
    if loan is None:
        return render(request, "404.html", status=404)
    return render(request, "catalogue/loan_detail.html", {"loan": loan})


@librarian_required("catalogue.view_loan", "catalogue.view_bookcopy")
@require_safe
def dashboard(request):
    loans = Loan.objects.select_related("book", "borrower")
    active = loans.filter(returned_at__isnull=True)
    return render(request, "catalogue/dashboard.html", {
        "total_books": BookCopy.objects.count(), "on_loan": active.count(),
        "available": BookCopy.objects.count() - active.count(),
        "overdue": active.filter(due_date__lt=timezone.localdate()).count(),
        "recent_loans": loans[:5],
        "due_soon": active.filter(due_date__gte=timezone.localdate(),
            due_date__lte=timezone.localdate() + timedelta(days=3)).order_by("due_date")[:4],
        "featured_books": BookCopy.objects.annotate(on_loan=Exists(
            Loan.objects.filter(book_id=OuterRef("pk"), returned_at__isnull=True)))[:4],
    })


@login_required
@require_safe
def books(request):
    active = Loan.objects.filter(book_id=OuterRef("pk"), returned_at__isnull=True)
    copies = BookCopy.objects.annotate(on_loan=Exists(active))
    query = request.GET.get("q", "").strip()[:150]
    if query:
        copies = copies.filter(Q(title__icontains=query) | Q(author__icontains=query) | Q(copy_number__icontains=query))
    availability = request.GET.get("availability", "all")
    if availability == "available":
        copies = copies.filter(on_loan=False)
    elif availability == "borrowed":
        copies = copies.filter(on_loan=True)
    else:
        availability = "all"
    return render(request, "catalogue/books.html", {"books": copies, "query": query,
        "availability": availability, "result_count": copies.count()})


@librarian_required("catalogue.add_bookcopy")
@require_http_methods(["GET", "POST"])
def book_add(request):
    form = BookCopyForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Book copy added to the catalogue.")
        return redirect("books")
    return render(request, "catalogue/form.html", {"form": form, "heading": "Add a book copy",
        "intro": "Record one physical copy. Give each copy its own unique number.", "button": "Add book", "back": "books"})


@librarian_required("catalogue.change_bookcopy")
@require_http_methods(["GET", "POST"])
def book_edit(request, pk):
    book = get_object_or_404(BookCopy, pk=pk)
    form = BookCopyForm(request.POST if request.method == "POST" else None, instance=book)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Book details updated.")
        return redirect("books")
    return render(request, "catalogue/form.html", {"form": form, "heading": "Edit book details",
        "intro": str(book), "button": "Save changes", "back": "books"})


@librarian_required("catalogue.view_loan")
@require_safe
def loans(request):
    records = Loan.objects.select_related("book", "borrower", "issued_by", "returned_by")
    status = request.GET.get("status", "active")
    if status not in ["active", "overdue", "returned", "all"]:
        status = "active"
    if status in ["active", "overdue"]:
        records = records.filter(returned_at__isnull=True)
    if status == "overdue":
        records = records.filter(due_date__lt=timezone.localdate())
    elif status == "returned":
        records = records.filter(returned_at__isnull=False)
    return render(request, "catalogue/loans.html", {"loans": records, "status_filter": status})


@librarian_required("catalogue.add_loan")
@require_http_methods(["GET", "POST"])
def issue_loan(request):
    form = IssueLoanForm(request.POST if request.method == "POST" else None)
    selected = request.GET.get("book", "")
    if request.method == "GET" and selected.isdecimal() and len(selected) < 12:
        if form.fields["book"].queryset.filter(pk=int(selected)).exists():
            form.initial["book"] = int(selected)
    if request.method == "POST" and form.is_valid():
        loan = form.save(commit=False)
        loan.issued_by = request.user
        try:
            with transaction.atomic():
                loan.save()
        except IntegrityError:
            form.add_error("book", "This copy is no longer available. Choose another copy.")
        else:
            messages.success(request, "Book issued. The borrower can now see the loan in their account.")
            return redirect("loans")
    return render(request, "catalogue/form.html", {"form": form, "heading": "Issue a book",
        "intro": "Choose an available copy, a borrower and the agreed return date.", "button": "Issue book", "back": "loans"})


@librarian_required("catalogue.change_loan")
@require_POST
def return_loan(request, pk):
    loan = get_object_or_404(Loan, pk=pk)
    updated = Loan.objects.filter(pk=loan.pk, returned_at__isnull=True).update(
        returned_at=timezone.now(), returned_by=request.user)
    if updated:
        messages.success(request, "Return recorded. The book copy is available again.")
    else:
        messages.info(request, "This loan has already been returned. Its return record was kept unchanged.")
    return redirect("loans")


@librarian_required("catalogue.change_loan")
@require_safe
def confirm_return(request, pk):
    loan = get_object_or_404(Loan.objects.select_related("book", "borrower"), pk=pk)
    return render(request, "catalogue/confirm_return.html", {"loan": loan})


@librarian_required("catalogue.manage_borrowers")
@require_safe
def borrowers(request):
    accounts = get_user_model().objects.filter(is_staff=False, is_active=True).order_by("username")
    query = request.GET.get("q", "").strip()[:150]
    if query:
        accounts = accounts.filter(Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query))
    return render(request, "catalogue/borrowers.html", {"borrowers": accounts, "query": query})


@librarian_required("catalogue.manage_borrowers")
@require_http_methods(["GET", "POST"])
def borrower_add(request):
    form = BorrowerCreationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Borrower account created. Share the login details privately with the borrower.")
        return redirect("borrowers")
    return render(request, "catalogue/form.html", {"form": form, "heading": "Add a borrower",
        "intro": "Create a borrower account. This account can view its own loans and browse the catalogue.",
        "button": "Create borrower", "back": "borrowers"})


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("my_loans")
    form = BorrowerCreationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your account has been created. Sign in with your username and password.")
        return redirect("login")
    return render(request, "registration/signup.html", {"form": form})
