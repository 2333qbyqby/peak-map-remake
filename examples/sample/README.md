# Sample bundle

This checked-in sample keeps the generated masks, manifests, statistics, and
previews. The generated `terrain.obj` is intentionally omitted to keep the
repository compact.

Rebuild the complete bundle, including `terrain.obj`, with:

```bash
island-baker bake \
  --seed 20260729 \
  --resolution 257 \
  --object-budget 520 \
  --second rainforest \
  --third alpine \
  --route-mode analyze \
  --output examples/sample
```
