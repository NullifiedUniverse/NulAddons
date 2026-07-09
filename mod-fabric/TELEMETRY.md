# Null's Addons — Telemetry & Feedback (transparency)

Telemetry is **opt‑in and off by default**. Nothing leaves your machine unless
you *both* turn it on **and** configure an endpoint. This document says exactly
what it does.

## How to control it

* Enable:  `/nulladdons telemetry on`
* Disable: `/nulladdons telemetry off`
* Status:  `/nulladdons telemetry status`
* Or edit `config/nulladdons.json`: `telemetryEnabled`, `telemetryEndpoint`.

It only sends anything if `telemetryEnabled` is `true` **and**
`telemetryEndpoint` is a URL you set (there is no default endpoint — the mod
ships pointing nowhere).

## What is collected (when enabled)

Anonymous, aggregate, non‑personal data only:

* A random **install id** (`anonId`, a UUID generated locally) — **not** your
  Minecraft account, name, or UUID.
* The **mod version** and **Minecraft version**.
* Which **features are enabled** (HUD / tooltips / craft / conservative).
* **Aggregate counters** per 5‑minute heartbeat: number of tooltips shown, and
  Bazaar fetch success/error counts and average latency (to spot API issues).
* A `session_start` event when you launch with telemetry on.

## What is NEVER collected

No username, no account UUID, no IGN, no coin/purse/bank balances, no inventory,
no chat, no location, no IP‑derived data, no per‑item history — the data model
has no field for any of it. See
`core/telemetry/TelemetryBuffer.java`: the payload is only
`{anon_id, mod, mc, sent_at, events:[…]}`.

## Feedback

`/nulladdons feedback <your message>` sends just that message (plus the anon id
and versions) to the endpoint. It's user‑initiated, so it sends whenever an
endpoint is configured. Don't type anything private into it.

## How it's sent

Batched and fire‑and‑forget on a low‑priority background thread using the JDK
HTTP client — it never blocks the game, and a failed send is silently dropped
(the buffer is bounded and discards oldest first).

## Running your own endpoint

Point `telemetryEndpoint` at any server that accepts a `POST` of
`application/json`. Example payload:

```json
{ "anon_id": "…", "mod": "1.0.0", "mc": "1.21.4", "sent_at": 1730000000000,
  "events": [ { "name": "heartbeat", "ts": 1730000000000,
               "hud": true, "tooltips_shown": 12, "fetch_ok": 5, "fetch_err": 0,
               "fetch_ms_avg": 210 } ] }
```
