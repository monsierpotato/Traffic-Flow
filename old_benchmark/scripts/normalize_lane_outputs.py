import argparse
import json
from pathlib import Path


def normalize_record(record, method=None, device=None):
    if method:
        record["method"] = method

    runtime = record.setdefault("runtime", {})
    total_ms = float(runtime.get("total_ms") or 0.0)
    if total_ms > 0 and not runtime.get("fps"):
        runtime["fps"] = 1000.0 / total_ms

    if device:
        meta = record.setdefault("meta", {})
        meta["device"] = device

    return record


def merge_jsonl(inputs, output, method=None, device=None):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    with output.open("w", encoding="utf-8") as fout:
        for input_path in inputs:
            input_path = Path(input_path)
            with input_path.open("r", encoding="utf-8") as fin:
                for line in fin:
                    if not line.strip():
                        continue
                    record = normalize_record(json.loads(line), method=method, device=device)
                    fout.write(json.dumps(record, ensure_ascii=False) + "\n")
                    total += 1

    print(f"Wrote {total} records to {output}")


def main():
    parser = argparse.ArgumentParser(description="Merge and normalize lane-output JSONL files.")
    parser.add_argument("--input", nargs="+", required=True, help="Input JSONL files.")
    parser.add_argument("--output", required=True, help="Output JSONL file.")
    parser.add_argument("--method", default=None, help="Optional method name override.")
    parser.add_argument("--device", default=None, help="Optional device metadata.")
    args = parser.parse_args()

    merge_jsonl(args.input, args.output, method=args.method, device=args.device)


if __name__ == "__main__":
    main()
