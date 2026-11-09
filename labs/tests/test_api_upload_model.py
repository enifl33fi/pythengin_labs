"""/upload-model."""

from __future__ import annotations

import labs.api.main as main_module


def test_wrong_extension(client):
    r = client.post(
        "/upload-model",
        files={"file": ("x.txt", b"abc", "text/plain")},
    )
    assert r.status_code == 400


def test_too_big(client, monkeypatch):
    monkeypatch.setattr(main_module, "MAX_MODEL_SIZE", 10)
    monkeypatch.setattr(main_module, "UPLOAD_CHUNK_SIZE", 5)
    r = client.post(
        "/upload-model",
        files={"file": ("x.pkl", b"x" * 20, "application/octet-stream")},
    )
    assert r.status_code == 413


def test_invalid_pickle(client):
    r = client.post(
        "/upload-model",
        files={"file": ("x.pkl", b"not a pickle", "application/octet-stream")},
    )
    assert r.status_code == 400


def test_valid_upload(client, valid_pkl_bytes):
    r = client.post(
        "/upload-model",
        files={"file": ("x.pkl", valid_pkl_bytes, "application/octet-stream")},
    )
    assert r.status_code == 200
    assert main_module.model is not None
    assert main_module.model_source == "uploaded"
