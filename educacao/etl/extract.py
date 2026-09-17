from pathlib import Path
from zipfile import ZipFile
from typing import Iterable


def extract_zip(zip_path: Path, target_dir: Path) -> list[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(zip_path, "r") as archive:
        archive.extractall(target_dir)
    extracted_paths = [target_dir / name for name in archive.namelist() if not name.endswith("/")]
    return extracted_paths


def extract_year_data(raw_dir: Path, year: int, extracted_dir: Path) -> list[Path]:
    year_dir = extracted_dir / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)

    found_zips = list(raw_dir.glob(f"*{year}*.zip"))
    if not found_zips:
        raise FileNotFoundError(f"Nenhum ZIP encontrado para o ano {year} em {raw_dir}")

    extracted_files: list[Path] = []
    for zip_path in found_zips:
        extracted_files.extend(extract_zip(zip_path, year_dir))
    return extracted_files
