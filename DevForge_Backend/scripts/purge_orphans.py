"""
Purge orphaned RAG chunks from pgvector.

An orphan is a chunk whose file_id has no corresponding `file:<id>` key in Redis
(meaning the file was deleted from Redis but not from pgvector, or Redis was flushed).

Usage (inside devforge-api container):
    docker cp scripts/purge_orphans.py devforge-api:/tmp/
    docker exec devforge-api python3 /tmp/purge_orphans.py            # dry run
    docker exec devforge-api python3 /tmp/purge_orphans.py --delete   # live delete
"""
import asyncio
import argparse
import asyncpg
import redis.asyncio as aioredis

POSTGRES_URL = "postgresql://devforge:devforge123@postgres:5432/devforge"
REDIS_URL = "redis://redis:6379"


async def run(dry_run: bool) -> None:
    pg = await asyncpg.connect(POSTGRES_URL)
    r = aioredis.from_url(REDIS_URL, decode_responses=True)

    rows = await pg.fetch("""
        SELECT DISTINCT metadata->>'file_id' as fid, tenant_id,
            COUNT(*) OVER (PARTITION BY metadata->>'file_id') as chunk_count
        FROM rag_vectors
        WHERE metadata->>'file_id' IS NOT NULL
    """)

    seen: set[str] = set()
    orphans: list[tuple[str, str, int]] = []

    for row in rows:
        fid = row["fid"]
        if fid in seen:
            continue
        seen.add(fid)
        has_redis = bool(await r.exists(f"file:{fid}"))
        status = "OK" if has_redis else "ORPHAN"
        print(f"{fid}  tenant={row['tenant_id']}  chunks={row['chunk_count']}  {status}")
        if not has_redis:
            orphans.append((fid, row["tenant_id"], row["chunk_count"]))

    total_chunks = sum(c for _, _, c in orphans)
    print(f"\nOrphans: {len(orphans)} file_ids, {total_chunks} chunks")

    if not orphans:
        print("Nothing to delete.")
    elif dry_run:
        print("DRY RUN — pass --delete to remove them.")
    else:
        result = await pg.execute(
            "DELETE FROM rag_vectors WHERE metadata->>'file_id' = ANY($1::text[])",
            [fid for fid, _, _ in orphans],
        )
        remaining = await pg.fetchval("SELECT COUNT(*) FROM rag_vectors")
        print(f"Deleted: {result} | Remaining chunks: {remaining}")
        print("Remember to restart the API container to clear the in-memory BM25 index.")

    await pg.close()
    await r.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete", action="store_true", help="Actually delete orphans (default: dry run)")
    args = parser.parse_args()
    asyncio.run(run(dry_run=not args.delete))
