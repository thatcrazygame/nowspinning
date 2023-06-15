import asyncio

from . import ViewDrawer


class Off(ViewDrawer):
    async def draw(self, canvas, data):
        self.update_last_drawn()
        await asyncio.sleep(1)
