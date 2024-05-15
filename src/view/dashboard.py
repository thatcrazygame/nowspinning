from datetime import datetime

from constants import PANEL_HEIGHT, PANEL_WIDTH
from constants.colors import (
    WHITE,
    CRIMSON,
    DARKRED,
    COBALT,
    NAVY,
    SOFTGREEN,
    DARKGREEN,
    LIGHTGRAY,
    DARKSLATEGRAY,
)
from constants.fonts import FONT_4X6, FONT_8X13
from data import Data
from rgbmatrix.graphics import DrawText

from linegraph import LineGraph
from view.viewbase import View, register


@register
class Dashboard(View):
    sort = 2

    def __init__(self) -> None:
        super().__init__()

    async def draw(self, canvas, data: Data):
        self.update_last_drawn()

        now = datetime.now()
        now_str = now.strftime("%I:%M %m/%d/%Y")

        x = PANEL_WIDTH - FONT_8X13.str_width(now_str) / 2
        y = FONT_8X13.height - 2
        DrawText(canvas, FONT_8X13, x, y, WHITE, now_str)

        tmpr_avgs = []
        hum_avgs = []
        voc_avgs = []
        co2_avgs = []

        tmpr_avgs.extend(data.averages.get("temperature") or [])
        if data.temperature_f is not None:
            tmpr_avgs.append(round(data.temperature_f, 1))

        hum_avgs.extend(data.averages.get("humidity") or [])
        if data.humidity is not None:
            hum_avgs.append(round(data.humidity, 1))

        voc_avgs.extend(data.averages.get("voc") or [])
        if data.voc is not None:
            voc_avgs.append(round(data.voc))

        co2_avgs.extend(data.averages.get("co2") or [])
        if data.co2 is not None:
            co2_avgs.append(round(data.co2))

        graphs = [
            LineGraph(
                label="Temp",
                units="°F",
                data=tmpr_avgs,
                round=1,
                line_color=CRIMSON.rgb,
                fill_color=DARKRED.rgb,
            ),
            LineGraph(
                label="Hum",
                units="%",
                data=hum_avgs,
                round=1,
                line_color=COBALT.rgb,
                fill_color=NAVY.rgb,
            ),
            LineGraph(
                label="VOC",
                data=voc_avgs,
                line_color=SOFTGREEN.rgb,
                fill_color=DARKGREEN.rgb,
            ),
            LineGraph(
                label="CO2",
                units="ppm",
                data=co2_avgs,
                line_color=LIGHTGRAY.rgb,
                fill_color=DARKSLATEGRAY.rgb,
            ),
        ]

        graph_x = 0
        background = (0, 0, 0)
        graph: LineGraph
        for i, graph in enumerate(graphs):
            graph.background = background
            graph_y = PANEL_HEIGHT - graph.height * (len(graphs) - i)
            graph.draw(canvas, FONT_4X6, graph_x, graph_y, WHITE)
            background = graph.fill_color
