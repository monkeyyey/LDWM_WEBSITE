"""Run the local API and frontend together; stop both when this launcher exits."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from environment import load_environment


def available(port):
    try:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", port))
    except OSError as exc:
        raise RuntimeError(f"Port {port} is in use. Choose another port with --backend-port or --frontend-port.") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=5173)
    parser.add_argument("--frontend-only", action="store_true")
    parser.add_argument("--backend-only", action="store_true")
    parser.add_argument("--api-url", help="Backend URL for a frontend-only installation")
    args = parser.parse_args()
    if args.frontend_only and args.backend_only:
        parser.error("Choose only one of --frontend-only and --backend-only")
    load_environment()
    env = os.environ.copy()
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    node_bin = env.get("LDWM_NODE_BIN")
    if node_bin:
        env["PATH"] = node_bin + os.pathsep + env.get("PATH", "")
    api_url = args.api_url or f"http://127.0.0.1:{args.backend_port}"
    env.setdefault("VITE_API_BASE", api_url)
    env.setdefault("VITE_FILE_BASE", api_url)
    commands = []
    if not args.frontend_only:
        available(args.backend_port)
        python = env.get("LDWM_BACKEND_PYTHON", sys.executable)
        commands.append(([python, str(ROOT / "backend/server.py"), "--host", "127.0.0.1", "--port", str(args.backend_port)], ROOT))
    if not args.backend_only:
        available(args.frontend_port)
        if not (ROOT / "watermark-lab/node_modules/vite/bin/vite.js").is_file():
            raise RuntimeError("Frontend dependencies are missing. Run bash setup.sh first.")
        commands.append((["node", "node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", str(args.frontend_port), "--strictPort"], ROOT / "watermark-lab"))
    processes = []

    def interrupted(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        for command, cwd in commands:
            processes.append(subprocess.Popen(command, cwd=cwd, env=env, start_new_session=True))
        print(f"Watermark Lab: http://127.0.0.1:{args.frontend_port}" if not args.backend_only else f"Backend: {api_url}", flush=True)
        print("Press Ctrl+C to stop the launched services.", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(0.25)
        return next((process.returncode for process in processes if process.returncode is not None), 1) or 1
    except KeyboardInterrupt:
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Could not start: {exc}", file=sys.stderr)
        raise SystemExit(1)
