import asyncio

from view.viewbase import View, register


@register
class Off(View):
    sort = 0

    async def draw(self, canvas, data):
        self.update_last_drawn()
        await asyncio.sleep(1)
