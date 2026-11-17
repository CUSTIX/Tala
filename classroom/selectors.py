from django.shortcuts import get_object_or_404

from classroom.models import Learner, Section


def sections_for(teacher):
    return Section.objects.filter(teacher=teacher)


def section_for(teacher, pk) -> Section:
    """A teacher's own class, or 404: other teachers' classes don't exist for them."""
    return get_object_or_404(Section, pk=pk, teacher=teacher)


def learner_for(section: Section, pk) -> Learner:
    return get_object_or_404(Learner, pk=pk, section=section)


def learner_by_token(token: str) -> Learner:
    return get_object_or_404(Learner.objects.select_related("section"), share_token=token)
