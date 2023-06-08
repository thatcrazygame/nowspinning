from datetime import datetime

from constants import PANEL_HEIGHT, PANEL_WIDTH
from data import Data
from rgbmatrix.graphics import Color, DrawText, Font

from linegraph import LineGraph
from . import ViewDrawer

class Dashboard(ViewDrawer):
    def __init__(self) -> None:
        super().__init__()
        self.fonts = {}
        
        font_8x13 = Font()
        font_8x13.LoadFont("../fonts/8x13.bdf")
        self.fonts["8x13"] = font_8x13
        
        font_4x6 = Font()
        font_4x6.LoadFont("../fonts/4x6.bdf")
        self.fonts["4x6"] = font_4x6
        
        self.white_text = Color(255, 255, 255)
    
    async def draw(self, canvas, data: Data):
        self.update_last_drawn()
        
        font_4x6 = self.fonts["4x6"]
        font_8x13 = self.fonts["8x13"]
        white_text = self.white_text
        
        now = datetime.now()
        now_str = now.strftime("%I:%M %m/%d/%Y")
        
        char_width = 8
        x = PANEL_WIDTH - (len(now_str) * char_width)/2
        y = font_8x13.height - 2
        DrawText(canvas, font_8x13, x, y, white_text, now_str)
        
        if not data.averages:
            return
        
        tmpr_avgs = data.averages.get("temperature").copy()
        if data.temperature_f is not None:
            tmpr_avgs.append(round(data.temperature_f, 1))
            
        hum_avgs = data.averages.get("humidity").copy()
        if data.humidity is not None:
            hum_avgs.append(round(data.humidity, 1))
            
        voc_avgs = data.averages.get("voc").copy()
        if data.voc is not None:
            voc_avgs.append(round(data.voc))
            
        co2_avgs = data.averages.get("co2").copy()
        if data.co2 is not None:
            co2_avgs.append(round(data.co2))
        
        graphs = [
            LineGraph("Temp", tmpr_avgs, "°F", round=1, 
                        line_color=(191, 29, 0),
                        fill_color=(51, 8, 0)),
            LineGraph("Hum", hum_avgs, "%", round=1, 
                        line_color=(0, 76, 191),
                        fill_color=(0, 20, 51)),
            LineGraph("VOC", voc_avgs, 
                        line_color=(109, 191, 119),
                        fill_color=(29, 51, 32)),
            LineGraph("CO2", co2_avgs, "ppm", 
                        line_color=(187, 191, 172),
                        fill_color=(50, 51, 46))
        ]
        
        graph_x = 0
        background = (0, 0, 0)
        graph: LineGraph
        for i, graph in enumerate(graphs):
            graph.background = background
            graph_y = PANEL_HEIGHT - graph.height * (len(graphs)-i)
            graph.draw(canvas, font_4x6, graph_x, graph_y, white_text)
            background = graph.fill_color