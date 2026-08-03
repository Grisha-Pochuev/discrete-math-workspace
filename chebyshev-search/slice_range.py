#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--input', required=True)
parser.add_argument('--output', required=True)
parser.add_argument('--fetch-start', required=True, type=int)
parser.add_argument('--logical-start', required=True, type=int)
parser.add_argument('--logical-end', required=True, type=int)
parser.add_argument('--source-size', required=True, type=int)
parser.add_argument('--meta', required=True)
args = parser.parse_args()

if not (0 <= args.fetch_start <= args.logical_start < args.logical_end <= args.source_size):
    raise SystemExit('invalid byte interval')

raw_size = Path(args.input).stat().st_size
absolute = args.fetch_start
count = 0
first_n = None
last_n = None
first_offset = None
last_offset = None

with open(args.input, 'rb') as src, open(args.output, 'wb') as dst:
    if args.fetch_start > 0:
        discarded = src.readline()
        absolute += len(discarded)

    while True:
        line_start = absolute
        line = src.readline()
        if not line:
            break
        absolute += len(line)
        if line_start < args.logical_start:
            continue
        if line_start >= args.logical_end:
            break
        if not line.endswith(b'\n') and absolute < args.source_size:
            raise SystemExit('overlap ended inside an assigned line')
        stripped = line.strip()
        if not stripped:
            raise SystemExit(f'blank assigned line at byte {line_start}')
        first_field = stripped.split(None, 1)[0]
        if not first_field.isdigit():
            raise SystemExit(f'non-numeric first field at byte {line_start}')
        n = first_field.decode('ascii')
        dst.write(line)
        count += 1
        if first_n is None:
            first_n = n
            first_offset = line_start
        last_n = n
        last_offset = line_start

meta = {
    'fetch_start': args.fetch_start,
    'logical_start': args.logical_start,
    'logical_end': args.logical_end,
    'source_size': args.source_size,
    'raw_bytes': raw_size,
    'assigned_lines': count,
    'assigned_bytes': Path(args.output).stat().st_size,
    'first_n': first_n,
    'last_n': last_n,
    'first_line_offset': first_offset,
    'last_line_offset': last_offset,
}
Path(args.meta).write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
print(json.dumps(meta, indent=2))
if count == 0:
    raise SystemExit('empty assigned range')
