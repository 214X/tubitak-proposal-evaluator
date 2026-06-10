from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"


def is_windows() -> bool:
    return os.name == "nt"


def python_launcher() -> str:
    if is_windows():
        return "py"
    return shutil.which("python3") or sys.executable


def venv_python() -> Path:
    if is_windows():
        return BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    return BACKEND_DIR / ".venv" / "bin" / "python"


def npm_command() -> str:
    return "npm.cmd" if is_windows() else "npm"


def ensure_command_exists(command: str) -> None:
    if shutil.which(command):
        return
    raise SystemExit(f"Required command not found: {command}")


def run_command(command: list[str], cwd: Path) -> None:
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def ensure_backend_venv() -> None:
    if venv_python().exists():
        return
    raise SystemExit(
        "Backend virtual environment not found. Run 'make setup' first.",
    )


def ensure_frontend_install() -> None:
    if (FRONTEND_DIR / "node_modules").exists():
        return
    raise SystemExit(
        "Frontend dependencies not found. Run 'make setup' first.",
    )


def setup() -> None:
    ensure_command_exists(npm_command())

    if not venv_python().exists():
        if is_windows():
            run_command([python_launcher(), "-3", "-m", "venv", ".venv"], BACKEND_DIR)
        else:
            run_command([python_launcher(), "-m", "venv", ".venv"], BACKEND_DIR)

    run_command(
        [str(venv_python()), "-m", "pip", "install", "-r", "requirements.txt"],
        BACKEND_DIR,
    )
    run_command([npm_command(), "install"], FRONTEND_DIR)


def warmup() -> None:
    ensure_backend_venv()
    run_command(
        [
            str(venv_python()),
            "-c",
            (
                "from app.services.embedding.provider import get_embedding_provider; "
                "provider = get_embedding_provider(); "
                "print(provider.model_name, provider.dimensions)"
            ),
        ],
        BACKEND_DIR,
    )


def backend() -> None:
    ensure_backend_venv()
    run_command(
        [
            str(venv_python()),
            "-m",
            "uvicorn",
            "app.main:app",
            "--reload",
        ],
        BACKEND_DIR,
    )


def frontend() -> None:
    ensure_frontend_install()
    run_command([npm_command(), "run", "dev"], FRONTEND_DIR)


def run_both() -> None:
    ensure_backend_venv()
    ensure_frontend_install()
    backend_process = subprocess.Popen(
        [str(venv_python()), "-m", "uvicorn", "app.main:app", "--reload"],
        cwd=BACKEND_DIR,
    )
    frontend_process = subprocess.Popen(
        [npm_command(), "run", "dev"],
        cwd=FRONTEND_DIR,
    )

    processes = [backend_process, frontend_process]

    try:
        while True:
            for process in processes:
                return_code = process.poll()
                if return_code is not None:
                    raise SystemExit(return_code)
            time.sleep(0.5)
    except KeyboardInterrupt:
        terminate_processes(processes)
    except SystemExit as exc:
        terminate_processes(processes)
        raise exc


def terminate_processes(processes: list[subprocess.Popen[bytes] | subprocess.Popen[str]]) -> None:
    for process in processes:
        if process.poll() is not None:
            continue
        if is_windows():
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.terminate()

    for process in processes:
        if process.poll() is not None:
            continue
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 scripts/run_dev.py [setup|warmup|backend|frontend|run]")

    command = sys.argv[1]

    if command == "setup":
        setup()
        return
    if command == "warmup":
        warmup()
        return
    if command == "backend":
        backend()
        return
    if command == "frontend":
        frontend()
        return
    if command == "run":
        run_both()
        return

    raise SystemExit(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
