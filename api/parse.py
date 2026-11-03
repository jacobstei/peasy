"""POST /api/parse  {"url": "..."} or {"text": "..."}  ->  normalized recipe JSON."""
import hmac
import html
import ipaddress
import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

import anthropic
from pydantic import BaseModel

MODEL = "claude-haiku-5-5"
CHROME_MAJOR = 130  # Chrome major version for the User-Agent
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      f"(KHTML, like Gecko) Chrome/{CHROME_MAJOR}{'.0' * 3} Safari/537.36")
MAX_PAGE_BYTES = 5_000_000
MAX_TEXT_CHARS = 60_000  # a recipe never needs more; nav/comment noise beyond this is cut

UNIT_RULES = (
    "Use these unit spellings when they apply: tsp, tbsp, cup, fl oz, pint, quart, gallon, "
    "ml, l, g, kg, oz, lb, pinch, dash. Otherwise use the singular word (clove, can, egg) or null. "
    "quantity is a number, a [min, max] pair for ranges like '2-3', or null. Convert fractions to "
    "decimals (1 1/2 -> 1.5). scalable is false for 'to taste', 'for serving', 'as needed' items. "
    "note holds prep text like 'finely chopped' or 'divided'."
)


class Ingredient(BaseModel):
    quantity: float | list[float] | None
    unit: str | None
    ingredient: str
    note: str | None
    scalable: bool


class Ingredients(BaseModel):
    ingredients: list[Ingredient]


class Recipe(BaseModel):
    title: str
    servings: int | None
    steps: list[str]
    ingredients: list[Ingredient]


# ---------- fetching ----------

def _check_host(url):
    p = urllib.parse.urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("Only http(s) URLs are allowed.")
    for info in socket.getaddrinfo(p.hostname, None):
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ValueError("That address is not allowed.")


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_host(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url):
    # shortcut: DNS is resolved twice (check, then connect), so rebinding is possible; fine behind the passcode.
    _check_host(url)
    opener = urllib.request.build_opener(_SafeRedirect)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with opener.open(req, timeout=15) as r:
        raw = r.read(MAX_PAGE_BYTES)
        charset = r.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


# ---------- JSON-LD ----------

def _is_recipe(node):
    t = node.get("@type")
    return "Recipe" in (t if isinstance(t, list) else [t])


def _find_recipe(node):
    """Walk any JSON-LD shape (@graph, lists, nested objects) for the first Recipe."""
    if isinstance(node, dict):
        if _is_recipe(node):
            return node
        node = list(node.values())
    if isinstance(node, list):
        for child in node:
            found = _find_recipe(child)
            if found:
                return found
    return None


def jsonld_recipe(page):
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            found = _find_recipe(json.loads(html.unescape(block.strip())))
        except ValueError:
            continue
        if found:
            return found
    return None


def _text(s):
    s = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(s))))
    return re.sub(r" ([.,;:!?])", r"\g<1>", s).strip()


def _steps(node):
    if isinstance(node, str):
        return [_text(node)] if _text(node) else []
    if isinstance(node, list):
        return [s for child in node for s in _steps(child)]
    if isinstance(node, dict):
        if "itemListElement" in node:  # HowToSection
            return _steps(node["itemListElement"])
        return _steps(node.get("text") or node.get("name") or "")
    return []


def _servings(y):
    for v in (y if isinstance(y, list) else [y]):
        m = re.search(r"\d+", str(v))
        if m:
            return int(m.group())
    return None


def _image(img):
    if isinstance(img, list):
        img = img[0] if img else None
    if isinstance(img, dict):
        img = img.get("url")
    return img if isinstance(img, str) else None


def og_image(page):
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', page, re.I)
    return html.unescape(m.group(1)) if m else None


def page_text(page):
    page = re.sub(r"<(script|style|noscript|svg|nav|footer|header)\b.*?</\1>", " ", page, flags=re.S | re.I)
    return _text(page)[:MAX_TEXT_CHARS]


# ---------- Claude ----------

def _claude(prompt, schema):
    resp = anthropic.Anthropic().messages.parse(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
        output_format=schema,
    )
    if resp.parsed_output is None:
        raise RuntimeError(f"Claude returned no recipe (stop_reason={resp.stop_reason}).")
    return resp.parsed_output


def normalize(lines):
    prompt = ("Normalize each recipe ingredient line into structured data, one item per line, "
              f"same order. {UNIT_RULES}\n\n" + "\n".join(lines))
    return [i.model_dump() for i in _claude(prompt, Ingredients).ingredients]


def extract(text):
    prompt = ("Extract the recipe from this web page text. steps is the list of instruction steps, "
              f"verbatim. servings is the yield as an integer. {UNIT_RULES}\n\n<page>\n{text}\n</page>")
    return _claude(prompt, Recipe).model_dump()


def parse_recipe(page, image=None):
    node = jsonld_recipe(page)
    if node and node.get("recipeIngredient"):
        return {
            "title": _text(node.get("name") or "Recipe"),
            "servings": _servings(node.get("recipeYield")),
            "image": _image(node.get("image")) or image,
            "steps": _steps(node.get("recipeInstructions")),
            "ingredients": normalize([_text(x) for x in node["recipeIngredient"]]),
            "source": "jsonld",
        }
    out = extract(page_text(page))
    return {**out, "image": image, "source": "claude"}


# ---------- HTTP ----------

class handler(BaseHTTPRequestHandler):
    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        expected = os.environ.get("PEASY_PASSCODE", "")
        given = self.headers.get("X-Peasy-Passcode", "")
        if not expected:
            return self._send(500, {"error": "PEASY_PASSCODE is not set on the server."})
        if not hmac.compare_digest(given.encode(), expected.encode()):
            return self._send(401, {"error": "Wrong passcode."})

        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(min(length, 2_000_000)) or b"{}")
        except ValueError:
            return self._send(400, {"error": "Bad JSON."})

        url, text = (body.get("url") or "").strip(), (body.get("text") or "").strip()
        try:
            if text:
                return self._send(200, parse_recipe(html.escape(text)))
            if not url:
                return self._send(400, {"error": "Send a url or text."})
            try:
                page = fetch(url)
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            except (urllib.error.URLError, OSError) as e:
                return self._send(422, {"error": f"Could not fetch the page ({e}).", "fetch_failed": True})
            return self._send(200, parse_recipe(page, og_image(page)))
        except anthropic.APIStatusError as e:
            return self._send(502, {"error": f"Claude API error {e.status_code}."})
        except anthropic.APIConnectionError:
            return self._send(502, {"error": "Could not reach the Claude API."})
        except Exception as e:  # keep the UI informative instead of a bare 500 page
            return self._send(500, {"error": f"Parse failed: {e}"})
