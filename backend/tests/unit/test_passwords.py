from app.services.passwords import hash_password, verify_password


def test_hash_verifies_matching_secret_and_rejects_other() -> None:
    secret = "a" * 12
    stored = hash_password(secret)
    assert stored != secret
    assert verify_password(stored, secret)
    assert not verify_password(stored, "b" * 12)
    assert not verify_password("not-a-hash", secret)
