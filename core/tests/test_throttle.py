import pytest
from django.test import RequestFactory

from core import throttle


@pytest.mark.django_db
def test_limit_allows_up_to_n_then_refuses():
    assert all(throttle.hit("t", "1.2.3.4", 3) for _ in range(3))
    assert not throttle.hit("t", "1.2.3.4", 3)
    assert throttle.hit("t", "5.6.7.8", 3), "another visitor has their own budget"


def test_client_ip_uses_the_configured_header_only(settings):
    request = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="6.6.6.6", REMOTE_ADDR="10.0.0.1")
    assert throttle.client_ip(request) == "10.0.0.1", "X-Forwarded-For can be forged"
    settings.CLIENT_IP_HEADER = "HTTP_CF_CONNECTING_IP"
    request = RequestFactory().get("/", HTTP_CF_CONNECTING_IP="9.9.9.9", REMOTE_ADDR="10.0.0.1")
    assert throttle.client_ip(request) == "9.9.9.9"
