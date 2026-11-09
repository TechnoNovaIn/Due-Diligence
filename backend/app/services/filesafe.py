"""Safe file handling: path containment, signature checks, size limits, scanning.

Every document the system touches arrives from a watched folder, so it is
treated as untrusted input: paths are resolved and confined, magic bytes are
checked against the extension, and nothing is ever executed.
"""
from __future__ import annotations

import hashlib
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

SUPPORTED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".rtf": "application/rtf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
}

#: Leading bytes that must be present for the declared extension.
_SIGNATURES = {
    ".pdf": [b"%PDF-"],
    ".docx": [b"PK\x03\x04"],
    ".doc": [b"\xd0\xcf\x11\xe0", b"PK\x03\x04", b"{\\rtf"],
    ".rtf": [b"{\\rtf"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".tif": [b"II*\x00", b"MM\x00*"],
    ".tiff": [b"II*\x00", b"MM\x00*"],
    ".bmp": [b"BM"],
    ".webp": [b"RIFF"],
}

#: "README.txt" is the instruction file this system writes into every case folder;
#: it is deliberately not treated as a property document.
IGNORED_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini", ".localized", "README.txt"}
IGNORED_PREFIXES = ("~$", "._", ".~lock.")
IGNORED_SUFFIXES = (".crdownload", ".part", ".partial", ".tmp", ".download", ".sb-")


class UnsafePathError(ValueError):
    """Raised when a path escapes every configured watch root."""


@dataclass
class FileCheck:
    ok: bool
    reason: Optional[str] = None
    mime: Optional[str] = None
    issues: List[str] = field(default_factory=list)
    quarantine: bool = False


def is_ignored(path: Path) -> bool:
    name = path.name
    if name in IGNORED_NAMES or name.startswith(IGNORED_PREFIXES):
        return True
    if any(name.endswith(sfx) for sfx in IGNORED_SUFFIXES):
        return True
    # Hidden files and anything inside a dot-directory.
    if name.startswith("."):
        return True
    return any(part.startswith(".") for part in path.parts[:-1])


def resolve_within(path, roots) -> Path:
    """Resolve ``path`` and assert that it lives under one of ``roots``.

    Symlinks are resolved first, so a symlink pointing outside a watch root is
    rejected rather than followed.
    """
    resolved = Path(os.path.expanduser(str(path))).resolve()
    for root in roots:
        root_resolved = Path(os.path.expanduser(str(root))).resolve()
        try:
            resolved.relative_to(root_resolved)
            return resolved
        except ValueError:
            continue
    raise UnsafePathError("Path {} is outside the permitted roots".format(resolved))


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


def check_file(path: Path, max_mb: int = 0, scan_command: Optional[str] = None) -> FileCheck:
    """Validate type, size and signature, and optionally run a malware scanner.

    ``max_mb`` of 0 (the default) means there is no size limit.
    """
    issues: List[str] = []
    if not path.exists() or not path.is_file():
        return FileCheck(False, "File does not exist or is not a regular file")
    if path.is_symlink():
        return FileCheck(False, "Symbolic links are not processed", quarantine=True)

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return FileCheck(False, "Unsupported file type '{}'".format(ext or "(none)"))

    size = path.stat().st_size
    if size == 0:
        return FileCheck(False, "File is empty")
    if max_mb and max_mb > 0 and size > max_mb * 1024 * 1024:
        return FileCheck(
            False,
            "File is {:.1f} MB, over the configured limit of {} MB. Raise MAX_FILE_MB, or set "
            "it to 0 for no limit.".format(size / 1024 / 1024, max_mb),
        )

    with open(path, "rb") as fh:
        head = fh.read(16)
    expected = _SIGNATURES.get(ext)
    if expected and not any(head.startswith(sig) for sig in expected):
        if ext in (".txt", ".md"):
            pass
        else:
            return FileCheck(
                False,
                "File contents do not match the '{}' extension (possible corruption or mislabelled file)".format(ext),
                quarantine=True,
            )

    if scan_command:
        try:
            cmd = shlex.split(scan_command) + [str(path)]
            proc = subprocess.run(cmd, capture_output=True, timeout=120)
            if proc.returncode != 0:
                return FileCheck(
                    False,
                    "Malware scan reported a problem: {}".format(
                        (proc.stdout or proc.stderr).decode("utf-8", "ignore")[:300]
                    ),
                    quarantine=True,
                )
        except FileNotFoundError:
            issues.append("Configured malware scanner was not found; the file was not scanned.")
        except subprocess.TimeoutExpired:
            issues.append("Malware scan timed out; the file was not scanned.")

    return FileCheck(True, None, SUPPORTED_EXTENSIONS[ext], issues)


def is_settled(path: Path, settle_seconds: float, now: float) -> bool:
    """True when a file has stopped changing (copy/download finished)."""
    try:
        st = path.stat()
    except OSError:
        return False
    return (now - st.st_mtime) >= settle_seconds


def safe_relpath(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return path.name
