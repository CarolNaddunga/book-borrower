from django.core.management.base import BaseCommand
from django.db import transaction
from catalogue.models import BookCopy
from catalogue.sample_data import DEMO_TITLES


class Command(BaseCommand):
    help = 'Replace unchanged demonstration titles with published titles, keeping copies and loans intact.'

    @transaction.atomic
    def handle(self, *args, **options):
        updated = 0
        for number, (title, author) in enumerate(DEMO_TITLES, start=1):
            updated += BookCopy.objects.filter(
                copy_number=f'DEMO-{number:03}', title=f'Demonstration book {number}',
                author='Fictional author',
            ).update(title=title, author=author)
        self.stdout.write(self.style.SUCCESS(f'Updated {updated} placeholder titles. Existing copy numbers and loan records were preserved.'))
