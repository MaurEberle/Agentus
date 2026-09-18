from __future__ import annotations

from app.common.secrets import mask_obj


def test_mask_obj_authorization_value() -> None:
    out = mask_obj({"Authorization": "Bearer abc", "x": 1})
    assert out == {"Authorization": "***", "x": 1}
