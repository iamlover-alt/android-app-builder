"""emulator-run: install an APK on an emulator/device and run instrumented tests via adb."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .process import CommandRunner

PKG_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$")


@dataclass(frozen=True)
class EmulatorResult:
    ok: bool
    package: str
    output: str = ""
    verified_on_emulator: bool = True  # False for fakes: must never be reported as real verification


class EmulatorRunner(Protocol):
    def run(self, apk: Path, package: str) -> EmulatorResult: ...


class EmulatorTool:
    def __init__(self, runner: CommandRunner, workdir: Path, serial: str | None = None, timeout: float = 900):
        self.runner, self.workdir, self.serial, self.timeout = runner, Path(workdir), serial, timeout

    def _adb(self, *args: str):
        base = ["adb", *(["-s", self.serial] if self.serial else [])]
        return self.runner.run([*base, *args], self.workdir, self.timeout)

    def run(self, apk: Path, package: str) -> EmulatorResult:
        if not PKG_RE.match(package):
            raise ValueError(f"invalid package name: {package!r}")
        if not Path(apk).is_file():
            return EmulatorResult(False, package, f"apk not found: {apk}")
        for step in (("install", "-r", str(apk)),
                     ("shell", "am", "instrument", "-w", f"{package}.test/androidx.test.runner.AndroidJUnitRunner")):
            r = self._adb(*step)
            out = r.stdout + r.stderr
            if not r.ok or "FAILURES!!!" in out or "INSTRUMENTATION_FAILED" in out:
                return EmulatorResult(False, package, out[-4000:])
        return EmulatorResult(True, package, out[-4000:])


@dataclass
class FakeEmulator:
    passes: bool = True
    calls: list[tuple[str, str]] = field(default_factory=list)

    def run(self, apk: Path, package: str) -> EmulatorResult:
        self.calls.append((str(apk), package))
        return EmulatorResult(self.passes, package, "fake emulator", verified_on_emulator=False)
