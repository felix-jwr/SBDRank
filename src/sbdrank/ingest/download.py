import json
from pathlib import Path

import httpx


def update_local_zip(url: str, local_zip_path: Path) -> None:
    local_metadata_path = local_zip_path.with_suffix(".json")
    local_metadata = get_metadata_from_json(local_metadata_path)
    headers = update_headers(local_metadata)

    with httpx.stream("GET", url, headers=headers, timeout=60) as response:
        if response.status_code == 304:
            print("Local version is current")
            return
        else:
            response.raise_for_status()
            local_metadata = write_new_zip(response, local_zip_path)
            local_metadata["Url"] = url
            write_new_metadata(local_metadata_path, local_metadata)


def update_headers(local_metadata: dict) -> dict:
    key_map = {"If-None-Match": "ETag", "If-Modified-Since": "Last-Modified"}

    headers = {
        header_key: local_metadata[metadata_key]
        for header_key, metadata_key in key_map.items()
        if metadata_key in local_metadata
    }

    return headers


def get_metadata_from_json(local_metadata_path: Path) -> dict:
    return json.loads(local_metadata_path.read_text()) if local_metadata_path.exists() else {}


def write_new_zip(response, local_zip_path: Path) -> dict:
    with local_zip_path.open("wb") as f:
        for chunk in response.iter_bytes():
            f.write(chunk)

    return bundle_metadata_from_response(response)


def bundle_metadata_from_response(response: httpx.Response) -> dict:
    local_metadata = {}
    local_metadata["ETag"] = response.headers.get("ETag")
    local_metadata["Last-Modified"] = response.headers.get("Last-Modified")

    return local_metadata


def write_new_metadata(metadata_path: Path, new_metadata: dict) -> None:
    metadata_path.write_text(json.dumps(new_metadata))
