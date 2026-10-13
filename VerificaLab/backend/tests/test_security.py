"""Segredos: sanitização, redação, Host/Origin/CSRF e cofre cifrado."""

from verificalab import security


def test_sanitize_strips_ansi_and_controls():
    dirty = "\x1b[31mvermelho\x1b[0m\x00\nsegunda\x07linha"
    clean = security.sanitize_text(dirty)
    assert "\x1b" not in clean and "\x00" not in clean
    assert "vermelho" in clean and "segunda" in clean


def test_sanitize_truncates():
    clean = security.sanitize_text("x" * 5000, max_len=100)
    assert clean.startswith("x" * 100) and "truncado" in clean


def test_redact_patterns():
    text = 'Authorization: Bearer abcdef123456 token=meusegredo123 "password": "hunter2"'
    out = security.redact(text)
    assert "abcdef123456" not in out
    assert "meusegredo123" not in out
    assert "hunter2" not in out


def test_registered_secret_redacted_everywhere():
    security.register_secret("valor-super-secreto-42")
    out = security.redact("cabecalho com valor-super-secreto-42 aqui")
    assert "valor-super-secreto-42" not in out


def test_redact_obj_masks_secret_keys():
    obj = {"api_key": "abc123", "nested": {"Authorization": "Bearer x"},
           "normal": "ok"}
    out = security.redact_obj(obj)
    assert out["api_key"] == "***"
    assert out["nested"]["Authorization"] == "***"
    assert out["normal"] == "ok"


def test_host_allowed_only_loopback():
    assert security.host_allowed("127.0.0.1:8400")
    assert security.host_allowed("localhost:8400")
    assert security.host_allowed("[::1]:8400")
    assert not security.host_allowed("example.com:8400")
    assert not security.host_allowed(None)


def test_origin_allowed():
    from verificalab import config
    assert security.origin_allowed(None)
    assert security.origin_allowed(f"http://127.0.0.1:{config.PORT}")
    assert not security.origin_allowed("http://evil.example")


def test_csrf_required_for_mutations():
    token = security.csrf_token()
    headers = {"X-VerificaLab-CSRF": token}
    assert security.check_mutation("POST", "127.0.0.1:8400", None,
                                   lambda k: headers.get(k)) is None
    assert security.check_mutation("POST", "127.0.0.1:8400", None,
                                   lambda k: None) is not None
    assert security.check_mutation("GET", "127.0.0.1:8400", None,
                                   lambda k: None) is None
    assert security.check_mutation(
        "POST", "127.0.0.1:8400", "http://evil.example",
        lambda k: headers.get(k)) is not None


def test_vault_roundtrip_and_no_plaintext():
    vault = security.get_vault()
    token = vault.encrypt("meu-token-123")
    assert "meu-token-123" not in token
    assert vault.decrypt(token) == "meu-token-123"
