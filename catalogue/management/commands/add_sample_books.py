from django.core.management.base import BaseCommand
from django.db import transaction
from catalogue.models import BookCopy

# Published books; copy numbers below are local sample identifiers, not ISBNs
# or a claim that the school library owns these copies.
SAMPLE_BOOKS = [
    ("SAMPLE-001", "Python Crash Course", "Eric Matthes"),
    ("SAMPLE-002", "The Web Application Hacker's Handbook: Finding and Exploiting Security Flaws",
     "Dafydd Stuttard and Marcus Pinto"),
    ("SAMPLE-003", "Computer Networks", "Andrew S. Tanenbaum and David J. Wetherall"),
    ("SAMPLE-004", "Things Fall Apart", "Chinua Achebe"),
    ("SAMPLE-005", "Pride and Prejudice", "Jane Austen"),
]


class Command(BaseCommand):
    help = "Add five real titles as sample copies without overwriting existing records."

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        for copy_number, title, author in SAMPLE_BOOKS:
            _, added = BookCopy.objects.get_or_create(
                copy_number=copy_number, defaults={"title": title, "author": author})
            created += added
        self.stdout.write(self.style.SUCCESS(
            f"Added {created} sample book copies; skipped {len(SAMPLE_BOOKS) - created} existing identifiers."
        ))
