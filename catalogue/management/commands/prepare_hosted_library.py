import os
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from catalogue.models import BookCopy
from catalogue.sample_data import DEMO_TITLES
from catalogue.management.commands.add_sample_books import SAMPLE_BOOKS


class Command(BaseCommand):
    help = 'Seed sample titles and create the hosted librarian once from private environment settings.'

    @transaction.atomic
    def handle(self, *args, **options):
        for number, (title, author) in enumerate(DEMO_TITLES, 1):
            BookCopy.objects.get_or_create(copy_number=f'DEMO-{number:03}', defaults={'title': title, 'author': author})
        for code, title, author in SAMPLE_BOOKS:
            BookCopy.objects.get_or_create(copy_number=code, defaults={'title': title, 'author': author})
        username = os.environ.get('LIBRARIAN_USERNAME', 'librarian')
        password = os.environ.get('LIBRARIAN_PASSWORD')
        if not password:
            raise CommandError('Set LIBRARIAN_PASSWORD in the hosting dashboard.')
        User = get_user_model()
        account = User.objects.filter(username=username).first()
        if account is not None and not account.is_staff:
            raise CommandError('The configured librarian username belongs to a borrower; choose another username.')
        if account is None:
            account = User.objects.create_user(username=username, password=password, is_staff=True)
            group, _ = Group.objects.get_or_create(name='Librarians')
            group.permissions.set(Permission.objects.filter(content_type__app_label='catalogue', codename__in=[
                'view_bookcopy','add_bookcopy','change_bookcopy','view_loan','add_loan','change_loan','manage_borrowers']))
            account.groups.add(group)
        self.stdout.write(self.style.SUCCESS('Hosted catalogue and librarian ready. No passwords written to logs.'))
