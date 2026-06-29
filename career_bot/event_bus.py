"""Process-global pub/sub for live game-API-call events -> the SSE /api/stream feed.

Decoupled from the single ``UmaClient.on_api_log`` hook slot (which the runner
owns during a career, runner.py:654), so the live stream coexists with a running
career instead of clobbering the runner's logging. The client publishes a compact,
SECRET-FREE event per call; SSE subscribers each get their own bounded queue and
drop (never block) when slow. Additive and best-effort: publish never raises.
"""
import queue
import threading

_subscribers = set()
_lock = threading.Lock()


def subscribe(maxsize=1000):
    """Register a new subscriber; returns a bounded queue.Queue of events."""
    q = queue.Queue(maxsize=maxsize)
    with _lock:
        _subscribers.add(q)
    return q


def unsubscribe(q):
    with _lock:
        _subscribers.discard(q)


def publish(evt):
    """Fan ``evt`` out to all subscribers. Never raises; a full/slow subscriber
    queue simply drops the event."""
    with _lock:
        subs = list(_subscribers)
    for q in subs:
        try:
            q.put_nowait(evt)
        except Exception:
            pass  # full or broken queue -> drop (bounded; stream stays best-effort)
