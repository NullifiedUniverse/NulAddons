package com.nullifieduniverse.nulladdons.fabric;

import com.nullifieduniverse.nulladdons.core.telemetry.TelemetryBuffer;
import com.nullifieduniverse.nulladdons.core.telemetry.TelemetryEvent;
import net.fabricmc.loader.api.FabricLoader;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Opt-in, anonymous telemetry &amp; feedback.
 *
 * <p><b>Privacy by default.</b> It is <em>off</em> unless you both enable it
 * ({@code /nulladdons telemetry on}) and set an endpoint. It only ever sends a
 * random install id (not your account), the mod &amp; Minecraft versions, which
 * features are enabled, and aggregate counters (tooltips shown, fetch latency /
 * error counts). No username, UUID, IGN, coins, chat or location — the buffer
 * literally has no field for them. Everything is batched and sent fire-and-forget
 * on a background thread, so it never touches the game thread.
 */
public final class Telemetry {
    private static final Telemetry INSTANCE = new Telemetry();
    public static Telemetry get() { return INSTANCE; }

    private final TelemetryBuffer buffer = new TelemetryBuffer(200);
    private final HttpClient http = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(8)).build();

    private final AtomicLong tooltips = new AtomicLong();
    private final AtomicLong fetchOk = new AtomicLong();
    private final AtomicLong fetchErr = new AtomicLong();
    private final AtomicLong fetchMsTotal = new AtomicLong();

    private ScheduledExecutorService scheduler;
    private String modVersion = "1.0.0";
    private String mcVersion = "unknown";

    private Telemetry() {}

    public void init() {
        mcVersion = version("minecraft", "unknown");
        modVersion = version("nulladdons", "1.0.0");
        if (NullsConfig.telemetryEnabled) {
            buffer.add(new TelemetryEvent("session_start")
                    .put("hud", NullsConfig.hudEnabled)
                    .put("tooltip", NullsConfig.tooltipEnabled)
                    .put("craft", NullsConfig.showCraft)
                    .put("conservative", NullsConfig.conservative));
        }
        scheduler = Executors.newSingleThreadScheduledExecutor(new ThreadFactory() {
            public Thread newThread(Runnable r) {
                Thread t = new Thread(r, "NullsAddons-Telemetry");
                t.setDaemon(true);
                t.setPriority(Thread.MIN_PRIORITY);
                return t;
            }
        });
        scheduler.scheduleWithFixedDelay(this::heartbeatAndFlush, 5, 5, TimeUnit.MINUTES);
    }

    // --- lightweight counters (called off the render path) ------------------

    public void onTooltip() { tooltips.incrementAndGet(); }

    public void onFetch(long ms, boolean ok) {
        if (ok) { fetchOk.incrementAndGet(); fetchMsTotal.addAndGet(ms); }
        else { fetchErr.incrementAndGet(); }
    }

    // --- feedback: user-initiated, so it sends when an endpoint is set -------

    public boolean feedback(String message) {
        if (!endpointSet()) return false;
        TelemetryBuffer one = new TelemetryBuffer(1);
        one.add(new TelemetryEvent("feedback").put("message", message));
        sendAsync(one.drainToJson(NullsConfig.anonId, modVersion, mcVersion));
        return true;
    }

    // --- batching / flush ---------------------------------------------------

    private void heartbeatAndFlush() {
        try {
            if (NullsConfig.telemetryEnabled) {
                long ok = fetchOk.getAndSet(0);
                long err = fetchErr.getAndSet(0);
                long ms = fetchMsTotal.getAndSet(0);
                long tt = tooltips.getAndSet(0);
                buffer.add(new TelemetryEvent("heartbeat")
                        .put("hud", NullsConfig.hudEnabled)
                        .put("tooltip", NullsConfig.tooltipEnabled)
                        .put("craft", NullsConfig.showCraft)
                        .put("tooltips_shown", tt)
                        .put("fetch_ok", ok)
                        .put("fetch_err", err)
                        .put("fetch_ms_avg", ok > 0 ? ms / ok : 0));
            }
            flush();
        } catch (Throwable ignored) {
        }
    }

    public void flush() {
        if (!NullsConfig.telemetryEnabled) return;
        sendAsync(buffer.drainToJson(NullsConfig.anonId, modVersion, mcVersion));
    }

    public void flushBlocking() {
        if (!NullsConfig.telemetryEnabled || !endpointSet()) return;
        String payload = buffer.drainToJson(NullsConfig.anonId, modVersion, mcVersion);
        if (payload == null) return;
        try {
            http.send(request(payload), HttpResponse.BodyHandlers.discarding());
        } catch (Exception ignored) {
        }
    }

    private void sendAsync(String payload) {
        if (payload == null || !endpointSet()) return;
        try {
            http.sendAsync(request(payload), HttpResponse.BodyHandlers.discarding())
                    .exceptionally(t -> null);   // fire-and-forget
        } catch (Exception ignored) {
        }
    }

    private HttpRequest request(String payload) {
        return HttpRequest.newBuilder(URI.create(NullsConfig.telemetryEndpoint))
                .header("Content-Type", "application/json")
                .header("User-Agent", "NullsAddons-Telemetry/1.0")
                .timeout(Duration.ofSeconds(10))
                .POST(HttpRequest.BodyPublishers.ofString(payload)).build();
    }

    private boolean endpointSet() {
        return NullsConfig.telemetryEndpoint != null
                && !NullsConfig.telemetryEndpoint.trim().isEmpty();
    }

    private static String version(String modId, String fallback) {
        try {
            return FabricLoader.getInstance().getModContainer(modId)
                    .map(c -> c.getMetadata().getVersion().getFriendlyString())
                    .orElse(fallback);
        } catch (Throwable t) {
            return fallback;
        }
    }
}
