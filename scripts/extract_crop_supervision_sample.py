from __future__ import annotations

import argparse
from pathlib import Path

import tables


def extract_sample(source: Path, sample_index: int, output: Path) -> None:
    if sample_index < 0:
        raise ValueError("sample_index must be greater than or equal to 0")
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source}")

    output.parent.mkdir(parents=True, exist_ok=True)

    with tables.open_file(str(source), mode="r") as src:
        sample_count = int(src.root.data.shape[0])
        if sample_index >= sample_count:
            raise IndexError(f"sample_index {sample_index} is out of range. Available: 0-{sample_count - 1}")

        data = src.root.data[sample_index : sample_index + 1]
        truth = src.root.truth[sample_index : sample_index + 1]

    filters = tables.Filters(complevel=5, complib="blosc")
    with tables.open_file(str(output), mode="w") as dst:
        dst.create_carray("/", "data", obj=data, filters=filters)
        dst.create_carray("/", "truth", obj=truth, filters=filters)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract one CropSupervision sample into a small HDF5 file.")
    parser.add_argument("--source", required=True, type=Path, help="Path to Site*_train.hdf5")
    parser.add_argument("--sample-index", required=True, type=int, help="Sample index to extract, starting from 0")
    parser.add_argument("--output", required=True, type=Path, help="Output HDF5 path")
    args = parser.parse_args()

    extract_sample(args.source, args.sample_index, args.output)
    print(f"Saved: {args.output}")
    print(f"Size: {args.output.stat().st_size / (1024 * 1024):.2f} MB")


if __name__ == "__main__":
    main()
