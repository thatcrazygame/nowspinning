from typing import Tuple

from PIL import Image, ImageDraw


class LineGraph(object):
    def __init__(self, label: str, data: list[float] = [],
                 units: str = "") -> None:
        self.label: str = label
        self.data: list[float] = data
        self.units: str = units
        self.data_space: int = 3
        self.height: int = 12
        self.min_val: float = 0.0
        self.max_val: float = 100.0
        self.line_color: Tuple[int, int, int] = (255, 255, 255)
        self.fill_color: Tuple[int, int, int] = (0, 0, 0)
        self.background: Tuple[int, int, int] = (0, 0, 0)

    
    @property
    def width(self) -> int:
        return (len(self.data) - 1) * self.data_space
    
    
    def get_scaled_data(self) -> list[int]:
        scaled = []
        for d in self.data:
            val = d
            if d < self.min_val:
               val = self.min_val
            elif d > self.max_val:
                val = self.max_val
        
            val = round((val - self.min_val)
                        / (self.max_val - self.min_val)
                        * self.height)
            scaled.append(val)
        return scaled
    
    
    def get_graph_img(self, data: list[float] = None) -> Image.Image:
        if data is not None:
            self.data = data

        size = (self.width, self.height)
        img = Image.new("RGB", size, self.background)
        draw = ImageDraw.Draw(img)
        
        points: list[Tuple[int,int]] = []
        x: int = 0
        y: int = 0
        points.append((x,y))
        
        scaled = self.get_scaled_data()
        for i in range(len(scaled)):
            val = scaled[i]
            y = val
            points.append((x,y))
            if i < len(scaled) - 1:
                x += self.data_space
            
        points.append((x,0))
        
        draw.polygon(points, fill=self.fill_color)
        # remove first and last points becase they 
        # are the front and back lines of the graph
        points.pop(0)
        points.pop()
        # draw line on top of the polygon fill
        draw.line(points, fill=self.line_color)
        
        # y coordinates are top to bottom in PIL images
        img = img.transpose(method=Image.Transpose.FLIP_TOP_BOTTOM)
        
        return img
