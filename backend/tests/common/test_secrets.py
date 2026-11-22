from app.common.secrets import mask_obj, mask_text


def test_mask_text_bearer_keeps_surrounding() -> None:
    assert mask_text("Authorization: Bearer abcdef.token") == "Authorization: Bearer ***"
    assert mask_text("bearer xyz") == "bearer ***"


def test_mask_text_sk_key() -> None:
    assert mask_text("key=sk-abcdefghijklmnop") == "key=sk-***"
    assert mask_text("sk-proj-12_34-ABCDEFGH") == "sk-***"


def test_mask_text_does_not_wipe_whole_string() -> None:
    out = mask_text("failed with Bearer secret-value and sk-12345678xxxx")
    assert "failed with" in out
    assert "and" in out
    assert "Bearer ***" in out
    assert "sk-***" in out
    assert "secret-value" not in out
    assert "12345678xxxx" not in out


def test_mask_text_short_sk_unchanged() -> None:
    assert mask_text("sk-short") == "sk-short"


def test_mask_obj_secret_keys() -> None:
    src = {
        "apiKey": "live-secret",
        "api_key": "other",
        "token": "t",
        "password": "p",
        "authorization": "Bearer abc",
        "secret": "s",
        "APIKEY": "upper",
        "name": "ok",
    }
    out = mask_obj(src)
    assert isinstance(out, dict)
    for key in ("apiKey", "api_key", "token", "password", "authorization", "secret", "APIKEY"):
        assert out[key] == "***"
    assert out["name"] == "ok"
    assert src["apiKey"] == "live-secret"


def test_mask_obj_nested_and_list() -> None:
    src = {
        "items": [
            {"name": "a", "token": "nope"},
            "Bearer abc",
        ],
        "meta": {"sk": "sk-abcdefghijkl"},
    }
    out = mask_obj(src)
    assert isinstance(out, dict)
    items = out["items"]
    assert isinstance(items, list)
    assert items[0] == {"name": "a", "token": "***"}
    assert items[1] == "Bearer ***"
    assert out["meta"] == {"sk": "sk-***"}


def test_mask_obj_tuple_and_scalars() -> None:
    assert mask_obj(("Bearer a", 1, True, None)) == ("Bearer ***", 1, True, None)
    assert mask_obj(42) == 42
    assert mask_obj(None) is None


def test_mask_obj_depth_cap() -> None:
    inner: object = {"token": "visible-if-too-deep"}
    for _ in range(8):
        inner = {"wrap": inner}
    out = mask_obj(inner)
    node: object = out
    for _ in range(8):
        assert isinstance(node, dict)
        node = node["wrap"]
    assert node == "***"


def test_mask_text_provider_keys() -> None:
    from app.common.secrets import mask_text

    text = (
        "gemini AIzaSyA1b2C3d4E5f6G7h8I9j0KlMnOpQrStUvW "
        "xai xai-AbCdEfGhIjKlMnOpQrStUv "
        "gh ghp_abcdefghijklmnopqrstuvwxyz0123 ok"
    )
    masked = mask_text(text)
    assert "AIzaSyA1" not in masked and "AIza***" in masked
    assert "xai-AbCd" not in masked and "xai-***" in masked
    assert "ghp_abc" not in masked
    assert masked.endswith(" ok")


def test_mask_obj_header_style_keys() -> None:
    from app.common.secrets import mask_obj

    masked = mask_obj({"x-api-key": "plain", "accessToken": "plain", "model": "m"})
    assert masked == {"x-api-key": "***", "accessToken": "***", "model": "m"}


def test_mask_content_keeps_code_templates() -> None:
    from app.common.secrets import mask_content

    for sample in (
        'headers = {"Authorization": f"Bearer {token}"}',
        "Authorization: Bearer ${ACCESS_TOKEN}",
        '"Bearer " + token',
        "curl -H 'Authorization: Bearer <token>'",
        "Bearer YOUR_API_KEY_HERE",
    ):
        assert mask_content(sample) == sample


def test_mask_content_masks_real_tokens() -> None:
    from app.common.secrets import mask_content

    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123DEF456"
    assert mask_content(f"Authorization: Bearer {jwt}") == "Authorization: Bearer ***"
    assert mask_content("key=sk-abcdefghijklmnop") == "key=sk-***"


def test_known_secret_is_masked_everywhere() -> None:
    from app.common.secrets import (
        forget_secrets,
        mask_content,
        mask_content_obj,
        mask_text,
        remember_secret,
    )

    forget_secrets()
    try:
        remember_secret("tvly-PLAINVALUE-without-pattern")
        remember_secret('{"token":"custom-token-value","headers":{"X-Api-Key":"header-key-value"}}')
        remember_secret("short")  # too short to register
        text = "a tvly-PLAINVALUE-without-pattern b custom-token-value c header-key-value d short"
        assert mask_content(text) == "a *** b *** c *** d short"
        assert mask_text(text) == "a *** b *** c *** d short"
        assert mask_content_obj({"content": "x header-key-value y"}) == {"content": "x *** y"}
    finally:
        forget_secrets()
