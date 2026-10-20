"""Check that every expected raw file exists and print its size, row count and SHA-256 checksum."""
import hashlib
import sys

from config import RAW_DIR, RAW_FILES


def sha256(path, chunk_size=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    missing = [name for name in RAW_FILES.values() if not (RAW_DIR / name).exists()]
    if missing:
        print(f"Missing files in {RAW_DIR}:")
        for name in missing:
            print(f"  - {name}")
        sys.exit(1)

    print("| File | Size (bytes) | Data rows | SHA-256 |")
    print("|---|---|---|---|")
    for name in RAW_FILES.values():
        path = RAW_DIR / name
        with open(path, "rb") as f:
            rows = sum(1 for _ in f) - 1  # minus header; embedded newlines in review text may inflate this
        print(f"| {name} | {path.stat().st_size} | {rows} | {sha256(path)} |")


if __name__ == "__main__":
    main()
