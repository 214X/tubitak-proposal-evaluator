from __future__ import annotations

import ast
import os
import shutil
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
DEFAULT_OLLAMA_MODEL_NAME = os.environ.get("OLLAMA_MODEL_NAME", "aya-expanse:8b")


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


def run_command_capture(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        raise SystemExit(stderr or stdout or completed.returncode)
    return completed


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


def verify_backend_import_contract() -> None:
    services_dir = BACKEND_DIR / "app" / "services"
    violating_files: list[str] = []

    for init_path in sorted(services_dir.glob("*/__init__.py")):
        tree = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
        for node in tree.body:
            if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant):
                if isinstance(node.value.value, str):
                    continue
            if isinstance(node, ast.Pass):
                continue
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                continue
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and _is_all_assignment(node):
                continue
            violating_files.append(str(init_path.relative_to(ROOT_DIR)))
            break

    if violating_files:
        raise SystemExit(
            "Service package __init__.py files must stay side-effect free. "
            "Move imports to the concrete module instead:\n- " + "\n- ".join(violating_files)
        )


def verify_backend_import_smoke() -> None:
    run_command(
        [str(venv_python()), "-c", "from app.main import app; print('backend-import-ok')"],
        BACKEND_DIR,
    )


def verify_backend_guards() -> None:
    ensure_backend_venv()
    verify_backend_import_contract()
    verify_backend_import_smoke()


def _is_all_assignment(node: ast.Assign | ast.AnnAssign) -> bool:
    if isinstance(node, ast.Assign):
        return any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)
    target = node.target
    return isinstance(target, ast.Name) and target.id == "__all__"


def clear_frontend_build_cache() -> None:
    next_dir = FRONTEND_DIR / ".next"
    if next_dir.exists():
        shutil.rmtree(next_dir)


def setup() -> None:
    ensure_command_exists(npm_command())
    ensure_command_exists("ollama")

    with managed_ollama(required=True):
        if not venv_python().exists():
            if is_windows():
                run_command([python_launcher(), "-3", "-m", "venv", ".venv"], BACKEND_DIR)
            else:
                run_command([python_launcher(), "-m", "venv", ".venv"], BACKEND_DIR)

        run_command(
            [str(venv_python()), "-m", "pip", "install", "-r", "requirements.txt"],
            BACKEND_DIR,
        )
        verify_backend_import_contract()
        verify_backend_import_smoke()
        run_command([npm_command(), "install"], FRONTEND_DIR)
        ensure_ollama_model()


def warmup() -> None:
    verify_backend_guards()
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


def ensure_ollama_model() -> None:
    installed_models = list_ollama_models()
    if DEFAULT_OLLAMA_MODEL_NAME in installed_models:
        return
    run_command(["ollama", "pull", DEFAULT_OLLAMA_MODEL_NAME], ROOT_DIR)


def list_ollama_models() -> str:
    return run_command_capture(["ollama", "list"], ROOT_DIR).stdout


def start_ollama_server() -> subprocess.Popen[bytes] | subprocess.Popen[str]:
    if is_windows():
        raise SystemExit(
            "Ollama is installed but not responding. Start the Ollama app/server first, "
            "then rerun the command."
        )

    server_process = subprocess.Popen(
        ["ollama", "serve"],
        cwd=ROOT_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    for _ in range(20):
        time.sleep(0.5)
        try:
            list_ollama_models()
            return server_process
        except SystemExit:
            if server_process.poll() is not None:
                break

    raise SystemExit(
        "Ollama is installed but could not be started automatically. "
        "Start the Ollama app/server first, then rerun the command.",
    )


@contextmanager
def managed_ollama(required: bool) -> subprocess.Popen[bytes] | subprocess.Popen[str] | None:
    ensure_command_exists("ollama")
    server_process: subprocess.Popen[bytes] | subprocess.Popen[str] | None = None
    try:
        try:
            list_ollama_models()
        except SystemExit:
            if not required:
                raise
            server_process = start_ollama_server()
        yield server_process
    finally:
        if server_process is not None:
            terminate_processes([server_process])


def backend() -> None:
    verify_backend_guards()
    with managed_ollama(required=True):
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
    clear_frontend_build_cache()
    run_command([npm_command(), "run", "dev"], FRONTEND_DIR)


def run_both() -> None:
    verify_backend_guards()
    ensure_frontend_install()
    clear_frontend_build_cache()
    with managed_ollama(required=True):
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
        raise SystemExit("Usage: python3 scripts/run_dev.py [setup|warmup|backend|frontend|run|check]")

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
    if command == "check":
        verify_backend_guards()
        return

    raise SystemExit(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
