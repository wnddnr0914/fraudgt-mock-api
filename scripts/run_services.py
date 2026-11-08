"""Start the four independent Mock API processes; Ctrl+C stops owned children."""
import argparse
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.deployment import SERVICE_SPECS


def available_port(host: str, port: int) -> None:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind((host, port))


def connection_host(host: str) -> str:
    if host == "0.0.0.0":
        return "127.0.0.1"
    if host == "::":
        return "[::1]"
    return f"[{host}]" if ":" in host else host


def stop_children(children: list[tuple[str, subprocess.Popen]]) -> None:
    for name, process in reversed(children):
        if process.poll() is not None:
            continue
        if os.name == "nt":
            # A Windows venv launcher can own another python.exe. Stop only the
            # process tree created by this launcher, including that child.
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW, check=False)
        else:
            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        print(f"Stopped {name}", flush=True)


def wait_ready(children: list[tuple[str, subprocess.Popen]], urls: dict[str, str], timeout: float) -> None:
    remaining = set(urls)
    deadline = time.monotonic() + timeout
    while remaining:
        for name, process in children:
            if process.poll() is not None:
                raise RuntimeError(f"{name} exited before startup (code {process.returncode})")
        if time.monotonic() > deadline:
            raise RuntimeError(f"Startup timed out: {', '.join(sorted(remaining))}")
        for name in tuple(remaining):
            try:
                with urlopen(urls[name] + "/openapi.json", timeout=0.5) as response:
                    if response.status == 200:
                        remaining.remove(name)
            except (URLError, TimeoutError, OSError):
                pass
        if remaining:
            time.sleep(0.1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="Bind host; use 0.0.0.0 for LAN access")
    parser.add_argument("--env-file", type=Path, help="Backend settings passed identically to every service")
    parser.add_argument("--startup-timeout", type=float, default=30)
    parser.add_argument("--smoke-test", action="store_true", help="Start four real servers, verify, then stop them")
    for name, spec in SERVICE_SPECS.items():
        parser.add_argument(f"--{name}-port", type=int, default=spec.port)
    args = parser.parse_args()
    ports = {name: getattr(args, name + "_port") for name in SERVICE_SPECS}
    if len(set(ports.values())) != len(ports) or any(not 1 <= port <= 65535 for port in ports.values()):
        parser.error("Service ports must be distinct integers in 1..65535")
    if not 0 < args.startup_timeout <= 300:
        parser.error("--startup-timeout must be in (0, 300]")
    if args.env_file is not None:
        args.env_file = args.env_file.resolve()
        if not args.env_file.is_file():
            parser.error(f"Environment file not found: {args.env_file}")
    for name, port in ports.items():
        try:
            available_port(args.host, port)
        except OSError as exc:
            parser.error(f"Cannot bind {name} on {args.host}:{port}: {exc}")

    children = []
    urls = {name: f"http://{connection_host(args.host)}:{port}" for name, port in ports.items()}
    try:
        for name, spec in SERVICE_SPECS.items():
            command = [sys.executable, "-m", "uvicorn", spec.module, "--host", args.host,
                       "--port", str(ports[name]), "--workers", "1"]
            if args.env_file:
                command.extend(["--env-file", str(args.env_file)])
            options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
            process = subprocess.Popen(command, cwd=ROOT, **options)
            children.append((name, process))
            print(f"Starting {name}: {urls[name]} (PID {process.pid})", flush=True)
        wait_ready(children, urls, args.startup_timeout)
        print("All four services are ready. Each /docs contains only its own endpoints.", flush=True)
        if args.smoke_test:
            command = [sys.executable, str(ROOT / "scripts" / "smoke_test.py")]
            for name, url in urls.items():
                command.extend([f"--{name}-base-url", url])
            return subprocess.run(command, cwd=ROOT, check=False).returncode
        print("Press Ctrl+C to stop all four services.", flush=True)
        while True:
            for name, process in children:
                if process.poll() is not None:
                    raise RuntimeError(f"{name} stopped unexpectedly (code {process.returncode})")
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nStopping services...", flush=True)
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"Service startup/run failed: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        stop_children(children)


if __name__ == "__main__":
    raise SystemExit(main())
