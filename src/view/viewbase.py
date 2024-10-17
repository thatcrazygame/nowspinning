from abc import ABC, abstractmethod
import functools
import os
import sys

file_path = os.path.abspath(__file__)
root_folder = os.path.abspath(os.path.dirname(os.path.dirname(file_path)))
sys.path.append(root_folder)


class View(ABC):
    name: str = None
    sort: int = None

    @abstractmethod
    async def draw(self, canvas, data):
        pass


VIEWS: dict[str, View] = {}


def register(view_cls: View):
    name = view_cls.__name__
    try:
        if view_cls.name is not None:
            name = view_cls.name
    except AttributeError:
        pass

    @functools.wraps(view_cls)
    def wrapper_singleton(*args, **kwargs):
        if wrapper_singleton.instance is None:
            wrapper_singleton.instance = view_cls(*args, **kwargs)
        return wrapper_singleton.instance

    wrapper_singleton.instance = view_cls()

    VIEWS[name] = wrapper_singleton.instance

    return wrapper_singleton
