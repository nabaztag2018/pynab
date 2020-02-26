import asyncio
from asgiref.sync import sync_to_async
from django.db import close_old_connections


async def close_old_async_connections_async():
    await sync_to_async(close_old_connections, thread_sensitive=True)()


def close_old_async_connections():
    event_loop = None
    try:
        event_loop = asyncio.get_event_loop()
    except RuntimeError:
        pass
    else:
        if not event_loop.is_running():
            event_loop = None
    if event_loop:
        loop = event_loop
    else:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(close_old_async_connections_async())
    if not event_loop:
        loop.close()
