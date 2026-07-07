"""
Null's Addons -- a tiny, self-contained NBT reader.

SkyBlock stores a player's inventories (including the accessory / talisman bag)
as a gzipped, base64-encoded NBT blob inside the profile API response.  To
personalise the Magical Power planner we only need one thing out of it: the set
of accessory ids the player already owns, so we don't tell them to buy something
twice.

This is a minimal big-endian NBT parser (stdlib only) plus a helper that pulls
every ``ExtraAttributes.id`` out of the decoded tree.  It is used strictly
best-effort: any decode failure returns an empty set and the planner falls back
to the account's configured ``owned_families``.
"""

from __future__ import annotations

import base64
import gzip
import struct

# NBT tag ids
_TAG_END = 0
_TAG_BYTE = 1
_TAG_SHORT = 2
_TAG_INT = 3
_TAG_LONG = 4
_TAG_FLOAT = 5
_TAG_DOUBLE = 6
_TAG_BYTE_ARRAY = 7
_TAG_STRING = 8
_TAG_LIST = 9
_TAG_COMPOUND = 10
_TAG_INT_ARRAY = 11
_TAG_LONG_ARRAY = 12


class _Reader:
    def __init__(self, data: bytes):
        self.d = data
        self.i = 0

    def _take(self, n: int) -> bytes:
        chunk = self.d[self.i:self.i + n]
        if len(chunk) != n:
            raise ValueError("truncated NBT")
        self.i += n
        return chunk

    def u1(self) -> int:
        return self._take(1)[0]

    def i2(self) -> int:
        return struct.unpack(">h", self._take(2))[0]

    def u2(self) -> int:
        return struct.unpack(">H", self._take(2))[0]

    def i4(self) -> int:
        return struct.unpack(">i", self._take(4))[0]

    def i8(self) -> int:
        return struct.unpack(">q", self._take(8))[0]

    def f4(self) -> float:
        return struct.unpack(">f", self._take(4))[0]

    def f8(self) -> float:
        return struct.unpack(">d", self._take(8))[0]

    def string(self) -> str:
        length = self.u2()
        return self._take(length).decode("utf-8", errors="replace")

    def payload(self, tag: int):
        if tag == _TAG_BYTE:
            return self.u1()
        if tag == _TAG_SHORT:
            return self.i2()
        if tag == _TAG_INT:
            return self.i4()
        if tag == _TAG_LONG:
            return self.i8()
        if tag == _TAG_FLOAT:
            return self.f4()
        if tag == _TAG_DOUBLE:
            return self.f8()
        if tag == _TAG_BYTE_ARRAY:
            return self._take(self.i4())
        if tag == _TAG_STRING:
            return self.string()
        if tag == _TAG_LIST:
            item_type = self.u1()
            length = self.i4()
            return [self.payload(item_type) for _ in range(max(0, length))]
        if tag == _TAG_COMPOUND:
            out: dict = {}
            while True:
                child = self.u1()
                if child == _TAG_END:
                    break
                name = self.string()
                out[name] = self.payload(child)
            return out
        if tag == _TAG_INT_ARRAY:
            return [self.i4() for _ in range(self.i4())]
        if tag == _TAG_LONG_ARRAY:
            return [self.i8() for _ in range(self.i4())]
        raise ValueError(f"unknown NBT tag {tag}")


def parse(data: bytes):
    """Decode raw (optionally gzipped) NBT bytes into Python structures."""
    try:
        data = gzip.decompress(data)
    except OSError:
        pass  # already decompressed
    r = _Reader(data)
    root_tag = r.u1()
    if root_tag == _TAG_END:
        return {}
    r.string()  # root name (ignored)
    return r.payload(root_tag)


def parse_b64(b64: str):
    """Decode a base64 (gzipped) NBT string into Python structures, or {}."""
    try:
        return parse(base64.b64decode(b64))
    except (ValueError, OSError, struct.error, base64.binascii.Error):
        return {}


def _walk_ids(node, out: set[str]) -> None:
    if isinstance(node, dict):
        extra = node.get("ExtraAttributes")
        if isinstance(extra, dict) and isinstance(extra.get("id"), str):
            out.add(extra["id"])
        for value in node.values():
            _walk_ids(value, out)
    elif isinstance(node, list):
        for item in node:
            _walk_ids(item, out)


def item_ids_from_bag(bag_field) -> set[str]:
    """
    Extract owned item ids from a profile bag field, which may be a dict with a
    base64 ``data`` string, or the raw base64 string itself.  Returns an empty
    set on any problem -- callers treat that as "unknown, use config".
    """
    try:
        if isinstance(bag_field, dict):
            bag_field = bag_field.get("data")
        if not isinstance(bag_field, str):
            return set()
        raw = base64.b64decode(bag_field)
        root = parse(raw)
        ids: set[str] = set()
        _walk_ids(root, ids)
        return ids
    except (ValueError, OSError, struct.error, base64.binascii.Error):
        return set()
