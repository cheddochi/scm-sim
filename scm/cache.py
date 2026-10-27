"""무거운 계산(LP 20개 연도 × 다수 네트워크)의 디스크 캐시. 엔진 코드나 엑셀이 바뀌면 자동 무효화."""
from __future__ import annotations

import hashlib
import pickle
from pathlib import Path

from . import config as C

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
ENGINE_FILES = ["config.py", "data.py", "cost.py", "network.py", "finance.py", "analysis.py"]


def engine_version() -> str:
    h = hashlib.sha1()
    root = Path(__file__).resolve().parent
    for name in ENGINE_FILES:
        h.update((root / name).read_bytes())
    if C.EXCEL_PATH.exists():
        h.update(str(C.EXCEL_PATH.stat().st_mtime).encode())
    return h.hexdigest()[:12]


def memo(name: str, key, fn):
    """key의 repr로 캐시 파일을 찾고, 없으면 fn()을 계산해 저장."""
    digest = hashlib.sha1(f"{engine_version()}|{name}|{key!r}".encode()).hexdigest()[:16]
    path = CACHE_DIR / f"{name}_{digest}.pkl"
    if path.exists():
        try:
            return pickle.loads(path.read_bytes())
        except Exception:
            path.unlink(missing_ok=True)
    value = fn()
    CACHE_DIR.mkdir(exist_ok=True)
    path.write_bytes(pickle.dumps(value))
    return value
