# RedisCluster MCP Server (scaffold)

**This is a scaffold, not a working server.** It was generated
by `ai-platform-generator` and is intended as a starting point.
Tool implementations raise `NotImplementedError` until you fill
them in.

## Source CRD

- **Group:** `cache.cnoe.io`
- **Version:** `v1alpha1`
- **Kind:** `RedisCluster`
- **Intent:** A Redis cluster with configurable memory, port and persistence.

## Tools exposed

- `get_memoryGiB`
- `get_persistence`
- `get_port`

## Running

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python server.py
```

The server speaks MCP over stdio by default.

## Next steps

1. Replace each tool body with real logic against your
   `rediscluster` controller / API.
2. Add authentication / authorisation as appropriate.
3. Wire the server into your MCP client of choice.
