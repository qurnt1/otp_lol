"""Build both PyInstaller shapes and measure their packaged process startup."""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = ROOT / "build-benchmark"
SAMPLES = 5


def build(mode: str) -> Path:
    command = [sys.executable, "create_exe.py", "--mode", mode, "--no-shortcut"]
    subprocess.run(command, cwd=ROOT, check=True)
    if mode == "onefile":
        target = BENCHMARK_DIR / "OTP LOL-onefile.exe"
        shutil.copy2(ROOT / "OTP LOL.exe", target)
        return target
    target = BENCHMARK_DIR / "OTP LOL-onedir"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(ROOT / "OTP LOL", target)
    return target / "OTP LOL.exe"


def measure(executable: Path) -> list[float]:
    durations = []
    for _ in range(SAMPLES):
        started = time.perf_counter()
        subprocess.run([str(executable), "--self-test"], cwd=executable.parent, check=True)
        durations.append((time.perf_counter() - started) * 1000)
    return durations


def main() -> int:
    BENCHMARK_DIR.mkdir(exist_ok=True)
    results = {}
    for mode in ("onefile", "onedir"):
        executable = build(mode)
        results[mode] = measure(executable)
    report = BENCHMARK_DIR / "startup-results.txt"
    lines = ["OTP LOL startup benchmark, 5 process samples per mode", "Note: Windows process samples approximate cold/warm filesystem behavior; they are not a reboot-level cold boot."]
    for mode, values in results.items():
        lines.append(f"{mode}: " + ", ".join(f"{value:.0f} ms" for value in values) + f" | avg={sum(values) / len(values):.0f} ms")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
