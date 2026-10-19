import base64
import binascii
import hmac
import json
import logging
import mimetypes
import os
from pathlib import Path
from http import HTTPStatus
from urllib.parse import parse_qs, unquote
from wsgiref.simple_server import make_server


ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "destinations.json"
MAX_QUERY_LENGTH = 120


def load_destinations():
    with DATA_FILE.open(encoding="utf-8") as data_file:
        destinations = json.load(data_file)
    if not isinstance(destinations, list):
        raise ValueError("Destination data must be a JSON array.")
    for place in destinations:
        required = ("slug", "name", "region", "categories", "summary", "image")
        if not isinstance(place, dict) or any(key not in place for key in required):
            raise ValueError("Every destination must include its required fields.")
        if not isinstance(place["categories"], list) or not all(
            isinstance(category, str) for category in place["categories"]
        ):
            raise ValueError(f"Destination categories are invalid: {place.get('slug', 'unknown')}")
    return destinations


def filter_destinations(destinations, query="", category=""):
    query = query.casefold().strip()
    matches = []
    for place in destinations:
        if category and category not in place["categories"]:
            continue
        searchable = [
            place.get("name", ""),
            place.get("region", ""),
            place.get("summary", ""),
            place.get("description", ""),
            place.get("label", ""),
            place.get("tag", ""),
            *place.get("categories", []),
            *place.get("searchTerms", []),
            *place.get("highlights", []),
            place.get("localTip", ""),
            *(
                value
                for section in place.get("guideSections", [])
                for value in (
                    section.get("title", ""),
                    section.get("intro", ""),
                    *section.get("items", []),
                )
            ),
        ]
        if query and not any(query in value.casefold() for value in searchable if isinstance(value, str)):
            continue
        matches.append(place)
    return matches


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = unquote(environ.get("PATH_INFO", "/"))

    def respond(status, body, content_type, extra_headers=()):
        headers = [
            ("Content-Type", content_type),
            ("Content-Length", str(len(body))),
            ("X-Content-Type-Options", "nosniff"),
            *extra_headers,
        ]
        start_response(f"{status} {HTTPStatus(status).phrase}", headers)
        return [body]

    def respond_json(status, payload, extra_headers=()):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return respond(
            status,
            body,
            "application/json; charset=utf-8",
            [("Cache-Control", "no-store"), *extra_headers],
        )

    if path != "/api/health" and os.environ.get("PREVIEW_AUTH_REQUIRED", "").casefold() in {
        "1", "true", "yes",
    }:
        expected_username = os.environ.get("PREVIEW_USERNAME", "")
        expected_password = os.environ.get("PREVIEW_PASSWORD", "")
        if not expected_username or not expected_password:
            logging.error("Preview authentication is required but its credentials are not configured.")
            return respond_json(503, {"error": "Private preview authentication is not configured."})
        authorization = environ.get("HTTP_AUTHORIZATION", "")
        scheme, _, encoded_credentials = authorization.partition(" ")
        try:
            decoded = base64.b64decode(encoded_credentials, validate=True).decode("utf-8")
            username, separator, password = decoded.partition(":")
        except (binascii.Error, UnicodeDecodeError):
            username, separator, password = "", "", ""
        username_matches = hmac.compare_digest(username, expected_username)
        password_matches = hmac.compare_digest(password, expected_password)
        authenticated = (
            scheme.casefold() == "basic"
            and bool(separator)
            and username_matches
            and password_matches
        )
        if not authenticated:
            return respond_json(
                401,
                {"error": "Authentication required."},
                [("WWW-Authenticate", 'Basic realm="Elsewhere Private Preview", charset="UTF-8"')],
            )

    if method != "GET":
        return respond_json(405, {"error": "Method not allowed."})
    if path == "/api/health":
        return respond_json(200, {"status": "ok"})
    if path == "/api/destinations":
        params = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
        query = params.get("q", [""])[0].strip()
        category = params.get("category", [""])[0].strip()
        if len(query) > MAX_QUERY_LENGTH:
            return respond_json(400, {"error": f"Search must be {MAX_QUERY_LENGTH} characters or fewer."})
        try:
            destinations = load_destinations()
            categories = {value for place in destinations for value in place["categories"]}
            if category and category not in categories:
                return respond_json(400, {"error": "Unknown destination category."})
            results = filter_destinations(destinations, query, category)
            summary_fields = (
                "slug", "name", "region", "categories", "label",
                "tag", "summary", "image", "imageAlt",
            )
            summaries = [{key: place[key] for key in summary_fields} for place in results]
            return respond_json(200, {"count": len(summaries), "results": summaries})
        except (OSError, ValueError, json.JSONDecodeError):
            logging.exception("Destination data could not be loaded.")
            return respond_json(500, {"error": "Destination data is temporarily unavailable."})
    if path.startswith("/api/destinations/"):
        try:
            destinations = load_destinations()
        except (OSError, ValueError, json.JSONDecodeError):
            logging.exception("Destination data could not be loaded.")
            return respond_json(500, {"error": "Destination data is temporarily unavailable."})
        slug = path.removeprefix("/api/destinations/")
        place = next((item for item in destinations if item["slug"] == slug), None)
        if place is None:
            return respond_json(404, {"error": "Destination not found."})
        return respond_json(200, place)

    relative_path = "index.html" if path == "/" else path.lstrip("/")
    requested_file = (ROOT / relative_path).resolve()
    if (
        not requested_file.is_relative_to(ROOT)
        or (relative_path != "index.html" and not relative_path.startswith("images/"))
        or requested_file.suffix.lower() not in {".html", ".jpg", ".jpeg", ".png", ".webp"}
        or not requested_file.is_file()
    ):
        return respond_json(404, {"error": "File not found."})
    content = requested_file.read_bytes()
    content_type = mimetypes.guess_type(requested_file.name)[0] or "application/octet-stream"
    if content_type.startswith("text/"):
        content_type = f"{content_type}; charset=utf-8"
    return respond(200, content, content_type)


def main():
    port = int(os.environ.get("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535.")
    host = os.environ.get("HOST", "127.0.0.1")
    server = make_server(host, port, application)
    print(f"Elsewhere is running at http://{host}:{port} (press Ctrl+C to stop).")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Elsewhere.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
