package com.nullifieduniverse.nulladdons.core.telemetry;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Map;

/**
 * A bounded, thread-safe buffer of telemetry events that serialises to a compact
 * JSON payload with no third-party dependency (so it unit-tests standalone).
 *
 * <p>Design notes for privacy &amp; performance:
 * <ul>
 *   <li>Bounded: when full it drops the <em>oldest</em> event, so it can never
 *       grow without bound even if the network is down.</li>
 *   <li>The payload wraps events with an <em>anonymous</em> install id (a random
 *       UUID, not the player's account) plus the mod and Minecraft versions —
 *       nothing that identifies a person.</li>
 *   <li>All strings are JSON-escaped; numbers/booleans are emitted raw.</li>
 * </ul>
 */
public final class TelemetryBuffer {
    private final int capacity;
    private final Deque<TelemetryEvent> queue = new ArrayDeque<TelemetryEvent>();

    public TelemetryBuffer(int capacity) {
        this.capacity = Math.max(1, capacity);
    }

    public synchronized void add(TelemetryEvent event) {
        if (event == null) return;
        while (queue.size() >= capacity) queue.pollFirst();  // drop oldest
        queue.addLast(event);
    }

    public synchronized int size() { return queue.size(); }

    public synchronized boolean isEmpty() { return queue.isEmpty(); }

    /** Serialise and clear. Returns null when empty. */
    public synchronized String drainToJson(String anonId, String modVersion, String mcVersion) {
        if (queue.isEmpty()) return null;
        StringBuilder sb = new StringBuilder(256);
        sb.append('{');
        str(sb, "anon_id", anonId).append(',');
        str(sb, "mod", modVersion).append(',');
        str(sb, "mc", mcVersion).append(',');
        sb.append("\"sent_at\":").append(System.currentTimeMillis()).append(',');
        sb.append("\"events\":[");
        boolean first = true;
        for (TelemetryEvent e : queue) {
            if (!first) sb.append(',');
            first = false;
            eventJson(sb, e);
        }
        sb.append("]}");
        queue.clear();
        return sb.toString();
    }

    private static void eventJson(StringBuilder sb, TelemetryEvent e) {
        sb.append('{');
        str(sb, "name", e.name).append(',');
        sb.append("\"ts\":").append(e.ts);
        for (Map.Entry<String, Object> en : e.fields.entrySet()) {
            sb.append(',');
            value(sb.append('"').append(escape(en.getKey())).append("\":"), en.getValue());
        }
        sb.append('}');
    }

    private static StringBuilder str(StringBuilder sb, String key, String val) {
        return sb.append('"').append(escape(key)).append("\":\"")
                .append(escape(val == null ? "" : val)).append('"');
    }

    private static void value(StringBuilder sb, Object v) {
        if (v instanceof Number || v instanceof Boolean) {
            sb.append(String.valueOf(v));
        } else {
            sb.append('"').append(escape(v == null ? "" : v.toString())).append('"');
        }
    }

    public static String escape(String s) {
        StringBuilder out = new StringBuilder(s.length() + 8);
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"':  out.append("\\\""); break;
                case '\\': out.append("\\\\"); break;
                case '\n': out.append("\\n"); break;
                case '\r': out.append("\\r"); break;
                case '\t': out.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else {
                        out.append(c);
                    }
            }
        }
        return out.toString();
    }
}
