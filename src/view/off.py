from view.viewbase import View, register


@register
class Off(View):
    sort = 0

    async def draw(self, canvas, data):
        pass
