import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()  

try:
    import psycopg
except ImportError as exc:
    raise ImportError("psycopg is required. Install it with `pip install psycopg[binary]`.") from exc


@dataclass
class PostgresConfig:
    host: str = os.getenv("PGHOST", "localhost")
    port: int = int(os.getenv("PGPORT", "5432"))
    dbname: str = os.getenv("PGDATABASE", "educacao_dw")
    user: str = os.getenv("PGUSER", "postgres")
    password: str = os.getenv("PGPASSWORD", "")

    def to_dsn(self) -> str:
        parts = [f"host={self.host}", f"port={self.port}", f"dbname={self.dbname}", f"user={self.user}"]
        if self.password:
            parts.append(f"password={self.password}")
        return " ".join(parts)


def get_connection():
    config = PostgresConfig()
    return psycopg.connect(config.to_dsn())
