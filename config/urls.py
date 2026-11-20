from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from catalogue import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/signup/", views.signup, name="signup"),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.my_loans, name="my_loans"),
    path("library/", views.dashboard, name="dashboard"),
    path("library/borrowers/", views.borrowers, name="borrowers"),
    path("library/borrowers/add/", views.borrower_add, name="borrower_add"),
    path("books/", views.books, name="books"),
    path("books/add/", views.book_add, name="book_add"),
    path("books/<int:pk>/edit/", views.book_edit, name="book_edit"),
    path("library/loans/", views.loans, name="loans"),
    path("library/loans/issue/", views.issue_loan, name="issue_loan"),
    path("library/loans/<int:pk>/return/confirm/", views.confirm_return, name="confirm_return"),
    path("library/loans/<int:pk>/return/", views.return_loan, name="return_loan"),
    path("loans/<int:pk>/", views.loan_detail, name="loan_detail"),
]
