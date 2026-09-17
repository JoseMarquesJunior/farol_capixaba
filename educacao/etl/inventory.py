import json
from pathlib import Path
from typing import Any


def build_inventory(extracted_dir: Path, inventory_dir: Path) -> list[dict[str, Any]]:
    inventory_dir.mkdir(parents=True, exist_ok=True)
    inventories: list[dict[str, Any]] = []

    for year_dir in sorted(extracted_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        year = int(year_dir.name)
        files = []
        for path in sorted(year_dir.rglob("*")):
            if path.is_file():
                files.append(
                    {
                        "name": path.name,
                        "path": str(path.resolve()),
                        "size": path.stat().st_size,
                        "extension": path.suffix.lstrip(".").lower(),
                    }
                )
        inventory = {"year": year, "files": files}
        inventories.append(inventory)
        inventory_path = inventory_dir / f"{year}.json"
        inventory_path.write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")
    return inventories
