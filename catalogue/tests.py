from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from .models import BookCopy, Loan

class BorrowingFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user('librarian', is_staff=True)
        cls.staff.user_permissions.set(Permission.objects.filter(content_type__app_label='catalogue',
            codename__in=['view_bookcopy','add_bookcopy','change_bookcopy','view_loan','add_loan','change_loan']))
        cls.a = User.objects.create_user('alice')
        cls.b = User.objects.create_user('beth')
        cls.book = BookCopy.objects.create(title='Private sample title',author='Demo',copy_number='A1')
        cls.loan = Loan.objects.create(book=cls.book,borrower=cls.a,issued_by=cls.staff,
                                      due_date=timezone.localdate()+timedelta(days=7))


class BorrowingTests(BorrowingFixture):
    def test_login_required(self):
        for url in [reverse('my_loans'), reverse('loan_detail',args=[self.loan.pk])]:
            self.assertEqual(self.client.get(url).status_code,302)

    def test_borrower_record_isolation(self):
        self.client.force_login(self.a)
        self.assertContains(self.client.get(reverse('my_loans')),self.book.title)
        self.assertEqual(self.client.get(reverse('loan_detail',args=[self.loan.pk])).status_code,200)
        self.client.force_login(self.b)
        self.assertNotContains(self.client.get(reverse('my_loans')),self.book.title)
        response = self.client.get(reverse('loan_detail',args=[self.loan.pk]))
        self.assertEqual(response.status_code,404)
        self.assertContains(response, 'This page isn’t on the shelf.', status_code=404)
        self.assertNotContains(response, self.book.title, status_code=404)

    def test_borrower_cannot_access_librarian_actions(self):
        self.client.force_login(self.a)
        for name,args in [('admin:catalogue_bookcopy_add',[]),('admin:catalogue_loan_add',[]),
                          ('admin:catalogue_loan_change',[self.loan.pk])]:
            for method in [self.client.get,self.client.post]:
                self.assertEqual(method(reverse(name,args=args)).status_code,302)
        self.loan.refresh_from_db()
        self.assertIsNone(self.loan.returned_at)

    def test_database_blocks_two_active_loans(self):
        with self.assertRaises(IntegrityError),transaction.atomic():
            Loan.objects.create(book=self.book,borrower=self.b,issued_by=self.staff,due_date=timezone.localdate())

    def test_librarian_issue_return_and_reissue(self):
        self.client.force_login(self.staff)
        book=BookCopy.objects.create(title='Second book',author='Demo',copy_number='A2')
        response=self.client.post(reverse('admin:catalogue_loan_add'),{
            'book':book.pk,'borrower':self.b.pk,'due_date':timezone.localdate().isoformat(),'_save':'Save'})
        self.assertEqual(response.status_code,302)
        loan=Loan.objects.get(book=book)
        self.assertEqual(loan.issued_by,self.staff)
        data={'action':'record_returns','_selected_action':[loan.pk],'index':0}
        self.assertEqual(self.client.post(reverse('admin:catalogue_loan_changelist'),data).status_code,302)
        loan.refresh_from_db()
        returned=loan.returned_at
        self.assertIsNotNone(returned)
        self.assertEqual(loan.returned_by,self.staff)
        self.client.post(reverse('admin:catalogue_loan_changelist'),data)
        loan.refresh_from_db()
        self.assertEqual(loan.returned_at,returned)
        Loan.objects.create(book=book,borrower=self.a,issued_by=self.staff,due_date=timezone.localdate())

    def test_duplicate_admin_submission_is_validation_error(self):
        self.client.force_login(self.staff)
        response=self.client.post(reverse('admin:catalogue_loan_add'),{
            'book':self.book.pk,'borrower':self.b.pk,'due_date':timezone.localdate().isoformat()})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['adminform'].form.errors)
        self.assertEqual(Loan.objects.count(),1)

    def test_due_and_returned_status(self):
        self.assertEqual(self.loan.status,'On loan')
        self.loan.due_date=timezone.localdate()-timedelta(days=1)
        self.assertEqual(self.loan.status,'Overdue')
        self.loan.returned_at=timezone.now()
        self.assertEqual(self.loan.status,'Returned')

    def test_logout_ends_session(self):
        self.client.force_login(self.a)
        self.assertEqual(self.client.get(reverse('logout')).status_code,405)
        self.client.post(reverse('logout'))
        self.assertEqual(self.client.get(reverse('my_loans')).status_code,302)

    def test_return_requires_csrf(self):
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        response=client.post(reverse('admin:catalogue_loan_changelist'),{
            'action':'record_returns','_selected_action':[self.loan.pk]})
        self.assertEqual(response.status_code,403)
        self.loan.refresh_from_db()
        self.assertIsNone(self.loan.returned_at)

class ApplicationWorkflowTests(BorrowingFixture):
    def test_librarian_pages_render(self):
        self.client.force_login(self.staff)
        for name in ['dashboard','books','loans','book_add','issue_loan']:
            self.assertEqual(self.client.get(reverse(name)).status_code,200,name)
        self.assertRedirects(self.client.get(reverse('my_loans')),reverse('dashboard'))

    def test_borrower_denied_every_management_view(self):
        self.client.force_login(self.a)
        endpoints=[('dashboard',[]),('loans',[]),('book_add',[]),('book_edit',[self.book.pk]),
                   ('issue_loan',[]),('return_loan',[self.loan.pk])]
        for name,args in endpoints:
            for method in [self.client.get,self.client.post]:
                self.assertEqual(method(reverse(name,args=args)).status_code,403,name)
        self.assertEqual(self.client.get(reverse('books')).status_code,200)

    def test_staff_without_model_permissions_denied(self):
        user=get_user_model().objects.create_user('unprivileged_staff',is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code,403)
        self.assertEqual(self.client.post(reverse('return_loan',args=[self.loan.pk])).status_code,403)

    def test_custom_issue_return_workflow(self):
        self.client.force_login(self.staff)
        self.client.post(reverse('book_add'),{'title':'New book','author':'Author','copy_number':'NEW-1'})
        book=BookCopy.objects.get(copy_number='NEW-1')
        self.assertRedirects(self.client.post(reverse('issue_loan'),{
            'book':book.pk,'borrower':self.b.pk,'due_date':timezone.localdate().isoformat()}),reverse('loans'))
        loan=Loan.objects.get(book=book)
        self.assertEqual(loan.issued_by,self.staff)
        self.assertEqual(self.client.get(reverse('return_loan',args=[loan.pk])).status_code,405)
        self.client.post(reverse('return_loan',args=[loan.pk]))
        loan.refresh_from_db()
        self.assertEqual(loan.returned_by,self.staff)
        returned=loan.returned_at
        self.client.post(reverse('return_loan',args=[loan.pk]))
        loan.refresh_from_db()
        self.assertEqual(loan.returned_at,returned)
        self.assertContains(self.client.get(reverse('loans')+'?status=returned'),'New book')

    def test_issue_form_excludes_borrowed_book_and_rejects_past_due_date(self):
        self.client.force_login(self.staff)
        response=self.client.get(reverse('issue_loan'))
        self.assertNotIn(self.book,response.context['form'].fields['book'].queryset)
        response=self.client.post(reverse('issue_loan'),{
            'book':self.book.pk,'borrower':self.b.pk,'due_date':timezone.localdate().isoformat()})
        self.assertTrue(response.context['form'].errors)
        book=BookCopy.objects.create(title='Free book',author='Demo',copy_number='FREE')
        response=self.client.post(reverse('issue_loan'),{'book':book.pk,'borrower':self.b.pk,
            'due_date':(timezone.localdate()-timedelta(days=1)).isoformat()})
        self.assertIn('due_date',response.context['form'].errors)

    def test_catalogue_search_does_not_expose_borrower(self):
        self.client.force_login(self.b)
        response=self.client.get(reverse('books'),{'q':'Private'})
        self.assertContains(response,self.book.title)
        self.assertNotContains(response,'alice')
        self.assertNotContains(self.client.get(reverse('books'),{'q':'no such book'}),self.book.title)

    def test_custom_return_requires_csrf(self):
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        self.assertEqual(client.post(reverse('return_loan',args=[self.loan.pk])).status_code,403)

class SampleBookTests(TestCase):
    def test_sample_import_is_repeatable_and_preserves_existing_records(self):
        from django.core.management import call_command
        from io import StringIO
        existing = BookCopy.objects.create(copy_number='SAMPLE-001', title='My existing title', author='Existing author')
        call_command('add_sample_books', stdout=StringIO())
        call_command('add_sample_books', stdout=StringIO())
        self.assertEqual(BookCopy.objects.count(), 5)
        existing.refresh_from_db()
        self.assertEqual(existing.title, 'My existing title')
        self.assertTrue(BookCopy.objects.filter(title='Things Fall Apart', author='Chinua Achebe').exists())

class WorkflowRefinementTests(BorrowingFixture):
    def test_empty_post_shows_required_field_errors(self):
        self.client.force_login(self.staff)
        for name in ['book_add', 'issue_loan']:
            response = self.client.post(reverse(name), {})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].is_bound)
            self.assertTrue(response.context['form'].errors)

    def test_available_copy_can_be_preselected_but_borrowed_copy_cannot(self):
        self.client.force_login(self.staff)
        book = BookCopy.objects.create(title='Available title', author='Author', copy_number='READY-1')
        response = self.client.get(reverse('issue_loan'), {'book': book.pk})
        self.assertEqual(response.context['form'].initial['book'], book.pk)
        for value in [self.book.pk, 'invalid', '9' * 30]:
            response = self.client.get(reverse('issue_loan'), {'book': value})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('book', response.context['form'].initial)

    def test_return_confirmation_does_not_change_record(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('confirm_return', args=[self.loan.pk]))
        self.assertContains(response, self.book.copy_number)
        self.assertContains(response, 'Confirm return')
        self.loan.refresh_from_db()
        self.assertIsNone(self.loan.returned_at)
        self.client.post(reverse('return_loan', args=[self.loan.pk]))
        response = self.client.get(reverse('confirm_return', args=[self.loan.pk]))
        self.assertContains(response, 'already recorded')
        self.assertNotContains(response, '<button>Confirm return</button>')

    def test_borrower_cannot_view_confirmation(self):
        self.client.force_login(self.b)
        response = self.client.get(reverse('confirm_return', args=[self.loan.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, self.book.title, status_code=403)

class BorrowerAccountTests(BorrowingFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.staff.user_permissions.add(Permission.objects.get(
            content_type__app_label='catalogue', codename='manage_borrowers'))

    def test_librarian_creates_borrower_with_no_staff_privileges(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse('borrower_add'), {
            'username': 'new_reader', 'first_name': 'New', 'last_name': 'Reader',
            'password1': 'A-long-local-test-pass-947!', 'password2': 'A-long-local-test-pass-947!',
            'is_staff': 'on', 'is_superuser': 'on'})
        self.assertRedirects(response, reverse('borrowers'))
        reader = get_user_model().objects.get(username='new_reader')
        self.assertFalse(reader.is_staff)
        self.assertFalse(reader.is_superuser)
        self.assertTrue(reader.check_password('A-long-local-test-pass-947!'))
        self.assertTrue(self.client.login(username='new_reader', password='A-long-local-test-pass-947!'))
        self.assertEqual(self.client.get(reverse('my_loans')).status_code, 200)
        self.assertEqual(self.client.get(reverse('borrowers')).status_code, 403)

    def test_borrower_cannot_list_or_create_accounts(self):
        self.client.force_login(self.b)
        for name in ['borrowers', 'borrower_add']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)
            self.assertEqual(self.client.post(reverse(name), {}).status_code, 403)

    def test_separate_permission_required(self):
        user = get_user_model().objects.create_user('limited_librarian', is_staff=True)
        user.user_permissions.add(Permission.objects.get(content_type__app_label='catalogue', codename='add_loan'))
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('borrowers')).status_code, 403)

    def test_duplicate_username_and_weak_password_are_rejected(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse('borrower_add'), {
            'username': self.a.username, 'password1': '123', 'password2': '123'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('username', response.context['form'].errors)
        self.assertIn('password2', response.context['form'].errors)

    def test_catalogue_availability_filters_reflect_actual_loans(self):
        free = BookCopy.objects.create(title='Available now', author='Author', copy_number='FILTER-1')
        self.client.force_login(self.b)
        response = self.client.get(reverse('books'), {'availability': 'available'})
        self.assertContains(response, free.title)
        self.assertNotContains(response, self.book.title)
        response = self.client.get(reverse('books'), {'availability': 'borrowed'})
        self.assertContains(response, self.book.title)
        self.assertNotIn(free, list(response.context['books']))

class PublicSignupTests(TestCase):
    def details(self, **changes):
        data = {'username': 'public_reader', 'first_name': 'New', 'last_name': 'Reader',
                'password1': 'Strong-local-example-957!', 'password2': 'Strong-local-example-957!'}
        return {**data, **changes}

    def test_signup_link_and_form_available_without_login(self):
        self.assertContains(self.client.get(reverse('login')), reverse('signup'))
        self.assertContains(self.client.get(reverse('signup')), 'Create account')

    def test_registration_then_login_and_borrower_permissions(self):
        response = self.client.post(reverse('signup'), self.details(is_staff='on', is_superuser='on'))
        self.assertRedirects(response, reverse('login'))
        user = get_user_model().objects.get(username='public_reader')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.user_permissions.exists())
        self.assertFalse(user.groups.exists())
        self.assertNotEqual(user.password, self.details()['password1'])
        self.assertTrue(self.client.login(username='public_reader', password=self.details()['password1']))
        self.assertEqual(self.client.get(reverse('my_loans')).status_code, 200)
        self.assertEqual(self.client.get(reverse('borrowers')).status_code, 403)
        self.assertEqual(self.client.get(reverse('issue_loan')).status_code, 403)

    def test_mismatched_passwords_and_duplicate_username_show_errors(self):
        response = self.client.post(reverse('signup'), self.details(password2='Different-password-857!'))
        self.assertIn('password2', response.context['form'].errors)
        self.assertFalse(get_user_model().objects.exists())
        get_user_model().objects.create_user(username='public_reader')
        response = self.client.post(reverse('signup'), self.details())
        self.assertIn('username', response.context['form'].errors)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_blank_and_weak_password_submissions_rejected(self):
        response = self.client.post(reverse('signup'), {})
        self.assertIn('username', response.context['form'].errors)
        response = self.client.post(reverse('signup'), self.details(password1='123', password2='123'))
        self.assertIn('password2', response.context['form'].errors)
        self.assertFalse(get_user_model().objects.exists())

    def test_csrf_and_signed_in_redirect(self):
        self.assertEqual(Client(enforce_csrf_checks=True).post(reverse('signup'), self.details()).status_code, 403)
        user = get_user_model().objects.create_user(username='already_signed_in')
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse('signup')), reverse('my_loans'))

class HostedSetupTests(TestCase):
    def test_hosted_setup_is_repeatable_and_preserves_librarian_password(self):
        from django.core.management import call_command
        from unittest.mock import patch
        from io import StringIO
        with patch.dict('os.environ', {'LIBRARIAN_USERNAME': 'hosted_librarian', 'LIBRARIAN_PASSWORD': 'Host-test-947!'}):
            call_command('prepare_hosted_library', stdout=StringIO())
            account = get_user_model().objects.get(username='hosted_librarian')
            self.assertTrue(account.is_staff)
            self.assertFalse(account.is_superuser)
            self.assertTrue(account.has_perm('catalogue.manage_borrowers'))
            self.assertEqual(BookCopy.objects.count(), 15)
            original = account.password
            call_command('prepare_hosted_library', stdout=StringIO())
            account.refresh_from_db()
            self.assertEqual(account.password, original)
            self.assertEqual(BookCopy.objects.count(), 15)

    def test_hosted_setup_does_not_promote_an_existing_borrower(self):
        from django.core.management import call_command, CommandError
        from unittest.mock import patch
        from io import StringIO
        account = get_user_model().objects.create_user(username='occupied_name')
        with patch.dict('os.environ', {'LIBRARIAN_USERNAME': 'occupied_name', 'LIBRARIAN_PASSWORD': 'Host-test-947!'}):
            with self.assertRaises(CommandError):
                call_command('prepare_hosted_library', stdout=StringIO())
        account.refresh_from_db()
        self.assertFalse(account.is_staff)
