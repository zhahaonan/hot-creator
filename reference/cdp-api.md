# CDP Proxy API Reference

## Basics

- Address: `http://localhost:3456` (configurable via `CDP_PROXY_PORT` env var)
- Start: `node <SKILL_DIR>/scripts/cdp/check.mjs` (auto-starts proxy if not running)
- Proxy runs persistently — do not stop it (restart requires Chrome re-authorization)
- Force stop: kill the process on the configured port

## Endpoints

### GET /health
Health check. Returns connection status.
```bash
curl -s http://localhost:3456/health
```

### GET /targets
List all open page tabs. Returns array with `targetId`, `title`, `url`.
```bash
curl -s http://localhost:3456/targets
```

### GET /new?url=URL
Create new background tab, waits for page load. Returns `{ targetId }`.
```bash
curl -s "http://localhost:3456/new?url=https://example.com"
```

### GET /close?target=ID
Close specified tab.
```bash
curl -s "http://localhost:3456/close?target=TARGET_ID"
```

### GET /navigate?target=ID&url=URL
Navigate existing tab to new URL, waits for load.
```bash
curl -s "http://localhost:3456/navigate?target=ID&url=https://example.com"
```

### GET /back?target=ID
Go back one page.
```bash
curl -s "http://localhost:3456/back?target=ID"
```

### GET /info?target=ID
Get page info (title, url, readyState).
```bash
curl -s "http://localhost:3456/info?target=ID"
```

### POST /eval?target=ID
Execute JavaScript expression. POST body is JS code.
```bash
curl -s -X POST "http://localhost:3456/eval?target=ID" -d 'document.title'
```

### POST /click?target=ID
JS-level click (`el.click()`). POST body is CSS selector. Auto scrollIntoView.
```bash
curl -s -X POST "http://localhost:3456/click?target=ID" -d 'button.submit'
```

### POST /clickAt?target=ID
CDP-level real mouse click (`Input.dispatchMouseEvent`). POST body is CSS selector. Counts as real user gesture — can trigger file dialogs, bypass anti-automation.
```bash
curl -s -X POST "http://localhost:3456/clickAt?target=ID" -d 'button.upload'
```

### POST /setFiles?target=ID
Set local files on file input (`DOM.setFileInputFiles`). POST body is JSON.
```bash
curl -s -X POST "http://localhost:3456/setFiles?target=ID" -d '{"selector":"input[type=file]","files":["/path/to/file.png"]}'
```

### GET /scroll?target=ID&y=3000&direction=down
Scroll page. `direction`: `down` (default), `up`, `top`, `bottom`. Waits 800ms after scroll for lazy-load.
```bash
curl -s "http://localhost:3456/scroll?target=ID&y=3000"
curl -s "http://localhost:3456/scroll?target=ID&direction=bottom"
```

### GET /screenshot?target=ID&file=/tmp/shot.png
Screenshot. Specify `file` to save locally; omit for binary image response. Optional `format=jpeg`.
```bash
curl -s "http://localhost:3456/screenshot?target=ID&file=/tmp/shot.png"
```

## /eval Tips

- POST body is any JS expression, returns `{ value }` or `{ error }`
- Supports `awaitPromise`: can use async expressions
- Return value must be serializable (string, number, object) — DOM nodes cannot be returned directly
- For large data extraction, wrap in `JSON.stringify()`
- Write selectors based on actual page DOM structure, not fixed templates

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| Chrome remote debugging not enabled | Chrome not configured | Open `chrome://inspect/#remote-debugging`, check Allow |
| Attach failed | Invalid targetId or tab closed | Use `/targets` to get fresh list |
| CDP command timeout | Page unresponsive | Retry or check tab status |
| Port already in use | Another proxy running | Existing instance can be reused |
