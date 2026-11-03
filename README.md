# Peasy (Recipeasy)

A mobile-first recipe scaler. Paste a recipe link. Peasy reads the recipe, lets you change servings, and converts units. You can install it to your home screen.

## How it works

1. The frontend sends the link to `/api/parse` with your passcode.
2. The function fetches the page with a normal browser User-Agent.
3. It looks for schema.org `Recipe` JSON-LD (handles `@graph`, lists, and `HowToSection` steps).
4. If there is no JSON-LD, it sends the cleaned page text to Claude to extract the whole recipe.
5. Either way, Claude normalizes each ingredient into `{quantity, unit, ingredient, note, scalable}`. `quantity` is a number, a `[min, max]` range, or `null`.
6. If the site blocks the fetch (403, bot wall), the app shows a "paste page text" box. That text goes through the same parser.

The frontend scales scalable amounts, converts volume (tsp/tbsp/cup <-> ml/l), converts oven temperatures in the steps, and keeps the screen awake while a recipe is open.

## Files

```
index.html             UI, styles, and all frontend logic (unit logic is in <script id="units">)
api/parse.py           Vercel Python function: fetch, JSON-LD, Claude normalization
manifest.webmanifest   PWA manifest
sw.js                  Service worker (offline app shell; never caches /api)
icon-*.png             App icons (regenerate with: python scripts/make_icons.py)
requirements.txt       Python dependencies for the function
vercel.json            Function timeout and service worker cache header
tests/                 Offline tests (no API key needed)
```

## Deploy to Vercel from GitHub

1. Create a new GitHub repository and push this folder to it:
   ```
   git init
   git add .
   git commit -m "Peasy"
   git branch -M main
   git remote add origin https://github.com/<you>/peasy.git
   git push -u origin main
   ```
2. In Vercel, click **Add New > Project** and import the repository.
3. Set **Framework Preset** to **Other**. Leave the build command and output directory empty.
4. Under **Environment Variables**, add:
   - `ANTHROPIC_API_KEY`: your Anthropic API key.
   - `PEASY_PASSCODE`: any shared passcode. Everyone who uses the app needs it.
5. Click **Deploy**. Every push to `main` deploys again.
6. Open the site on your phone. The app asks for the passcode once and remembers it.
7. Install it: on iPhone, tap **Share > Add to Home Screen**. On Android Chrome, tap **Install app**.

If you change the passcode, each device asks again on its next request.

## Run locally

```
npm i -g vercel
vercel link
vercel env pull .env.local
vercel dev
```

## Tests

```
python -X utf8 tests/test_parse.py   # JSON-LD parsing, text fallback, URL guard (Claude stubbed)
node tests/units.test.mjs            # fractions, unit conversion, promotion, temperatures
```

## Cost

The function uses `claude-haiku-5-5` at low effort ($0.10 input, $0.50 output per million tokens). A JSON-LD recipe costs about 0.1 cents. A page without JSON-LD sends up to 60,000 characters of text, about 0.3 cents. If extraction quality is poor on messy pages, change `MODEL` in `api/parse.py` to `claude-sonnet-5-5` or `claude-opus-5-5`.

## Limits

- Weight and density conversion (cups of flour to grams) is not done. Weights scale but keep their unit.
- Imperial volume stops at cups. A gallon shows as 16 cups.
- The passcode is a shared secret, not user accounts. Rotate it in Vercel if it leaks.
- The URL guard blocks private and local addresses. A DNS rebinding attack can still get past it; the passcode limits who can try.
