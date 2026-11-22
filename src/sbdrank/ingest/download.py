import json
from pathlib import Path

import httpx


def update_local_zip(url: str, local_zip_path: Path) -> None:
    local_metadata_path = local_zip_path.with_suffix(".json")
    local_metadata = get_metadata_from_json(local_metadata_path)
    local_metadata = usable_metadata(local_metadata, local_zip_path)
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
        if local_metadata.get(metadata_key) 
    }

    return headers


def get_metadata_from_json(local_metadata_path: Path) -> dict:
    return json.loads(local_metadata_path.read_text()) if local_metadata_path.exists() else {}


def usable_metadata(local_metadata: dict, local_zip_path: Path) -> dict:
    if local_zip_path.exists():
        return local_metadata
    else:
        return {}


def write_new_zip(response: httpx.Response, local_zip_path: Path) -> dict:
    temp_path = local_zip_path.with_name(local_zip_path.name + ".part")

    with temp_path.open("wb") as f:
        for chunk in response.iter_bytes():
            f.write(chunk)

    Path.replace(temp_path, local_zip_path)
    return bundle_metadata_from_response(response)


def bundle_metadata_from_response(response: httpx.Response) -> dict:
    metadata = {}
    response_keys = ["ETag", "Last-Modified"]

    for key in response_keys:
        if response_value := response.headers.get(key):
            metadata[key] = response_value

    return metadata 


def write_new_metadata(metadata_path: Path, new_metadata: dict) -> None:
    metadata_path.write_text(json.dumps(new_metadata))
