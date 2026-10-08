"""In-process events: strictly increasing seq per run, replayable from the buffer,
live via asyncio queues. Same port as the Redis streams adapter."""

import asyncio
from collections import defaultdict

from blindrun.ports import Event, Events, RunId
from blindrun.schemas import utcnow


class InProcEvents(Events):
    def __init__(self) -> None:
        self._buffer: dict[RunId, list[Event]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._subs: dict[RunId, list[asyncio.Queue]] = defaultdict(list)

    async def emit(self, run_id: RunId, type_: str, data: dict) -> int:
        async with self._lock:
            seq = len(self._buffer[run_id])
            ev = Event(seq=seq, run_id=run_id, type=type_, at=utcnow(), data=data)
            self._buffer[run_id].append(ev)
        for q in list(self._subs[run_id]):
            await q.put(ev)
        return seq

    def replay(self, run_id: RunId, after_seq: int = -1) -> list[Event]:
        return [e for e in self._buffer.get(run_id, []) if e.seq > after_seq]

    async def subscribe(self, run_id: RunId, after_seq: int = -1):
        q: asyncio.Queue = asyncio.Queue()
        # Anything already buffered arrives before live events, in seq order.
        for ev in self.replay(run_id, after_seq):
            await q.put(ev)
        self._subs[run_id].append(q)
        try:
            while True:
                ev = await q.get()
                yield ev
        finally:
            self._subs[run_id].remove(q)
