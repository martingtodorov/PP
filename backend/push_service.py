"""Web Push (VAPID) notifications for the admin — new orders and contact requests."""

import json
import logging
import os
from typing import Any, Dict, List

from pywebpush import webpush, WebPushException
from starlette.concurrency import run_in_threadpool

log = logging.getLogger("push")


def _status(exc: WebPushException):
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None)


def _send_one(sub: Dict[str, Any], payload: Dict[str, Any]) -> int:
    """Returns the HTTP status-ish result: 0 = ok, 410/404 = gone, -1 = other failure."""
    try:
        webpush(
            subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]},
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=os.environ["VAPID_PRIVATE_KEY"],
            vapid_claims={"sub": os.environ["VAPID_SUBJECT"]},
            ttl=600,
        )
        return 0
    except WebPushException as exc:
        code = _status(exc)
        if code in (404, 410):
            return code
        log.warning("Web push failed for %s: %s", sub.get("endpoint", "")[:60], exc)
        return -1


async def send_to_subscriptions(subs: List[Dict[str, Any]], payload: Dict[str, Any]) -> Dict[str, List[str]]:
    sent, gone, failed = [], [], []
    for sub in subs:
        result = await run_in_threadpool(_send_one, sub, payload)
        if result == 0:
            sent.append(sub["endpoint"])
        elif result in (404, 410):
            gone.append(sub["endpoint"])
        else:
            failed.append(sub["endpoint"])
    return {"sent": sent, "gone": gone, "failed": failed}
