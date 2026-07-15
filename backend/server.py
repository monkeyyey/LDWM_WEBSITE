from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from registry import MethodRegistry
from runtimes.sfwmark_lite import runtime_report
from schemas import WatermarkRequest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY = MethodRegistry(PROJECT_ROOT)


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "WatermarkBackend/0.1"

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._json({"ok": True, "service": "watermark-backend"})
            return
        if path == "/methods":
            self._json({"methods": REGISTRY.list_methods()})
            return
        if path == "/runtime":
            self._json({"runtime": runtime_report()})
            return
        if path.startswith("/files/"):
            self._serve_storage_file(path)
            return
        self._json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in {
            "/watermark/upload",
            "/watermark/generate",
            "/detect",
            "/attack-test",
        }:
            self._json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            payload = self._read_json()
            workflow = "upload" if path == "/watermark/upload" else "generate"
            if path == "/detect":
                workflow = "detect"
            if path == "/attack-test":
                workflow = "attack"
            payload = normalize_payload(payload)
            request = WatermarkRequest(workflow=workflow, **payload)
            adapter = REGISTRY.get_adapter(request.method)
            result = adapter.run(request)
            self._json({"result": result.to_dict()})
        except KeyError as exc:
            self._json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except TypeError as exc:
            self._json({"error": f"Invalid request: {exc}"}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._json({"error": f"Backend error: {exc}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _read_json(self) -> dict:
        length = int(self.headers.get("content-length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        if not raw:
            return {}
        return json.loads(raw)

    def _json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_cors_headers(self) -> None:
        self.send_header("access-control-allow-origin", "*")
        self.send_header("access-control-allow-methods", "GET, POST, OPTIONS")
        self.send_header("access-control-allow-headers", "content-type")

    def _serve_storage_file(self, path: str) -> None:
        storage_root = (PROJECT_ROOT / "backend" / "storage").resolve()
        requested = unquote(path.removeprefix("/files/"))
        file_path = (storage_root / requested).resolve()
        if storage_root not in file_path.parents and file_path != storage_root:
            self._json({"error": "Invalid file path"}, status=HTTPStatus.BAD_REQUEST)
            return
        if not file_path.is_file():
            self._json({"error": "File not found"}, status=HTTPStatus.NOT_FOUND)
            return
        content = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self._send_cors_headers()
        self.send_header("content-type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
        self.send_header("content-length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), ApiHandler)
    print(f"Watermark backend listening on http://{args.host}:{args.port}")
    server.serve_forever()


def normalize_payload(payload: dict) -> dict:
    aliases = {
        "imageName": "image_name",
        "imageDataUrl": "image_data_url",
    }
    normalized = dict(payload)
    for source, target in aliases.items():
        if source in normalized and target not in normalized:
            normalized[target] = normalized.pop(source)
    return normalized


if __name__ == "__main__":
    main()
