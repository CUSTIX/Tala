"""Every teacher page refuses visitors who aren't signed in, and hides one teacher's classes from
another (404, as if they didn't exist). The URL list is walked from the URLconf, so a new page is
covered automatically."""

import datetime as dt
from decimal import Decimal

import pytest
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from grades.models import Assessment


def _app_patterns(resolver=None, prefix=""):
    resolver = resolver or get_resolver()
    for p in resolver.url_patterns:
        if isinstance(p, URLResolver):
            yield from _app_patterns(p, prefix + str(p.pattern))
        elif isinstance(p, URLPattern) and (prefix + str(p.pattern)).startswith("app/"):
            namespace = resolver.namespace if hasattr(resolver, "namespace") else None
            yield f"{namespace}:{p.name}" if namespace else p.name, p.pattern.converters


@pytest.fixture
def owned(section, learners):
    assessment = Assessment.objects.create(
        section=section,
        quarter=1,
        component="WW",
        title="Q",
        max_score=Decimal(10),
        date=dt.date(2026, 9, 1),
    )
    return {"pk": section.pk, "learner_pk": learners[0].pk, "assessment_pk": assessment.pk}


def _urls(owned):
    names = sorted({name for name, _ in _app_patterns()})
    assert len(names) > 20, names
    for name in names:
        from django.urls import NoReverseMatch

        for kwargs in (
            {},
            {"pk": owned["pk"]},
            {"pk": owned["pk"], "learner_pk": owned["learner_pk"]},
            {"pk": owned["pk"], "assessment_pk": owned["assessment_pk"]},
        ):
            try:
                yield name, reverse(name, kwargs=kwargs), bool(kwargs)
                break
            except NoReverseMatch:
                continue
        else:
            raise AssertionError(f"Can't build a URL for {name}")


@pytest.mark.django_db
def test_every_app_url_needs_sign_in(client, owned):
    for name, url, _ in _urls(owned):
        for method in (client.get, client.post):
            response = method(url)
            assert response.status_code == 302, (name, method.__name__)
            assert response["Location"].startswith(reverse("accounts:login")), name


@pytest.mark.django_db
def test_other_teachers_get_404_on_every_class_url(other_client, owned):
    for name, url, scoped in _urls(owned):
        if not scoped:
            continue
        for method in (other_client.get, other_client.post):
            response = method(url)
            assert response.status_code in (404, 405), (name, method.__name__, response.status_code)


@pytest.mark.django_db
def test_owner_can_open_every_get_page(signed_in, owned):
    post_only = {"section_delete", "learner_delete", "learner_new_link", "scan_mark", "delete"}
    for name, url, _ in _urls(owned):
        if name.split(":")[-1] in post_only:
            assert signed_in.get(url).status_code == 405, name
            continue
        response = signed_in.get(url)
        assert response.status_code in (200, 302), (name, response.status_code)
