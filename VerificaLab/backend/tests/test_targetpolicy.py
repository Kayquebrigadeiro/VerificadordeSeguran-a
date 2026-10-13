"""Política de alvo: somente loopback literal, origem exata, sem DNS."""

import pytest

from verificalab.targetpolicy import TargetPolicy, TargetPolicyError, parse_endpoint


def test_parse_endpoint_loopback_ipv4_ok():
    assert parse_endpoint("http://127.0.0.1:8477") == ("http", "127.0.0.1", 8477)


def test_parse_endpoint_loopback_range_ok():
    scheme, host, port = parse_endpoint("http://127.5.5.5:80")
    assert (scheme, host, port) == ("http", "127.5.5.5", 80)


def test_parse_endpoint_ipv6_loopback_ok():
    scheme, host, port = parse_endpoint("http://[::1]:8080")
    assert (scheme, host, port) == ("http", "::1", 8080)


@pytest.mark.parametrize("url,fragment", [
    ("http://example.com:80", "IP literal"),
    ("http://192.168.1.10:80", "loopback"),
    ("http://10.0.0.1:80", "loopback"),
    ("ftp://127.0.0.1:80", "http"),
    ("http://user:pass@127.0.0.1:80", "credenciais"),
    ("http://127.0.0.1:80/path", "apenas esquema://host:porta"),
    ("http://127.0.0.1:80?a=b", "apenas esquema://host:porta"),
])
def test_parse_endpoint_rejects(url, fragment):
    with pytest.raises(TargetPolicyError) as exc:
        parse_endpoint(url)
    assert fragment in exc.value.reason


def test_policy_blocks_foreign_origin():
    policy = TargetPolicy("http", "127.0.0.1", 8477)
    with pytest.raises(TargetPolicyError):
        policy.validate_url("http://127.0.0.1:9999/ok")
    with pytest.raises(TargetPolicyError):
        policy.validate_url("http://example.com/ok")
    with pytest.raises(TargetPolicyError):
        policy.validate_url("https://127.0.0.1:8477/ok")  # esquema trocado


def test_policy_blocks_dns_hostname():
    policy = TargetPolicy("http", "127.0.0.1", 8477)
    with pytest.raises(TargetPolicyError) as exc:
        policy.validate_url("http://localhost:8477/ok")
    assert "IP literal" in exc.value.reason


def test_policy_blocks_embedded_credentials():
    policy = TargetPolicy("http", "127.0.0.1", 8477)
    with pytest.raises(TargetPolicyError):
        policy.validate_url("http://x@127.0.0.1:8477/ok")


def test_policy_allows_registered_origin():
    policy = TargetPolicy("http", "127.0.0.1", 8477)
    url = policy.build("/ok?x=1")
    assert url == "http://127.0.0.1:8477/ok?x=1"


def test_redirect_to_foreign_destination_blocked():
    policy = TargetPolicy("http", "127.0.0.1", 8477)
    current = policy.build("/redirect-external")
    # destino com host não-loopback: recusado por IP literal
    with pytest.raises(TargetPolicyError) as exc:
        policy.validate_redirect(current, "http://example.com/")
    assert "IP literal" in exc.value.reason
    # destino loopback mas fora da porta cadastrada: recusado por origem
    with pytest.raises(TargetPolicyError) as exc2:
        policy.validate_redirect(current, "http://127.0.0.1:9999/x")
    assert "fora da origem" in exc2.value.reason


def test_redirect_relative_allowed():
    policy = TargetPolicy("http", "127.0.0.1", 8477)
    current = policy.build("/redirect-local")
    assert policy.validate_redirect(current, "/ok") == "http://127.0.0.1:8477/ok"


def test_policy_rejects_non_loopback_construction():
    with pytest.raises(TargetPolicyError):
        TargetPolicy("http", "8.8.8.8", 80)
    with pytest.raises(TargetPolicyError):
        TargetPolicy("javascript", "127.0.0.1", 80)
    with pytest.raises(TargetPolicyError):
        TargetPolicy("http", "localhost", 80)
