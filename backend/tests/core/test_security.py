from app.core.security import generate_raw_token, hash_token


def test_generate_raw_token_is_url_safe():
    token = generate_raw_token()
    assert len(token) > 40
    assert " " not in token


def test_hash_token_is_deterministic():
    raw = generate_raw_token()
    assert hash_token(raw) == hash_token(raw)


def test_hash_token_differs_for_different_inputs():
    assert hash_token("abc") != hash_token("xyz")


def test_hash_token_length():
    assert len(hash_token("test")) == 64  # SHA-256 hex = 64 chars
