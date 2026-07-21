import asyncio
import aiohttp
import json
import ssl
import certifi


# Apple shards the Hide My Email backend across per-account "partitions"
# (e.g. p68, p174, ...). The correct one for *this* account is discovered via
# setup/ws/1/validate — the same call icloud.com's web client makes — rather
# than assumed, since a wrong/stale partition can silently return an
# incomplete alias list instead of erroring.
SETUP_URL = "https://setup.icloud.com/setup/ws/1"
DEFAULT_MAIL_HOST = "https://p68-maildomainws.icloud.com"


class HideMyEmail:
    params = {
        "clientBuildNumber": "2536Project32",
        "clientMasteringNumber": "2536B20",
        "clientId": "",
        "dsid": "", # Directory Services Identifier (DSID) is a method of identifying AppleID accounts
    }

    def __init__(self, label: str = "", cookies: str = ""):
        """Initializes the HideMyEmail class.

        Args:
            label (str)     Fallback label used only when reserve_email() is
                            called without a per-alias label. Real callers pass
                            a fresh, realistic label for each alias.
            cookies (str)   Cookie string to be used with requests. Required for authorization.
        """
        # Fallback label; per-alias labels are normally passed to reserve_email().
        self.label = label

        # Cookie string to be used with requests. Required for authorization.
        self.cookies = cookies

        # Overwritten with the real per-account host once resolved in
        # __aenter__; this hardcoded partition is only a last-resort fallback.
        self.base_url_v1 = f"{DEFAULT_MAIL_HOST}/v1/hme"
        self.base_url_v2 = f"{DEFAULT_MAIL_HOST}/v2/hme"
        self.mail_host_resolved = False

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(ssl_context=ssl.create_default_context(cafile=certifi.where()))
        self.s = aiohttp.ClientSession(
            headers={
                "Connection": "keep-alive",
                "Pragma": "no-cache",
                "Cache-Control": "no-cache",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
                "Content-Type": "text/plain",
                "Accept": "*/*",
                "Sec-GPC": "1",
                "Origin": "https://www.icloud.com",
                "Sec-Fetch-Site": "same-site",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Dest": "empty",
                "Referer": "https://www.icloud.com/",
                "Accept-Language": "en-US,en-GB;q=0.9,en;q=0.8,cs;q=0.7",
                "sec-ch-ua": '"Brave";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
                "Cookie": self.__cookies.strip(),
            },
            timeout=aiohttp.ClientTimeout(total=10),
            connector=connector,
        )

        await self._resolve_mail_host()

        return self

    async def __aexit__(self, exc_t, exc_v, exc_tb):
        await self.s.close()

    async def _resolve_mail_host(self) -> None:
        """Discover this account's real premiummailsettings host.

        Mirrors icloud.com's own web client: POST setup/ws/1/validate with
        the current session cookies and read webservices.premiummailsettings.
        Leaves the DEFAULT_MAIL_HOST fallback in place if this fails for any
        reason (network error, unexpected schema, stale cookie).
        """
        try:
            async with self.s.post(f"{SETUP_URL}/validate") as resp:
                if resp.status != 200:
                    return
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, ValueError):
            return

        webservices = data.get("webservices") if isinstance(data, dict) else None
        service = (
            webservices.get("premiummailsettings")
            if isinstance(webservices, dict)
            else None
        )
        host = service.get("url") if isinstance(service, dict) else None
        if not host or not isinstance(host, str):
            return

        host = host.rstrip("/")
        self.base_url_v1 = f"{host}/v1/hme"
        self.base_url_v2 = f"{host}/v2/hme"
        self.mail_host_resolved = True

    @property
    def cookies(self) -> str:
        return self.__cookies

    @cookies.setter
    def cookies(self, cookies: str):
        # remove new lines/whitespace for security reasons
        self.__cookies = cookies.strip()

    async def _request_json(self, method: str, url: str, **kwargs) -> dict:
        try:
            async with self.s.request(method, url, **kwargs) as resp:
                if resp.status == 429:
                    return {"error": 1, "reason": "Apple rate limit reached (HTTP 429)"}

                body = await resp.text()
                if not body.strip():
                    return {
                        "error": 1,
                        "reason": f"Invalid Apple response (HTTP {resp.status}: empty body)",
                    }

                try:
                    return json.loads(body)
                except json.JSONDecodeError:
                    return {
                        "error": 1,
                        "reason": (
                            "Invalid Apple response "
                            f"(HTTP {resp.status}: expected JSON body)"
                        ),
                    }
        except asyncio.TimeoutError:
            return {"error": 1, "reason": "Request timed out"}
        except aiohttp.ClientError as e:
            return {"error": 1, "reason": f"Network error: {e}"}
        except Exception as e:
            return {"error": 1, "reason": str(e)}

    async def generate_email(self) -> dict:
        """Generates an email"""
        return await self._request_json(
            "POST",
            f"{self.base_url_v1}/generate",
            params=self.params,
            json={"langCode": "en-us"},
        )

    async def reserve_email(
        self, email: str, label: str | None = None, note: str = ""
    ) -> dict:
        """Reserves an email and registers it for forwarding.

        A per-alias ``label`` should be passed so aliases don't all share one
        fingerprint; ``note`` defaults to empty, matching a normal manual
        creation on icloud.com.
        """
        payload = {
            "hme": email,
            "label": label if label is not None else self.label,
            "note": note,
        }
        return await self._request_json(
            "POST",
            f"{self.base_url_v1}/reserve",
            params=self.params,
            json=payload,
        )

    async def list_email(self) -> dict:
        """List all HME"""
        return await self._request_json(
            "GET",
            f"{self.base_url_v2}/list",
            params=self.params,
        )

    async def deactivate_email(self, anonymous_id: str) -> dict:
        """Deactivate a Hide My Email alias (stops forwarding).

        ``anonymous_id`` is the ``anonymousId`` field returned for the alias by
        ``list_email()``. Reversible via ``reactivate_email()``.
        """
        return await self._request_json(
            "POST",
            f"{self.base_url_v1}/deactivate",
            params=self.params,
            json={"anonymousId": anonymous_id},
        )

    async def reactivate_email(self, anonymous_id: str) -> dict:
        """Re-activate a previously deactivated Hide My Email alias."""
        return await self._request_json(
            "POST",
            f"{self.base_url_v1}/reactivate",
            params=self.params,
            json={"anonymousId": anonymous_id},
        )
