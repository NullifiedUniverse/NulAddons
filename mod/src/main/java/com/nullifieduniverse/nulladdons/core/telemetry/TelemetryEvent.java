package com.nullifieduniverse.nulladdons.core.telemetry;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * A single, anonymous telemetry data point — a short name plus a few scalar
 * fields. By convention it carries only aggregate/usage numbers and never any
 * personal data (no username, UUID, IGN, coin balances, chat, etc.).
 */
public final class TelemetryEvent {
    public final String name;
    public final long ts;
    public final Map<String, Object> fields = new LinkedHashMap<String, Object>();

    public TelemetryEvent(String name) {
        this.name = name;
        this.ts = System.currentTimeMillis();
    }

    public TelemetryEvent put(String key, Object value) {
        fields.put(key, value);
        return this;
    }
}
