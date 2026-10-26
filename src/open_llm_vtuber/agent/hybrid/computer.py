"""Browser-only computer use with an operator-owned approval boundary.

DOM/page text/images are observations, never authority. No shell, filesystem,
clipboard, arbitrary JavaScript, desktop input, or model-accessible approval API.
"""

import asyncio
import base64
import hashlib
import json
import uuid
from urllib.parse import urlsplit
from .contracts import validate


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def origin(url):
    if (
        not isinstance(url, str)
        or any(ord(c) <= 32 or ord(c) == 127 for c in url)
        or "\\" in url
    ):
        raise PermissionError("Malformed URL")
    parts = urlsplit(url)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
    ):
        raise PermissionError("Only http(s) URLs without credentials are allowed")
    host = parts.hostname.lower().encode("idna").decode("ascii")
    if ":" in host:
        host = f"[{host}]"
    port = parts.port
    suffix = (
        f":{port}" if port and port != {"http": 80, "https": 443}[parts.scheme] else ""
    )
    return f"{parts.scheme}://{host}{suffix}"


class BrowserComputer:
    ACTIONS = {
        "navigate",
        "observe",
        "screenshot",
        "click",
        "fill",
        "vision_click",
        "close",
        "scroll",
    }

    def __init__(self, config, store):
        self.config, self.store = config, store
        for entry in config.allowed_origins:
            parts = urlsplit(entry)
            if (
                parts.path not in {"", "/"}
                or parts.query
                or parts.fragment
                or "*" in entry
            ):
                raise ValueError(
                    "Allowlist entries must be exact origins, without paths, queries or wildcards"
                )
        self.allowed = {origin(url) for url in config.allowed_origins}
        self._lock = asyncio.Lock()
        self._playwright = self._browser = self._context = self._page = None
        self._active_action = None
        self._network_pending = []
        self._network_attempts = 0
        self._network_completed = []
        self._session = uuid.uuid4().hex
        self._observation = None
        self._vision_observation = None
        self._vision_hash = None

    def check_url(self, url):
        if origin(url) not in self.allowed:
            raise PermissionError("Origin is outside operator allowlist")

    async def _rate_limit(self):
        await asyncio.to_thread(self.store.rate_limit, self.config.actions_per_minute)

    async def _approval(self, payload):
        payload = {**payload, "browser_session": self._session}
        return await asyncio.to_thread(
            self.store.request_approval, payload, self.config.approval_seconds
        )

    async def _start(self):
        if self._page:
            return
        from playwright.async_api import async_playwright

        try:
            self._playwright = await async_playwright().start()
            if self.config.cdp_url:
                parts = urlsplit(self.config.cdp_url)
                if (
                    parts.scheme != "http"
                    or parts.hostname not in {"localhost", "127.0.0.1", "::1"}
                    or parts.username
                    or parts.password
                ):
                    raise PermissionError("CDP endpoint must be local HTTP")
                self._browser = await self._playwright.chromium.connect_over_cdp(
                    self.config.cdp_url
                )
            else:
                self._browser = await self._playwright.chromium.launch(
                    headless=self.config.headless
                )
            self._context = await self._browser.new_context(
                accept_downloads=False,
                service_workers="block",
                permissions=[],
                viewport={"width": 1280, "height": 720},
            )
            self._context.set_default_timeout(self.config.timeout_seconds * 1000)
            await self._context.route("**/*", self._route)
            await self._context.route_web_socket("**/*", lambda ws: ws.close())
            self._page = await self._context.new_page()
            self._page.on("dialog", lambda dialog: dialog.dismiss())
            self._page.on("filechooser", lambda chooser: chooser.set_files([]))
            self._context.on("page", self._reject_popup)
        except BaseException:
            await self.close()
            raise

    async def _reject_popup(self, page):
        if page != self._page:
            await page.close()

    async def _route(self, route):
        request = route.request
        try:
            self.check_url(request.url)
            if request.method not in {"GET", "HEAD"}:
                self._network_attempts += 1
                if self._network_attempts > 4 or request.method not in {
                    "POST",
                    "PUT",
                    "PATCH",
                    "DELETE",
                }:
                    raise PermissionError(
                        "Network mutation budget/method not permitted"
                    )
                if self._active_action not in {"click", "vision_click"}:
                    raise PermissionError("Background/fill writes blocked")
                body = request.post_data_buffer or b""
                if len(body) > 8192:
                    raise PermissionError("Network mutation body exceeds review budget")
                payload = {
                    "kind": "network_request",
                    "method": request.method,
                    "url": request.url,
                    "body_sha256": hashlib.sha256(body).hexdigest(),
                    "body_preview": body.decode("utf-8", errors="replace"),
                    "page_url": self._page.url,
                    "content_type": request.headers.get("content-type", ""),
                }
                payload["headers_sha256"] = hashlib.sha256(
                    canonical(await request.all_headers()).encode()
                ).hexdigest()
                pending = await self._approval(payload)
                if pending:
                    self._network_pending.append(pending)
                    raise PermissionError(
                        "Exact network request requires separate operator approval"
                    )
            # Never follow an off-origin redirect, even for subresources/frames.
            response = await route.fetch(
                max_redirects=0, timeout=self.config.timeout_seconds * 1000
            )
            # Browser redirects can bypass route callbacks for subsequent hops.
            # Require a new, explicitly checked navigation instead of forwarding 3xx.
            if 300 <= response.status < 400 and response.headers.get("location"):
                raise PermissionError(
                    "Redirects require explicit navigation to the final allowed URL"
                )
            try:
                await route.fulfill(response=response)
                if request.method not in {"GET", "HEAD"}:
                    self._network_completed.append(
                        {
                            "method": request.method,
                            "url": request.url,
                            "http_status": response.status,
                        }
                    )
            finally:
                await response.dispose()
        except Exception:
            await route.abort()

    async def _fingerprint(self):
        self.check_url(self._page.url)
        # Fixed code only; model cannot supply JavaScript to execute.
        dom = await self._page.content()
        scroll = await self._page.evaluate("() => [scrollX,scrollY]")
        return hashlib.sha256(
            (self._page.url + dom + canonical(scroll)).encode()
        ).hexdigest()

    async def _observe(self, screenshot=False):
        self.check_url(self._page.url)
        self._observation = await self._fingerprint()
        text = await self._page.locator("body").inner_text()
        controls = await self._page.locator(
            "a,button,input,textarea,select"
        ).evaluate_all(
            "els => els.slice(0,60).map((e,i) => ({tag:e.tagName, selector:e.id && document.querySelectorAll('#'+CSS.escape(e.id)).length===1 ? '#'+CSS.escape(e.id) : 'a,button,input,textarea,select >> nth='+i, role:e.getAttribute('role'), name:e.getAttribute('aria-label') || e.innerText?.slice(0,100), type:e.getAttribute('type'), href:e.tagName==='A' ? e.href : undefined}))"
        )
        result = {
            "status": "observed",
            "untrusted": True,
            "url": self._page.url,
            "observation": self._observation,
            "text": text[:8000],
            "controls": controls,
        }
        if screenshot:
            pixels = await self._page.screenshot(type="png")
            result["_image"] = base64.b64encode(pixels).decode()
            self._vision_hash = hashlib.sha256(pixels).hexdigest()
            # Playwright can leave empty style attributes while restoring caret
            # visibility. Bind the observation to the post-capture DOM.
            self._observation = await self._fingerprint()
            result["observation"] = self._observation
            self._vision_observation = self._observation
        else:
            self._vision_observation = None
        return result

    async def execute(self, action):
        action = validate("computer", action)
        async with self._lock:
            # close remains available after permission revocation or budget exhaustion.
            if action.get("action") == "close":
                await self.close()
                return {"status": "closed"}
            if not self.config.enabled:
                raise PermissionError("Computer use is disabled by the operator")
            await self._rate_limit()
            self._network_pending = []
            self._network_attempts = 0
            self._network_completed = []
            digest = hashlib.sha256(canonical(action).encode()).hexdigest()
            try:
                result = await asyncio.wait_for(
                    self._execute(action), self.config.timeout_seconds + 5
                )
                if self._network_pending:
                    result.update(
                        status="network_confirmation_required",
                        pending_network=self._network_pending[:4],
                        message="Network write was blocked. Operator must inspect the exact request, then retry the intended UI action with a fresh observation.",
                    )
                if self._network_completed:
                    result["network_results"] = self._network_completed[:4]
            except Exception as error:
                await asyncio.to_thread(
                    self.store.event,
                    "computer_result",
                    {
                        "action": action.get("action"),
                        "status": "error",
                        "error_type": type(error).__name__,
                        "action_hash": digest,
                    },
                )
                raise
            await asyncio.to_thread(
                self.store.event,
                "computer_result",
                {
                    "action": action.get("action"),
                    "status": result["status"],
                    "action_hash": digest,
                },
            )
            return result

    async def _execute(self, action):
        op = action.get("action")
        if op not in self.ACTIONS:
            raise PermissionError("Unsupported computer action")
        if op == "navigate":
            self.check_url(action["url"])
            # URLs with query data can transmit data; always confirm those.
            if urlsplit(action["url"]).query or urlsplit(action["url"]).fragment:
                pending = await self._approval(
                    {
                        "action": action,
                        "current_url": self._page.url if self._page else "about:blank",
                    }
                )
                if pending:
                    return pending
        await self._start()
        if op == "navigate":
            await self._page.goto(action["url"], wait_until="domcontentloaded")
            return await self._observe()
        self.check_url(self._page.url)
        if op in {"observe", "screenshot"}:
            return await self._observe(screenshot=op == "screenshot")
        current = await self._fingerprint()
        if (
            not self._observation
            or action.get("observation") != current
            or current != self._observation
        ):
            raise PermissionError(
                "Observe the current page first; stale or missing observation"
            )
        if op == "vision_click" and self._vision_observation != current:
            raise PermissionError(
                "Take a current screenshot before using vision coordinates"
            )
        if op == "scroll":
            await self._page.mouse.wheel(0, action["dy"])
            await self._page.evaluate(
                "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
            )
            return await self._observe(screenshot=True)
        if op == "vision_click":
            pixels = await self._page.screenshot(type="png")
            if hashlib.sha256(pixels).hexdigest() != self._vision_hash:
                raise PermissionError(
                    "Screenshot changed; take a fresh screenshot and request approval again"
                )
        pending = await self._approval(
            {
                "action": action,
                "current_url": self._page.url,
                "vision_hash": self._vision_hash if op == "vision_click" else None,
            }
        )
        if pending:
            return pending
        # Re-check after the database round-trip, before enabling even a single input.
        if await self._fingerprint() != current:
            raise PermissionError(
                "Page changed while approval was checked; observe again"
            )
        self._active_action = op
        self._observation = None
        try:
            if op == "vision_click":
                x, y = float(action["x"]), float(action["y"])
                if not (0 <= x < 1280 and 0 <= y < 720):
                    raise ValueError("Coordinates outside screenshot viewport")
                await self._page.mouse.click(x, y)
            else:
                selector = action["selector"]
                if not isinstance(selector, str) or len(selector) > 300:
                    raise ValueError("Invalid selector")
                target = self._page.locator(selector)
                if await target.count() != 1:
                    return {
                        **await self._observe(screenshot=True),
                        "status": "vision_required",
                    }
                field_type = await target.get_attribute("type")
                if field_type in {"password", "file"}:
                    raise PermissionError("Password and file inputs are excluded")
                if op == "click":
                    await target.click()
                elif op == "fill":
                    await target.fill(str(action["text"])[:2000])
            # Drain immediate UI-triggered requests before reporting the outcome.
            # Polling sites may never become idle: an observation still is not proof
            # that a server-side operation succeeded.
            from playwright.async_api import TimeoutError as PlaywrightTimeout

            try:
                await self._page.wait_for_load_state("networkidle", timeout=1500)
            except PlaywrightTimeout:
                pass
            return await self._observe()
        finally:
            self._active_action = None

    async def close(self):
        try:
            if self._context:
                await self._context.close()
            if self._browser and not self.config.cdp_url:
                await self._browser.close()
        finally:
            if self._playwright:
                await self._playwright.stop()
            self._playwright = self._browser = self._context = self._page = None
            self._observation = None
            self._vision_observation = self._vision_hash = None
            self._session = uuid.uuid4().hex
