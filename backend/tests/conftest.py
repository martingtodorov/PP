"""One event loop for the whole test session — motor binds its client to the loop that is current
when `server` is imported, so every test file must drive that same loop."""
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
