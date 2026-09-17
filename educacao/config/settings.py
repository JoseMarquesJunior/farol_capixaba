from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data"
RAW_DIR = DATA_ROOT / "raw"
EXTRACTED_DIR = DATA_ROOT / "extracted"
INVENTORY_DIR = DATA_ROOT / "inventory"
PARQUET_DIR = DATA_ROOT / "parquet"

METADATA_DIR = ROOT / "metadata"
DATABASE_DIR = ROOT / "database"

DEFAULT_ENCODING = "latin1"
DEFAULT_SEPARATOR = ";"
DEFAULT_SAMPLE_ROWS = 500
