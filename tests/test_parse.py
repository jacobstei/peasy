"""Offline checks for the JSON-LD path. Run: python tests/test_parse.py (no API key needed)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
import parse  # noqa: E402

parse.normalize = lambda lines: [{"raw": l} for l in lines]  # stub out the Claude call
parse.extract = lambda text: {"title": "FROM_CLAUDE", "servings": None, "steps": [], "ingredients": [], "_text": text}

graph = {"@context": "https://schema.org", "@graph": [
    {"@type": "WebPage", "name": "page"},
    {"@type": ["Recipe", "NewsArticle"], "name": "Tom &amp; Pie", "recipeYield": ["4", "4 servings"],
     "image": [{"@type": "ImageObject", "url": "https://x.test/a.jpg"}],
     "recipeIngredient": ["1 1/2 cups flour", "salt to taste"],
     "recipeInstructions": [
         {"@type": "HowToSection", "name": "Dough", "itemListElement": [
             {"@type": "HowToStep", "text": "Mix <b>well</b>."}, {"@type": "HowToStep", "text": "Rest."}]},
         "Bake at 350°F."]},
]}
page = f'<html><script type="application/ld+json">{{bad json</script>' \
       f'<script type="application/ld+json">{json.dumps(graph)}</script></html>'

r = parse.parse_recipe(page, "https://x.test/og.jpg")
assert r["source"] == "jsonld", r
assert r["title"] == "Tom & Pie", r["title"]
assert r["servings"] == 4
assert r["image"] == "https://x.test/a.jpg"
assert r["steps"] == ["Mix well.", "Rest.", "Bake at 350°F."], r["steps"]
assert r["ingredients"] == [{"raw": "1 1/2 cups flour"}, {"raw": "salt to taste"}]

# No JSON-LD: falls back to page text, drops scripts, keeps og:image.
plain = '<meta property="og:image" content="https://x.test/og.jpg"><script>evil()</script><p>2 eggs</p>'
r = parse.parse_recipe(plain, parse.og_image(plain))
assert r["source"] == "claude" and r["image"] == "https://x.test/og.jpg"
assert "evil" not in r["_text"] and "2 eggs" in r["_text"]

assert parse._servings("Makes 12 cookies") == 12 and parse._servings(None) is None

# SSRF guard
for bad in ("file:///etc/passwd", "http://localhost/", "http://169.254.169.254/"):
    try:
        parse._check_host(bad)
        raise AssertionError(f"allowed {bad}")
    except ValueError:
        pass

print("parse tests passed")
