from abc import ABC, abstractmethod
import os
import sys
from time import perf_counter

file_path = os.path.abspath(__file__)
root_folder = os.path.abspath(os.path.dirname(os.path.dirname(file_path)))
sys.path.append(root_folder)

class ViewDrawer(ABC):
    def __init__(self) -> None:
        self.last_drawn: float = None
    
    
    def update_last_drawn(self):
        self.last_drawn = perf_counter()
    
    
    @abstractmethod
    def draw(self, canvas, data):
        pass


