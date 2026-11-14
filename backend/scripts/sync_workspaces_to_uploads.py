#!/usr/bin/env python3
from __future__ import annotations

import shutil
import time
from pathlib import Path

SRC = Path('/app/data/workspaces')
DST = Path('/app/data/uploads/workspaces')
INTERVAL_SECONDS = 5


def sync_once() -> None:
    if not SRC.exists():
        return
    for src_file in SRC.rglob('*'):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(SRC)
        dst_file = DST / rel
        try:
            src_stat = src_file.stat()
            if dst_file.exists():
                dst_stat = dst_file.stat()
                if dst_stat.st_size == src_stat.st_size and int(dst_stat.st_mtime) >= int(src_stat.st_mtime):
                    continue
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = dst_file.with_suffix(dst_file.suffix + '.tmp')
            shutil.copy2(src_file, tmp_file)
            tmp_file.replace(dst_file)
        except FileNotFoundError:
            continue
        except Exception as exc:
            print(f'[workspace-sync] failed {src_file}: {exc}', flush=True)


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    while True:
        sync_once()
        time.sleep(INTERVAL_SECONDS)


if __name__ == '__main__':
    main()
