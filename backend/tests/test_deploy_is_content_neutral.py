"""A deploy must not change one piece of dynamic content, and the analytics tab must be warm.

The checks are on the source and on the live database — the content-touching migrations only ever
run once, and the analytics answer comes from a cache the background loop refills every 5 minutes.
"""
import os
import time
from pathlib import Path

import pytest
from dotenv import load_dotenv
from pymongo import MongoClient

BACKEND = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND / ".env")
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
SRC = (BACKEND / "server.py").read_text()


def test_content_migrations_run_through_run_once():
    assert 'await run_once("adopt_imported_redirects", adopt_imported_redirects)' in SRC
    assert 'await run_once("restore_body_headings", lambda: restore_headings(db, storage))' in SRC
    assert 'await run_once("drop_page_aliases", drop_aliases)' in SRC


def test_the_migrations_are_recorded_so_a_restart_skips_them():
    done = {d["name"] for d in DB.migrations.find({}, {"_id": 0, "name": 1})}
    assert {"adopt_imported_redirects", "restore_body_headings", "drop_page_aliases"} <= done


def test_the_catalog_import_is_the_only_db_write_of_a_deploy_and_is_opt_in():
    play = (BACKEND.parent / "deploy/hetzner/ansible/playbooks/deploy_backend.yml").read_text()
    assert "matrixify_import.py" in play
    assert "when: run_catalog_import | default(false) | bool" in play


def test_sitemaps_are_built_from_the_database_not_from_files():
    assert "async def _sitemap_groups(request: Request):" in SRC
    assert "sitemap" not in os.listdir(BACKEND)


@pytest.mark.parametrize("rng", ["today", "7d", "30d"])
def test_the_warm_loop_precomputes_the_ranges_the_owner_opens(rng):
    import server

    assert rng in server.ANALYTICS_WARM_RANGES
    assert server.ANALYTICS_WARM_SEC == 300


def test_the_endpoint_serves_the_cache_and_keeps_live_fresh():
    assert "payload = await _analytics_cached(range, date_from, date_to, fresh=fresh)" in SRC
    assert "return {**payload, **await _analytics_live()}" in SRC
    assert '"live": len(live), "live_geo": await _geo_breakdown(live_start, now)' in SRC


def test_a_cached_read_is_instant_and_reports_its_age():
    import asyncio
    import server

    asyncio.get_event_loop_policy().new_event_loop()
    server._analytics_cache.clear()
    run = asyncio.new_event_loop().run_until_complete
    t0 = time.time()
    first = run(server._analytics_cached("today"))
    cold = time.time() - t0
    t0 = time.time()
    second = run(server._analytics_cached("today"))
    warm = time.time() - t0
    assert first["current"]["sessions"] == second["current"]["sessions"]
    assert second["cached_at"] == first["cached_at"]
    assert warm <= cold
    assert warm < 0.05
    assert "live" not in second        # the live counters are added by the endpoint, never cached
