"""evidence 异地备份工具（Q-L13-14①②义务的机械承载；P1 起每次门退出执行）。

子命令：
- backup   打包 evidence/ → tar.gz + 整体 sha256 sidecar（推送远端由调用方 scp，
           或 --push emb@host 直推）
- drill    恢复演练（Q-L13-14② 机械判据）：从远端副本取 tar → 还原临时目录 →
           **逐文件** sha256 与本地 evidence/ 比对 → N/N 一致才算过（整体 digest
           ≠ 逐件判据——REV-0025 R4 口径）

确定性：文件清单排序遍历；digest = sha256(文件字节)。退出码：0=过，1=不过。
"""
from __future__ import annotations

import argparse
import hashlib
import io
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_EVIDENCE = _REPO / "evidence"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_digest(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _evidence_digests() -> dict[str, str]:
    """{相对路径: sha256}（排序遍历——确定性）。"""
    out: dict[str, str] = {}
    for path in sorted(_EVIDENCE.rglob("*")):
        if path.is_file():
            out[path.relative_to(_EVIDENCE).as_posix()] = _file_digest(path)
    return out


def cmd_backup(push_target: str | None) -> int:
    if not _EVIDENCE.is_dir():
        print("BACKUP_FAIL: evidence/ 不存在（fresh clone？）", file=sys.stderr)
        return 1
    tar_path = Path(tempfile.gettempdir()) / "galatea-evidence.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for rel in sorted(p.relative_to(_REPO).as_posix() for p in _EVIDENCE.rglob("*") if p.is_file()):
            tar.add(_REPO / rel, arcname=rel)
    blob = tar_path.read_bytes()
    whole = _sha256_bytes(blob)
    per_file = _evidence_digests()
    sidecar = tar_path.with_suffix(".sha256")
    sidecar.write_text(
        f"whole={whole}\nfiles={len(per_file)}\n" +
        "".join(f"{digest}  {name}\n" for name, digest in sorted(per_file.items())),
        encoding="utf-8",
    )
    print(f"backup_tar={tar_path}")
    print(f"whole_sha256={whole}")
    print(f"files={len(per_file)}")
    print(f"sidecar={sidecar}")
    if push_target:
        subprocess.run(["scp", "-q", str(tar_path), f"{push_target}:/tmp/"], check=True)
        subprocess.run(["scp", "-q", str(sidecar), f"{push_target}:/tmp/"], check=True)
        print(f"pushed -> {push_target}:/tmp/")
    return 0


def cmd_drill(remote_host: str, remote_tar: str = "/tmp/galatea-evidence.tar.gz") -> int:
    """恢复演练：远端副本 → 临时目录还原 → 逐文件 digest 一致（Q-L13-14②）。"""
    with tempfile.TemporaryDirectory(prefix="evidence_drill_") as tmp:
        tmp_dir = Path(tmp)
        local_tar = tmp_dir / "galatea-evidence.tar.gz"
        subprocess.run(["scp", "-q", f"{remote_host}:{remote_tar}", str(local_tar)], check=True)
        extract_dir = tmp_dir / "restored"
        extract_dir.mkdir()
        with tarfile.open(local_tar, "r:gz") as tar:
            tar.extractall(extract_dir, filter="data")
        local_digests = _evidence_digests()
        restored_root = extract_dir / "evidence"
        if not restored_root.is_dir():
            print("DRILL_FAIL: 还原产物无 evidence/ 根", file=sys.stderr)
            return 1
        restored: dict[str, str] = {}
        for path in sorted(restored_root.rglob("*")):
            if path.is_file():
                restored[path.relative_to(restored_root).as_posix()] = _file_digest(path)
        missing = sorted(set(local_digests) - set(restored))
        extra = sorted(set(restored) - set(local_digests))
        mismatch = sorted(k for k in set(local_digests) & set(restored)
                          if local_digests[k] != restored[k])
        print(f"local_files={len(local_digests)} restored_files={len(restored)}")
        print(f"missing={len(missing)} extra={len(extra)} mismatched={len(mismatch)}")
        for name in (missing + extra + mismatch)[:10]:
            print(f"  diff: {name}")
        passed = not missing and not extra and not mismatch
        print(f"drill_per_file_match={passed}")
        print(f"drill_verdict={'PASS' if passed else 'FAIL'}")
        return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="evidence 异地备份/恢复演练（Q-L13-14）")
    sub = parser.add_subparsers(dest="command", required=True)
    backup = sub.add_parser("backup", help="打包 + 整体 digest sidecar（可选直推远端）")
    backup.add_argument("--push", help="scp 目标（如 emb@192.168.2.91）", default=None)
    drill = sub.add_parser("drill", help="恢复演练：逐文件 digest 一致（Q-L13-14②）")
    drill.add_argument("--remote", default="emb@192.168.2.91")
    drill.add_argument("--remote-tar", default="/tmp/galatea-evidence.tar.gz")
    args = parser.parse_args(argv)
    if args.command == "backup":
        return cmd_backup(args.push)
    return cmd_drill(args.remote, args.remote_tar)


if __name__ == "__main__":
    sys.exit(main())
