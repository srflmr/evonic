# Obscura — Headless Browser CLI

You have `obscura` installed at `/usr/local/bin/obscura`. It is a lightweight, single-binary headless browser — no dependencies, no Chromium download. It bundles V8 (JavaScript engine) and a minimal rendering engine.

## Quick Check

```bash
obscura --version
```

If the command fails with "command not found", inform the user that obscura is not installed. Offer to install it from `https://github.com/h4ckf0r0day/obscura/releases`.

---

## Commands Overview

| Command | Purpose |
|---------|---------|
| `obscura fetch <URL>` | Fetch a single page. Render JS, evaluate expressions, dump content. |
| `obscura scrape <URLS...>` | Fetch multiple URLs in parallel with high concurrency. |
| `obscura serve` | Run a CDP (Chrome DevTools Protocol) server for Puppeteer/Playwright. |
| `obscura mcp` | Run an MCP (Model Context Protocol) server for LLM tool-use. |

### Global Options

| Flag | Description |
|------|-------------|
| `-v, --verbose` | Verbose logging |
| `--proxy <PROXY>` | Route traffic through a proxy (e.g. `socks5://127.0.0.1:9050`) |
| `--user-agent <UA>` | Custom User-Agent string |
| `--storage-dir <DIR>` | Directory for cookies and cache (persists across runs) |
| `--allow-private-network` | Allow fetches to localhost / RFC1918 / link-local addresses (blocked by default for SSRF safety) |
| `--v8-flags <FLAGS>` | Pass raw V8 flags (e.g. `"--max-old-space-size=4096"`) |
| `--obey-robots` | Respect robots.txt (not default) |

---

## `fetch` — Fetch a Single Page

```bash
obscura fetch <URL> [OPTIONS]
```

### Basic fetch + JS evaluation

```bash
obscura fetch https://example.com --eval "document.title"
```

The `--eval` expression runs in the page context after JS has executed. Use it to extract data.

### Dump rendered content

```bash
# Rendered HTML (after JS execution)
obscura fetch https://example.com --dump html

# Visible text only (stripped tags)
obscura fetch https://example.com --dump text

# All links on the page
obscura fetch https://example.com --dump links

# Markdown version of the page
obscura fetch https://example.com --dump markdown

# Raw HTTP response body (bypasses browser/JS — use for JSON, images, CSS, etc.)
obscura fetch https://api.example.com/data.json --dump original

# Sub-resource asset URLs (scripts, images, stylesheets, iframes)
obscura fetch https://example.com --dump assets
```

### Targeted extraction

```bash
obscura fetch https://example.com --selector "div.content" --dump html
obscura fetch https://example.com --selector "h1" --eval "el => el.textContent"
```

### Timing & waiting

```bash
# Wait longer for SPAs to render (default: 5s)
obscura fetch https://spa.example.com --wait 10 --dump html

# Timeout (default: 30s)
obscura fetch https://slow.example.com --timeout 60

# Wait strategy (default: load)
obscura fetch https://example.com --wait-until load
```

---

## `scrape` — Parallel Scraping

```bash
obscura scrape [OPTIONS] <URLS...>
```

Scrape multiple URLs with parallel concurrency.

```bash
# Scrape 3 URLs, extract title from each
obscura scrape https://example.com https://httpbin.org/json https://news.ycombinator.com --eval "document.title"

# High concurrency (default: 10)
obscura scrape --concurrency 20 url1 url2 url3 ... url50 --eval "document.querySelector('h1')?.textContent"

# JSON output (default) with timeout
obscura scrape --format json --timeout 60 url1 url2 url3 --eval "document.title"

# Quiet mode — only output results
obscura scrape -q url1 url2 --eval "document.title"
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--concurrency <N>` | 10 | Max parallel fetches |
| `--format <json\|csv>` | json | Output format |
| `--timeout <SEC>` | 60 | Per-URL timeout |
| `--eval <JS>` | — | JS expression to evaluate on each page |
| `-q, --quiet` | — | Suppress progress output |
| `--proxy <PROXY>` | — | Proxy for all requests |

---

## `serve` — CDP Server

Run a Chrome DevTools Protocol server that Puppeteer, Playwright, or any CDP client can connect to.

```bash
obscura serve [OPTIONS]
```

```bash
# Start CDP server on default port 9222
obscura serve

# Custom port and host (for remote access)
obscura serve --port 9222 --host 0.0.0.0

# Stealth mode (evade bot detection)
obscura serve --stealth

# Multiple worker processes
obscura serve --workers 4

# Custom user agent
obscura serve --user-agent "Mozilla/5.0 ..."

# Allow local file:// access (off by default)
obscura serve --allow-file-access

# Persist cookies/cache
obscura serve --storage-dir /tmp/obscura-data
```

Connect from Puppeteer:
```js
const browser = await puppeteer.connect({ browserURL: 'http://127.0.0.1:9222' });
```

Connect from Playwright:
```js
const browser = await playwright.chromium.connectOverCDP('http://127.0.0.1:9222');
```

**Important:** The CDP server runs in the foreground. Use `tmux` or `screen` to run it in the background.

---

## `mcp` — MCP Server

Run a Model Context Protocol server so LLM tools (Claude, Cursor, etc.) can use obscura as a browser tool.

```bash
obscura mcp [OPTIONS]
```

```bash
# Stdio transport (default for local MCP)
obscura mcp

# HTTP transport (for remote MCP)
obscura mcp --http --port 3000

# Stealth mode
obscura mcp --stealth

# Custom user agent
obscura mcp --user-agent "Mozilla/5.0 ..."

# Allow private network access
obscura mcp --allow-private-network
```

**Important:** The MCP server runs in the foreground. Use `tmux` or `screen`.

---

## Common Patterns

### Extract page title
```bash
obscura fetch https://example.com --eval "document.title"
```

### Check if an element exists
```bash
obscura fetch https://example.com --eval "!!document.querySelector('.target-class')"
```

### Get full rendered HTML of a SPA
```bash
obscura fetch https://spa.example.com --wait 10 --dump html
```

### Extract multiple data points
```bash
obscura fetch https://example.com --eval "
  JSON.stringify({
    title: document.title,
    h1: document.querySelector('h1')?.textContent,
    links: [...document.querySelectorAll('a')].map(a => a.href)
  })
"
```

### Scrape a batch of URLs for titles
```bash
obscura scrape url1 url2 url3 url4 url5 --concurrency 5 --eval "document.title" -q
```

### Get all image URLs from a page
```bash
obscura fetch https://example.com --eval "
  [...document.querySelectorAll('img')].map(img => img.src)
"
```

### Fetch raw JSON API (bypass browser)
```bash
obscura fetch https://api.example.com/data.json --dump original
```

---

## Security Notes

- **Private network access is blocked by default** (SSRF protection). Use `--allow-private-network` only for local development.
- **File access is off by default** in `serve` mode. Use `--allow-file-access` only on trusted networks.
- When running `serve` or `mcp` on `0.0.0.0`, ensure the port is firewalled or on a trusted network.
- Use `--proxy` to route traffic through Tor or an upstream proxy when needed.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Page content is empty | Increase `--wait` (SPAs need more time). Try `--wait 15`. |
| `--eval` returns null | The element may not exist. Check with `!!document.querySelector(...)` first. |
| Timeout errors | Increase `--timeout`. Default is 30s for fetch, 60s for scrape. |
| `serve` cannot bind port | Port already in use. Kill the existing process or use `--port <other>`. |
| Large page memory | Use `--v8-flags "--max-old-space-size=256"` to limit V8 heap. |
