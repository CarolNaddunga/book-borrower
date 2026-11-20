# Book Borrower

A Django library borrowing tracker by Carol Naddunga. The application uses a light
blue interface and separate librarian and borrower workflows.

## Features

- Public borrower registration and login with Django password validation and hashing.
- Private borrower loan history, due dates and return status.
- Searchable catalogue with availability filters.
- Librarian book-copy creation and editing, issuing and confirmed returns.
- Librarian-controlled borrower creation with a separate permission.
- Automatic issuing/returning staff records and timestamps.
- Database protection against two active loans for one copy.

## Run locally

Requires Python 3.12 or later.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py setup_demo
python manage.py add_sample_books
python manage.py runserver 127.0.0.1:8000
```

Open http://127.0.0.1:8000/. Sign up at `/accounts/signup/` or sign in at
`/accounts/login/`.

`setup_demo` asks you to choose a password for the fictional accounts `librarian`,
`borrower1` and `borrower2`, and creates ten sample book copies. It refuses to
overwrite existing accounts. `add_sample_books` adds five more published titles
without overwriting existing copy identifiers. These are sample holdings, not
confirmed records from the school library. Do not use a personal password for
demonstration accounts.

A private development secret is generated in `.django-secret-key` and excluded from
Git. Alternatively, set the `DJANGO_SECRET_KEY` environment variable. The database,
account data, session data and local execution records are also excluded from Git.
The committed settings are for local development, not hosted production use.

## Try the workflow

1. Sign in as `librarian`, open Book catalogue and issue an available copy to `borrower1`.
2. Sign out and sign in as `borrower1`. Open the loan and note its address.
3. Sign in as `borrower2`. The other borrower's loan address should return 404.
4. Return to the librarian account. Open Loans & returns, choose Record return,
   check the copy number and confirm. The copy becomes available again.
5. Borrowers cannot use librarian pages or create privileged accounts.

New public sign-ups are always borrowers. To create a borrower from the librarian
workspace, use Borrowers > Add a borrower. The Librarians group configured by
`setup_demo` has the required `catalogue.manage_borrowers` permission.

## Verify

```sh
python manage.py check
python manage.py test
```

Tests cover registration, validation, borrower privacy, permissions, issuing,
returns, CSRF protection and database consistency. Automated tests are development
evidence; they do not represent librarian acceptance or a real user pilot.

## Project structure

- `catalogue/models.py`: book copies, loans and database constraints.
- `catalogue/views.py`: borrower and librarian request handling.
- `catalogue/forms.py`: registration, book and loan forms.
- `catalogue/templates/` and `catalogue/static/`: interface and styling.
- `catalogue/tests.py`: functional and permission tests.
- `config/`: Django configuration and URL routes.

## Scope and references

This is an undergraduate project. It does not include fines, reservations,
notifications, password recovery or integration with an existing library system.
Library consultation, hosted deployment and stakeholder acceptance are separate
from the local implementation.

Uses Django's generated project structure, authentication and admin:

- https://docs.djangoproject.com/en/6.0/topics/auth/default/
- https://docs.djangoproject.com/en/6.0/ref/contrib/admin/
- https://docs.djangoproject.com/en/6.0/ref/models/constraints/

Initial code and documentation were prepared with AI assistance. Review and
understand the implementation, and record assistance according to course requirements.
