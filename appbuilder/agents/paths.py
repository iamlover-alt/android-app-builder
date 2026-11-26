"""Shared path rules for code written by agents (deterministic verifier helpers)."""
from __future__ import annotations

import re
from pathlib import PurePosixPath

# Files an agent may never write: signing material, local config, the Gradle wrapper, VCS data.
FORBIDDEN_NAMES = {"local.properties", "keystore.properties", "gradlew", "gradlew.bat", "gradle-wrapper.jar",
                   "gradle-wrapper.properties", ".env"}
FORBIDDEN_SUFFIXES = (".jks", ".keystore", ".p12", ".pem", ".key", ".json.enc")
SECRET_RE = re.compile(
    r"sk-" r"ant-[A-Za-z0-9_-]+|-----BEGIN [A-Z ]*PRIVATE KEY-----|AIza[0-9A-Za-z_-]{20,}"
    r"|gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|(?i:bearer)\s+[A-Za-z0-9._~+/-]{16,}"
    r"|://[^/\s:@]+:[^/\s@]+@|(?i:(?:password|passwd|secret|token|api[_-]?key|storepass|keypass))\s*[=:]\s*\S{4,}")


def path_errors(path: str) -> list[str]:
    p = PurePosixPath(path)
    if not path or p.is_absolute() or "\\" in path or ".." in p.parts or p.parts[:1] == (".git",):
        return [f"path {path!r} must be a relative path inside the project"]
    if ".git" in p.parts or p.name in FORBIDDEN_NAMES or p.name.endswith(FORBIDDEN_SUFFIXES):
        return [f"path {path!r} is not writable by agents"]
    return []


def module_dir(module_path: str) -> str:
    """':feature:tasks' -> 'feature/tasks'."""
    return module_path.lstrip(":").replace(":", "/")


PATCH_SUFFIXES = (".kt", ".java", ".xml", ".pro")


def patch_path_errors(path: str) -> list[str]:
    """Build Doctor may patch source and resources only. Gradle scripts, version catalogs and
    gradle.properties run code or pin dependencies, so those fixes escalate to a human."""
    errs = path_errors(path)
    if errs:
        return errs
    p = PurePosixPath(path)
    if not (path.endswith(PATCH_SUFFIXES) and ("src" in p.parts or p.name == "proguard-rules.pro")):
        return [f"path {path!r}: Build Doctor may patch only source/resource files under src/ (build files escalate)"]
    return []


def symlink_errors(root, rel: str) -> list[str]:
    """Reject paths that pass through a symlink (existing components only)."""
    from pathlib import Path
    cur = Path(root)
    for part in PurePosixPath(rel).parts:
        cur = cur / part
        if cur.is_symlink():
            return [f"path {rel!r} passes through a symlink"]
    return []
