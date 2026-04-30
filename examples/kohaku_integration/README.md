# Kohaku + e_AI v2 Integration Demo

Demonstrates how e_AI v2's ops advisor middleware wraps a Kohaku plugin to add pre-submission risk analysis.

## How it works

```
User intent → Kohaku plugin (Railgun) → OpsAdvisor middleware → Risk check
                                              ↓
                                        Profile-based analysis
                                              ↓
                                   ✅ Pass / ⚠️ Warning / ⛔ Block
```

The middleware intercepts `prepareShield` and `prepareUnshield` calls, runs the stealth address ops analyzer, and either proceeds, warns, or blocks.

## Run

```bash
cd examples/kohaku_integration
npm install
npx tsx demo.ts
```

## Files

- `demo.ts` — Runnable demo with 3 scenarios (good practice, bad practice, self-send)
- `analyzer.ts` — TypeScript port of stealth address ops analyzer
- `kohaku-middleware.ts` — Generic middleware that wraps any Kohaku PluginInstance
- `types.ts` — Shared types

## Integration with real Kohaku

Replace `mockRailgunPlugin` with a real `@kohaku-eth/railgun` instance:

```ts
import { createRailgun } from '@kohaku-eth/railgun';
import { withOpsAdvisor } from './kohaku-middleware';

const plugin = await createRailgun(host, params);
const advised = withOpsAdvisor(plugin, 'domains/stealth_address_ops/profile.json');

// Now all shield/unshield/transfer calls get risk-checked
const op = await advised.prepareUnshield(asset, toAddress);
```
