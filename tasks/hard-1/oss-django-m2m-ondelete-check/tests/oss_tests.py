"""Hidden behavioral tests for oss-django-m2m-ondelete-check (django #21746).

A new system check `fields.E323`: an auto-created ManyToMany *through* model uses
Python-level cascade, so if either end model's ForeignKey uses a *database-level*
`on_delete` variant (e.g. `DB_CASCADE`), the two cannot be mixed and the field must
raise E323. Graded through the public `Field.check()` output — the presence/absence
of E323 and which field it points at — never internal check plumbing.
"""

from __future__ import annotations

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        INSTALLED_APPS=["django.contrib.contenttypes", "django.contrib.auth"],
        USE_TZ=True,
    )
    django.setup()

from django.db import models  # noqa: E402
from django.test.utils import isolate_apps  # noqa: E402


def _e323(field, model):
    return [e for e in field.check(from_model=model) if getattr(e, "id", None) == "fields.E323"]


# --- fail_to_pass: the E323 check did not exist at the base commit ------------


@isolate_apps("testapp")
def test_both_ends_db_cascade_flags_e323() -> None:
    class OMP(models.Model):
        class Meta:
            app_label = "testapp"

    class OtherModel(models.Model):
        parent = models.ForeignKey(OMP, on_delete=models.DB_CASCADE)

        class Meta:
            app_label = "testapp"

    class Parent(models.Model):
        class Meta:
            app_label = "testapp"

    class Child(models.Model):
        parent = models.ForeignKey(Parent, on_delete=models.DB_CASCADE)
        other_models = models.ManyToManyField(OtherModel)

        class Meta:
            app_label = "testapp"

    errors = _e323(Child._meta.get_field("other_models"), Child)
    assert len(errors) == 2
    assert all(str(e.obj).endswith("parent") for e in errors)


@isolate_apps("testapp")
def test_source_end_db_cascade_flags_e323() -> None:
    class OMP(models.Model):
        class Meta:
            app_label = "testapp"

    class OtherModel(models.Model):
        parent = models.ForeignKey(OMP, on_delete=models.CASCADE)  # Python-level

        class Meta:
            app_label = "testapp"

    class Parent(models.Model):
        class Meta:
            app_label = "testapp"

    class Child(models.Model):
        parent = models.ForeignKey(Parent, on_delete=models.DB_CASCADE)  # database-level
        other_models = models.ManyToManyField(OtherModel)

        class Meta:
            app_label = "testapp"

    errors = _e323(Child._meta.get_field("other_models"), Child)
    assert len(errors) == 1
    assert str(errors[0].obj) == "testapp.Child.parent"


@isolate_apps("testapp")
def test_target_end_db_cascade_flags_e323() -> None:
    class OMP(models.Model):
        class Meta:
            app_label = "testapp"

    class OtherModel(models.Model):
        parent = models.ForeignKey(OMP, on_delete=models.DB_CASCADE)  # database-level

        class Meta:
            app_label = "testapp"

    class Parent(models.Model):
        class Meta:
            app_label = "testapp"

    class Child(models.Model):
        parent = models.ForeignKey(Parent, on_delete=models.CASCADE)  # Python-level
        other_models = models.ManyToManyField(OtherModel)

        class Meta:
            app_label = "testapp"

    errors = _e323(Child._meta.get_field("other_models"), Child)
    assert len(errors) == 1
    assert str(errors[0].obj) == "testapp.OtherModel.parent"


# --- pass_to_pass: no false positives (pass at base and after the patch) ------


@isolate_apps("testapp")
def test_all_python_on_delete_no_e323() -> None:
    class OMP(models.Model):
        class Meta:
            app_label = "testapp"

    class OtherModel(models.Model):
        parent = models.ForeignKey(OMP, on_delete=models.CASCADE)

        class Meta:
            app_label = "testapp"

    class Parent(models.Model):
        class Meta:
            app_label = "testapp"

    class Child(models.Model):
        parent = models.ForeignKey(Parent, on_delete=models.CASCADE)
        other_models = models.ManyToManyField(OtherModel)

        class Meta:
            app_label = "testapp"

    assert _e323(Child._meta.get_field("other_models"), Child) == []


@isolate_apps("testapp")
def test_manual_through_model_no_e323() -> None:
    """A manually-created through model is checked on its own, so the M2M field
    must not raise E323 even when the ends use database-level on_delete."""

    class OMP(models.Model):
        class Meta:
            app_label = "testapp"

    class OtherModel(models.Model):
        parent = models.ForeignKey(OMP, on_delete=models.DB_CASCADE)

        class Meta:
            app_label = "testapp"

    class Parent(models.Model):
        class Meta:
            app_label = "testapp"

    class Through(models.Model):
        child = models.ForeignKey("Child", on_delete=models.CASCADE)
        other = models.ForeignKey(OtherModel, on_delete=models.CASCADE)

        class Meta:
            app_label = "testapp"

    class Child(models.Model):
        parent = models.ForeignKey(Parent, on_delete=models.DB_CASCADE)
        other_models = models.ManyToManyField(OtherModel, through=Through)

        class Meta:
            app_label = "testapp"

    assert _e323(Child._meta.get_field("other_models"), Child) == []
