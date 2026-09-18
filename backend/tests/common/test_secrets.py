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
