import asyncio


async def wait_with_cancel_event(task, event, stop_coroutine):
    """
    Wait until a task is complete or a cancel event.
    """
    if task:
        if event:
            event_wait_task = asyncio.create_task(event.wait())
            wait_set = {event_wait_task, task}
            done, pending = await asyncio.wait(
                wait_set, return_when=asyncio.FIRST_COMPLETED
            )
            if task in pending:
                await stop_coroutine()
            else:
                event_wait_task.cancel()
        else:
            await task
