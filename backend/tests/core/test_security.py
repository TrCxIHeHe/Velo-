from app.core.security import generate_raw_token, hash_token


class TestGenerateRawToken:
    def test_returns_string(self):
        assert isinstance(generate_raw_token(), str)

    def test_tokens_are_unique(self):
        tokens = {generate_raw_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_minimum_length(self):
        # 64 bytes → ~86 base64url chars
        assert len(generate_raw_token()) >= 80


class TestHashToken:
    def test_deterministic(self):
        raw = "some_raw_token_value"
        assert hash_token(raw) == hash_token(raw)

    def test_sha256_hex_length(self):
        # SHA-256 produces 64 hex chars
        assert len(hash_token("anything")) == 64

    def test_different_inputs_produce_different_hashes(self):
        assert hash_token("token_a") != hash_token("token_b")

    def test_hash_is_not_reversible_to_original(self):
        raw = generate_raw_token()
        hashed = hash_token(raw)
        assert raw not in hashed
