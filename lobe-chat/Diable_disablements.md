DevForge Performance Optimizations & Disabled Modules

Purpose
This document records all performance-related disablements done during DevForge development on top of Lobe Chat.
Each change includes:

What was disabled

Why

Exact files touched

How to re-enable later

This ensures fast local development today without permanently breaking upstream features.

1. Telemetry & Observability (OpenTelemetry)
Status

✅ Disabled

Reason

Telemetry adds startup overhead

Not needed for local DevForge development

Causes unnecessary instrumentation compilation

Files Modified
src/instrumentation.node.ts
import { version } from '../package.json';

export async function register() {
  if (process.env.ENABLE_TELEMETRY !== '1') return;

  const { register } = await import('@lobechat/observability-otel/node');
  register({ version });
}

src/instrumentation.ts
export async function register() {
  if (process.env.NEXT_RUNTIME === 'nodejs' && process.env.ENABLE_TELEMETRY) {
    await import('./instrumentation.node');
  }
}

Environment Control
ENABLE_TELEMETRY=0

Re-enable
ENABLE_TELEMETRY=1

2. Marketplace / Discover System (Assistants, Plugins, MCP, Models)
Status

✅ Effectively Disabled (Phase-1 / Phase-2 hybrid)

Reason

Marketplace introduces:

Heavy imports (MarketSDK, model-bank)

GitHub raw fetches during SSR

Slow sitemap generation

DevForge uses locally hosted plugins, not marketplace

3. Discover Store (Client State)
Status

✅ Disabled

Files
src/store/discover/store.ts

Marketplace Zustand store initialization was replaced with stubs.

/**
 * Discover disabled (DevForge mode)
 */
export const useDiscoverStore = () => null as any;
export const getDiscoverStoreState = () => null as any;
export type DiscoverStore = never;

Re-enable

Restore original Zustand store implementation using:

createMCPSlice

createAssistantSlice

createPluginSlice

createModelSlice

createProviderSlice

4. Discover Service (Server)
Status

✅ Disabled by non-usage (imports cut)

Reason

DiscoverService caused:

Marketplace SDK initialization

Network calls to GitHub

Model-bank eager loading

Sitemap explosion

Key Files Where Discover Was Removed / Neutralized
File	Action
src/server/sitemap.ts	Removed dependency on DiscoverService
src/server/routers/lambda/market/index.ts	Marketplace routes unused
src/services/discover.ts	Not used in DevForge runtime
Rule

As long as DiscoverService is not imported, it does not execute

5. Sitemap Generation (Major Performance Win)
Status

✅ Discover-based sitemap routes neutralized

Reason

Sitemap generation was:

Triggering DiscoverService

Fetching identifiers for assistants, plugins, models

Causing 100s of seconds compile time

Files
src/server/sitemap.ts

Before

private discoverService = new DiscoverService();


After

// Discover disabled for DevForge
private discoverService = null;


And all methods that depended on it are no longer invoked in runtime paths.

Re-enable

Restore:

DiscoverService import

getAssistantIdentifiers

getPluginIdentifiers

getModelIdentifiers

6. Changelog Fetching
Status

⚠️ Still enabled (non-blocking)

File

src/server/services/changelog/index.ts

Notes

Still fetches from GitHub

Does not block chat

Can be disabled later if needed

Optional Disable

Gate with feature flag or env:

if (process.env.DISABLE_CHANGELOG === '1') return [];

7. Feature Flags
Status

✅ Kept enabled (safe)

File

src/config/featureFlags/index.ts

Reason

Lightweight

No network calls unless EdgeConfig is enabled

Useful for future re-enablement

Recommended Env Lock
EDGE_CONFIG_ENABLED=false

FEATURE_FLAGS='{
  "market": false,
  "plugins": false,
  "mcp": false,
  "discover": false,
  "rag": false,
  "changelog": false
}'

8. Resulting Performance Impact
Before

/chat compile: 150+ seconds

Heavy SSR blocking

Marketplace calls during dev

After

/chat usable

Faster HMR

Predictable startup

No external network dependency for core chat

9. How to Fully Re-Enable Marketplace Later (Checklist)

Re-enable Discover Store

Restore DiscoverService imports

Restore sitemap discover routes

Enable marketplace TRPC router

Enable feature flags

Set:

FEATURE_FLAGS=...
ENABLE_TELEMETRY=1
EDGE_CONFIG_ENABLED=true

10. DevForge Architecture Intent (Important)

Lobe Chat = UI shell
DevForge Backend = source of truth

Marketplace is optional, not foundational.