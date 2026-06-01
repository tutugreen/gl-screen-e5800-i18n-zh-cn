# -*- coding: utf-8 -*-
"""Build OpenWrt ipk from overlay/ (only /etc/gl_screen/language)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse
import io
import tarfile
import time
from datetime import datetime, timezone
from repo_paths import DEPENDS_GL_SCREEN_SDK, DIST_DIR, OVERLAY_DIR, PACKAGE_SCRIPTS_DIR

AR_MAGIC = b"!<arch>\n"

ALLOWED_PREFIXES = (
    "etc/gl_screen/language/text/",
    "etc/gl_screen/language/ttf/",
)

DEFAULT_PACKAGE = "gl-screen-e5800-i18n-zh-cn"
DEFAULT_MAINTAINER = "tutugreen <https://tutu.green>"
DEFAULT_HOMEPAGE = "https://github.com/tutugreen/gl-screen-e5800-i18n-zh-cn"
DEFAULT_DESCRIPTION = (
    "GL-E5800 screen Chinese i18n (lang + TTF).\n"
    " Author: tutugreen — https://tutu.green\n"
    " Only overlays /etc/gl_screen/language; does not touch other gl_screen files.\n"
    " Backs up text/default before install; opkg remove restores English from backup.\n"
    " Runs /etc/init.d/gl_screen restart after install/remove.\n"
    f" Requires: {DEPENDS_GL_SCREEN_SDK}."
)


def default_version() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")


def format_description_block(description: str) -> str:
    lines = [ln.rstrip() for ln in description.strip().splitlines()]
    if not lines:
        return "Description:\n"
    block = f"Description: {lines[0]}\n"
    for line in lines[1:]:
        block += f" {line}\n"
    return block


def iter_payload_files(overlay_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(overlay_root.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        rel = path.relative_to(overlay_root).as_posix()
        if not any(rel.startswith(p) for p in ALLOWED_PREFIXES):
            raise SystemExit(f"Refusing to pack outside language/: {rel}")
        files.append(path)
    if not files:
        raise SystemExit(f"No payload files under {overlay_root}")
    return files


def read_script_bytes(path: Path) -> bytes:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if not text.endswith("\n"):
        text += "\n"
    return text.encode("utf-8")


def tar_gz_from_files(overlay_root: Path, files: list[Path]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.GNU_FORMAT) as tar:
        for path in files:
            rel = path.relative_to(overlay_root).as_posix()
            arcname = f"./{rel}"
            info = tar.gettarinfo(name=str(path), arcname=arcname)
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            info.mode = 0o644
            with path.open("rb") as fh:
                tar.addfile(info, fh)
    return buf.getvalue()


def tar_gz_control(control_text: str, script_files: list[Path] | None = None) -> bytes:
    buf = io.BytesIO()
    ts = int(time.time())
    with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.GNU_FORMAT) as tar:
        data = control_text.encode("utf-8")
        info = tarfile.TarInfo(name="./control")
        info.size = len(data)
        info.mode = 0o644
        info.uid = info.gid = 0
        info.uname = info.gname = "root"
        info.mtime = ts
        tar.addfile(info, io.BytesIO(data))

        for script in script_files or []:
            body = read_script_bytes(script)
            info = tarfile.TarInfo(name=f"./{script.name}")
            info.size = len(body)
            info.mode = 0o755
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            info.mtime = ts
            tar.addfile(info, io.BytesIO(body))
    return buf.getvalue()


def collect_control_scripts() -> list[Path]:
    if not PACKAGE_SCRIPTS_DIR.is_dir():
        return []
    order = ("preinst", "postinst", "prerm", "postrm")
    found = {
        p.name: p
        for p in PACKAGE_SCRIPTS_DIR.iterdir()
        if p.is_file() and p.suffix == "" and not p.name.startswith(".")
    }
    scripts: list[Path] = []
    for name in order:
        if name in found:
            scripts.append(found.pop(name))
    scripts.extend(sorted(found.values(), key=lambda p: p.name))
    return scripts


def _ar_field(value: str | bytes, width: int) -> bytes:
    raw = value.encode("ascii") if isinstance(value, str) else value
    if len(raw) > width:
        raise ValueError(f"ar field too long ({len(raw)} > {width}): {value!r}")
    return raw + b" " * (width - len(raw))


def ar_member(name: str, data: bytes) -> bytes:
    if len(name) > 16:
        raise ValueError(f"ar member name too long: {name}")
    header = (
        _ar_field(name, 16)
        + _ar_field(str(int(time.time())), 12)
        + _ar_field("0", 6)
        + _ar_field("0", 6)
        + _ar_field("100644", 8)
        + _ar_field(str(len(data)), 10)
        + b"`\n"
    )
    out = header + data
    if len(out) % 2:
        out += b"\n"
    return out


def verify_ipk(ipk_path: Path) -> None:
    data = ipk_path.read_bytes()
    if not data.startswith(AR_MAGIC):
        raise SystemExit(f"Invalid IPK: missing ar magic {AR_MAGIC!r}")
    off = len(AR_MAGIC)
    names: list[str] = []
    while off + 60 <= len(data):
        hdr = data[off : off + 60]
        name = hdr[:16].decode("ascii", errors="replace").rstrip()
        size = int(hdr[48:58].decode().strip())
        off += 60 + size + (size % 2)
        names.append(name)
    if names[:3] != ["debian-binary", "control.tar.gz", "data.tar.gz"]:
        raise SystemExit(f"Unexpected IPK members: {names}")


def build_ipk(
    overlay_root: Path,
    out_dir: Path,
    package: str,
    version: str,
    architecture: str,
    maintainer: str,
    homepage: str,
    description: str,
    depends: str,
) -> Path:
    files = iter_payload_files(overlay_root)
    data_tar = tar_gz_from_files(overlay_root, files)
    installed_kb = (sum(f.stat().st_size for f in files) + 1023) // 1024

    control = (
        f"Package: {package}\n"
        f"Version: {version}\n"
        f"Architecture: {architecture}\n"
        f"Depends: {depends}\n"
        f"Maintainer: {maintainer}\n"
        f"Homepage: {homepage}\n"
        f"Section: misc\n"
        f"Priority: optional\n"
        f"Installed-Size: {installed_kb}\n"
        f"{format_description_block(description)}"
    )
    script_files = collect_control_scripts()
    control_tar = tar_gz_control(control, script_files)

    ipk_name = f"{package}_{version}_{architecture}.ipk"
    out_dir.mkdir(parents=True, exist_ok=True)
    ipk_path = out_dir / ipk_name

    body = (
        AR_MAGIC
        + ar_member("debian-binary", b"2.0\n")
        + ar_member("control.tar.gz", control_tar)
        + ar_member("data.tar.gz", data_tar)
    )
    ipk_path.write_bytes(body)
    verify_ipk(ipk_path)

    print(f"IPK: {ipk_path}")
    print(f"  version: {version}")
    print(f"  depends: {depends}")
    print(f"  control scripts: {[p.name for p in script_files] or '(none)'}")
    print(f"  files: {len(files)}, installed ~{installed_kb} KiB")
    for f in files:
        rel = f.relative_to(overlay_root).as_posix()
        print(f"    ./{rel} ({f.stat().st_size} bytes)")
    return ipk_path


def main() -> None:
    p = argparse.ArgumentParser(description="Build OpenWrt ipk from overlay/")
    p.add_argument("--overlay", type=Path, default=OVERLAY_DIR)
    p.add_argument("--out-dir", type=Path, default=DIST_DIR)
    p.add_argument("--package", default=DEFAULT_PACKAGE)
    p.add_argument(
        "--version",
        default=None,
        help="UTC version, e.g. 2026-06-01-23-11-17 (default: now)",
    )
    p.add_argument("--arch", default="all")
    p.add_argument("--maintainer", default=DEFAULT_MAINTAINER)
    p.add_argument("--homepage", default=DEFAULT_HOMEPAGE)
    p.add_argument("--description", default=DEFAULT_DESCRIPTION)
    p.add_argument("--depends", default=DEPENDS_GL_SCREEN_SDK)
    args = p.parse_args()

    version = args.version or default_version()
    if not args.overlay.is_dir():
        raise SystemExit(f"Missing overlay dir: {args.overlay}")

    build_ipk(
        args.overlay,
        args.out_dir,
        args.package,
        version,
        args.arch,
        args.maintainer,
        args.homepage,
        args.description,
        args.depends,
    )


if __name__ == "__main__":
    main()
