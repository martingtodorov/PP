"""Shared test plumbing: the backend on the import path, the .env loaded and ONE event loop.

The motor client is created once, when `server` is imported, and belongs to the loop that first
touches it — so every test file in the suite must drive the same loop. Use `from conftest import run`
instead of `asyncio.run`.
"""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).parent))     # so a test file can `from conftest import run`
load_dotenv(BACKEND / ".env")

LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)
run = LOOP.run_until_complete
