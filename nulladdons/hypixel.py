"""
Null's Addons -- Hypixel + Mojang API client (zero third-party dependencies).

Everything here uses only the Python standard library so the tool runs anywhere
with ``python3`` and an internet connection -- no ``pip install`` step.

Endpoints
---------
* ``GET /v2/skyblock/bazaar``          -- public, no key.  The live market.
* ``GET /v2/skyblock/profiles?uuid=``  -- needs a developer API key.  Used to
  personalise: read the player's purse/bank (capital) and unlocked collections
  (which craft recipes they can actually make).
* Mojang name -> UUID lookup, for turning "NullifiedGalaxy" into an account.

Networking notes
----------------
The client honours standard ``HTTPS_PROXY`` / ``HTTP_PROXY`` environment
variables (urllib does this automatically) and, if you are behind a TLS-
inspecting proxy, a custom CA bundle via any of ``NULLADDONS_CA_BUNDLE``,
``REQUESTS_CA_BUNDLE`` or ``SSL_CERT_FILE``.  On a normal machine you need none
of that -- it just works against the public internet.
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.request

API = "https://api.hypixel.net/v2"
BAZAAR_URL = f"{API}/skyblock/bazaar"
PROFILES_URL = f"{API}/skyblock/profiles"
AUCTIONS_URL = f"{API}/skyblock/auctions"
AUCTIONS_ENDED_URL = f"{API}/skyblock/auctions_ended"
PLAYER_AUCTION_URL = f"{API}/skyblock/auction"
PLAYER_URL = f"{API}/player"
RESOURCE_URL = f"{API}/resources/skyblock"
MOJANG_URL = "https://api.mojang.com/users/profiles/minecraft/"

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".nulladdons", "cache")
DEFAULT_BAZAAR_TTL = 60  # seconds; the API itself refreshes about this often
ENDED_TTL = 45           # auctions_ended refreshes ~every minute
RESOURCE_TTL = 24 * 3600  # skill/collection tables barely change
UUID_TTL = 7 * 24 * 3600  # names rarely change


class HypixelError(RuntimeError):
    """Raised when an API call fails in a way the caller should hear about."""


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    for var in ("NULLADDONS_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
        bundle = os.environ.get(var)
        if bundle and os.path.exists(bundle):
            try:
                ctx.load_verify_locations(bundle)
            except ssl.SSLError:
                pass
    return ctx


def _get_json(url: str, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "NullsAddons/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Surface the API's own error message where possible.
        body = ""
        try:
            body = exc.read().decode("utf-8")
            cause = json.loads(body).get("cause", body)
        except Exception:
            cause = body or str(exc)
        raise HypixelError(f"HTTP {exc.code} from {url}: {cause}") from exc
    except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
        raise HypixelError(f"Network error contacting {url}: {exc}") from exc


def _cache_path(name: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, name)


def _read_cache(name: str, ttl: float) -> dict | None:
    path = _cache_path(name)
    if not os.path.exists(path):
        return None
    if time.time() - os.path.getmtime(path) > ttl:
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _write_cache(name: str, payload: dict) -> None:
    try:
        with open(_cache_path(name), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
    except OSError:
        pass


# --- Public API -------------------------------------------------------------

def fetch_bazaar(ttl: float = DEFAULT_BAZAAR_TTL, use_cache: bool = True,
                 offline_path: str | None = None) -> dict:
    """
    Return the raw Bazaar payload.

    * ``offline_path`` -- load a saved snapshot instead of the network (great for
      demos, tests, or a no-internet session).
    * otherwise served from a short-lived disk cache, falling back to the API.
    """
    if offline_path:
        with open(offline_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    if use_cache:
        cached = _read_cache("bazaar.json", ttl)
        if cached is not None:
            return cached

    payload = _get_json(BAZAAR_URL)
    if not payload.get("success"):
        raise HypixelError(f"Bazaar API returned success=false: {payload.get('cause')}")
    _write_cache("bazaar.json", payload)
    return payload


def resolve_uuid(username: str, use_cache: bool = True) -> str | None:
    """Resolve a Minecraft username to its dashless UUID, or ``None``."""
    key = f"uuid_{username.lower()}.json"
    if use_cache:
        cached = _read_cache(key, UUID_TTL)
        if cached and cached.get("id"):
            return cached["id"]
    try:
        data = _get_json(MOJANG_URL + username)
    except HypixelError:
        return None
    if data.get("id"):
        _write_cache(key, data)
        return data["id"]
    return None


def fetch_profiles(uuid: str, api_key: str) -> dict | None:
    """
    Fetch a player's SkyBlock profiles (needs a developer API key from
    developer.hypixel.net).  Returns the raw payload or ``None`` on any failure
    -- personalisation is best-effort and must never crash the tool.
    """
    if not api_key:
        return None
    url = f"{PROFILES_URL}?uuid={uuid}&key={api_key}"
    try:
        payload = _get_json(url)
    except HypixelError:
        return None
    return payload if payload.get("success") else None


def fetch_auctions_ended(ttl: float = ENDED_TTL, use_cache: bool = True) -> list[dict]:
    """Recently sold auctions (public, no key). ~2 min rolling window."""
    if use_cache:
        cached = _read_cache("auctions_ended.json", ttl)
        if cached is not None:
            return cached.get("auctions", [])
    payload = _get_json(AUCTIONS_ENDED_URL)
    if payload.get("success"):
        _write_cache("auctions_ended.json", payload)
    return payload.get("auctions", [])


def fetch_auctions_page(page: int = 0, ttl: float = ENDED_TTL,
                        use_cache: bool = True) -> dict:
    """One page (~1000) of active auctions (public). ``totalPages`` says how many."""
    name = f"auctions_p{page}.json"
    if use_cache:
        cached = _read_cache(name, ttl)
        if cached is not None:
            return cached
    payload = _get_json(f"{AUCTIONS_URL}?page={page}")
    if payload.get("success"):
        _write_cache(name, payload)
    return payload


def fetch_player_auctions(uuid: str, api_key: str) -> list[dict]:
    """A specific player's own auctions (needs key). Empty list on failure."""
    if not api_key:
        return []
    try:
        payload = _get_json(f"{PLAYER_AUCTION_URL}?player={uuid}&key={api_key}")
    except HypixelError:
        return []
    return payload.get("auctions", []) if payload.get("success") else []


def fetch_player(uuid: str, api_key: str) -> dict | None:
    """General Hypixel player object (needs key)."""
    if not api_key:
        return None
    try:
        payload = _get_json(f"{PLAYER_URL}?uuid={uuid}&key={api_key}")
    except HypixelError:
        return None
    return payload.get("player") if payload.get("success") else None


def fetch_resource(name: str, ttl: float = RESOURCE_TTL,
                   use_cache: bool = True) -> dict | None:
    """Public reference data, e.g. ``skills`` or ``collections`` (no key)."""
    cache_name = f"resource_{name}.json"
    if use_cache:
        cached = _read_cache(cache_name, ttl)
        if cached is not None:
            return cached
    try:
        payload = _get_json(f"{RESOURCE_URL}/{name}")
    except HypixelError:
        return None
    if payload.get("success"):
        _write_cache(cache_name, payload)
        return payload
    return None
