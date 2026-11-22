import os
import sys

import psycopg
from dotenv import load_dotenv


def get_db_config() -> dict[str, object]:
    return {
        "host": os.environ.get("POSTGRES_HOST", "localhost"),
        "port": int(os.environ["POSTGRES_PORT"]),
        "dbname": os.environ["POSTGRES_DB"],
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
    }


if __name__ == "__main__":
    load_dotenv()

    try:
        with psycopg.connect(**get_db_config()) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                ver = cur.fetchone()
                print(ver[0])

    except psycopg.OperationalError as e:
        print(
            "Encountered an error whilst accessing the database.\n"
            + "(Did you check the port? Is the container up?)\n"
            + f"{e}",
            file=sys.stderr,
        )
        sys.exit(1)
