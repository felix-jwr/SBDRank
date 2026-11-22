import json

import httpx
import pytest

from sbdrank.ingest import download

URL = "https://example.test/openpowerlifting-latest.zip"
LAST_MODIFIED = "Sat, 21 Nov 2026 03:07:41 GMT"


# --- update_headers -------------------------------------------------------------------------


def test_update_headers_empty_metadata():
    assert download.update_headers({}) == {}


def test_update_headers_etag_only():
    assert download.update_headers({"ETag": '"abc"'}) == {"If-None-Match": '"abc"'}


def test_update_headers_both():
    metadata = {"ETag": '"abc"', "Last-Modified": LAST_MODIFIED}
    assert download.update_headers(metadata) == {
        "If-None-Match": '"abc"',
        "If-Modified-Since": LAST_MODIFIED,
    }


def test_update_headers_ignores_unrelated_keys():
    assert download.update_headers({"Url": URL}) == {}


def test_update_headers_skips_none_values():
    headers = download.update_headers({"ETag": None, "Last-Modified": LAST_MODIFIED})
    assert headers == {"If-Modified-Since": LAST_MODIFIED}


# --- metadata files -------------------------------------------------------------------------


def test_get_metadata_from_json_missing_file(tmp_path):
    assert download.get_metadata_from_json(tmp_path / "nope.json") == {}


def test_metadata_round_trip(tmp_path):
    path = tmp_path / "data.json"
    metadata = {"ETag": '"abc"', "Last-Modified": LAST_MODIFIED, "Url": URL}

    download.write_new_metadata(path, metadata)

    assert download.get_metadata_from_json(path) == metadata


def test_bundle_metadata_from_response():
    response = httpx.Response(200, headers={"ETag": '"abc"', "Last-Modified": LAST_MODIFIED})

    assert download.bundle_metadata_from_response(response) == {
        "ETag": '"abc"',
        "Last-Modified": LAST_MODIFIED,
    }


# --- write_new_zip --------------------------------------------------------------------------


def test_write_new_zip_writes_bytes_and_returns_metadata(tmp_path):
    zip_path = tmp_path / "data.zip"
    response = httpx.Response(200, content=b"zip-bytes", headers={"ETag": '"abc"'})

    metadata = download.write_new_zip(response, zip_path)

    assert zip_path.read_bytes() == b"zip-bytes"
    assert metadata["ETag"] == '"abc"'


# --- update_local_zip, against a fake server ------------------------------------------------


class FakeServer:
    """Pretends to be the download server and records the requests it receives."""

    def __init__(self) -> None:
        self.content = b"zip-v1"
        self.etag = '"v1"'
        self.error_status: int | None = None
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.error_status is not None:
            return httpx.Response(self.error_status)
        if request.headers.get("If-None-Match") == self.etag:
            return httpx.Response(304)
        return httpx.Response(
            200,
            content=self.content,
            headers={"ETag": self.etag, "Last-Modified": LAST_MODIFIED},
        )


@pytest.fixture
def server(monkeypatch):
    fake = FakeServer()

    def fake_stream(method, url, **kwargs):
        client = httpx.Client(transport=httpx.MockTransport(fake.handler))
        return client.stream(method, url, **kwargs)

    monkeypatch.setattr(download.httpx, "stream", fake_stream)
    return fake


def test_first_download_writes_zip_and_metadata(server, tmp_path):
    zip_path = tmp_path / "data.zip"

    download.update_local_zip(URL, zip_path)

    assert zip_path.read_bytes() == b"zip-v1"
    saved = json.loads((tmp_path / "data.json").read_text())
    assert saved == {"ETag": '"v1"', "Last-Modified": LAST_MODIFIED, "Url": URL}
    # nothing local yet, so the request shouldn't have been conditional
    assert "If-None-Match" not in server.requests[0].headers


def test_second_run_sends_conditional_headers_and_keeps_zip(server, tmp_path):
    zip_path = tmp_path / "data.zip"
    download.update_local_zip(URL, zip_path)

    server.content = b"should-not-be-downloaded"  # the server would only send this on a 200
    download.update_local_zip(URL, zip_path)

    assert server.requests[1].headers["If-None-Match"] == '"v1"'
    assert zip_path.read_bytes() == b"zip-v1"


def test_new_upstream_version_replaces_zip_and_metadata(server, tmp_path):
    zip_path = tmp_path / "data.zip"
    download.update_local_zip(URL, zip_path)

    server.content = b"zip-v2"
    server.etag = '"v2"'
    download.update_local_zip(URL, zip_path)

    assert zip_path.read_bytes() == b"zip-v2"
    assert json.loads((tmp_path / "data.json").read_text())["ETag"] == '"v2"'


def test_server_error_raises_and_writes_nothing(server, tmp_path):
    zip_path = tmp_path / "data.zip"
    server.error_status = 500

    with pytest.raises(httpx.HTTPStatusError):
        download.update_local_zip(URL, zip_path)

    assert not zip_path.exists()
    assert not (tmp_path / "data.json").exists()


def test_redownloads_if_zip_missing_but_metadata_exists(server, tmp_path):
    zip_path = tmp_path / "data.zip"
    download.update_local_zip(URL, zip_path)
    zip_path.unlink()

    download.update_local_zip(URL, zip_path)

    assert zip_path.read_bytes() == b"zip-v1"
