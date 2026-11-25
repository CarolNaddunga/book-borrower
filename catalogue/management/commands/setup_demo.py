from getpass import getpass
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from catalogue.models import BookCopy
from catalogue.sample_data import DEMO_TITLES


class Command(BaseCommand):
    help = "Create fictional demo accounts and ten book copies; prompts for a demo password."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        names = ["librarian", "borrower1", "borrower2"]
        if User.objects.filter(username__in=names).exists():
            raise CommandError("Demo accounts already exist. Existing accounts were not changed.")
        password = getpass("Choose a password for the three local demo accounts: ")
        if password != getpass("Confirm password: "):
            raise CommandError("Passwords do not match.")
        try:
            validate_password(password)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages))
        group, _ = Group.objects.get_or_create(name="Librarians")
        group.permissions.set(Permission.objects.filter(content_type__app_label="catalogue",
            codename__in=["manage_borrowers", "view_bookcopy", "add_bookcopy", "change_bookcopy", "view_loan", "add_loan", "change_loan"]))
        librarian = User.objects.create_user("librarian", password=password, is_staff=True)
        librarian.groups.add(group)
        for name in names[1:]:
            User.objects.create_user(name, password=password)
        for number, (title, author) in enumerate(DEMO_TITLES, start=1):
            BookCopy.objects.get_or_create(copy_number=f"LIB-{number:03}", defaults={
                "title": title, "author": author})
        self.stdout.write(self.style.SUCCESS("Created librarian, borrower1, borrower2 and ten sample copies of published books. No real borrower records were used."))
