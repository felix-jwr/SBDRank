from pathlib import Path

from sbdrank.ingest.download import update_local_zip

URL = "https://openpowerlifting.gitlab.io/opl-csv/files/openpowerlifting-latest.zip"
DATA_DEST = Path("data/raw/openpowerlifting-latest.zip")

update_local_zip(url=URL, local_zip_path=DATA_DEST)
