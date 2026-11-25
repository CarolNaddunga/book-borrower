import re
from django.db import migrations


def rename_book_codes(apps, schema_editor):
    BookCopy = apps.get_model("catalogue", "BookCopy")
    used = set(BookCopy.objects.values_list("copy_number", flat=True))
    next_number = 16
    for book in BookCopy.objects.order_by("pk").iterator():
        match = re.fullmatch(r"(DEMO|SAMPLE)-(\d+)", book.copy_number)
        if not match:
            continue
        number = int(match.group(2)) + (10 if match.group(1) == "SAMPLE" else 0)
        code = f"LIB-{number:03}"
        while code in used:
            code = f"LIB-{next_number:03}"
            next_number += 1
        used.add(code)
        BookCopy.objects.filter(pk=book.pk).update(copy_number=code)


class Migration(migrations.Migration):
    dependencies = [("catalogue", "0002_alter_bookcopy_options")]
    operations = [migrations.RunPython(rename_book_codes, migrations.RunPython.noop)]
