from math import ceil, floor

import numpy as np
from PIL import ImageDraw
from pyaudio import paContinue, paInt16, PyAudio, Stream

from constants import (
    BIN_DIMENSIONS,
    CHUNK,
    RATE,
    MIN_HZ,
    MAX_HZ,
    MAX_VOL,
    BUFFER_FRAMES,
)
from constants.colors import BLACK
from utils.images import get_gradient_img

import logging

logger = logging.getLogger(__name__)


class EQStream(object):
    def __init__(self) -> None:
        self.pyaudio = PyAudio()
        self.stream: Stream = None
        self.frame_buffer = None
        self.max_val = None
        self._gradient_img = None
        self._bar_colors = None

    def _callback(self, in_data, frame_count, time_info, status):
        frame = np.frombuffer(in_data, dtype=np.int16).reshape((1, CHUNK))

        if self.frame_buffer is None:
            self.frame_buffer = frame
        else:
            new_buffer = np.concatenate((frame, self.frame_buffer))
            self.frame_buffer = new_buffer[0:BUFFER_FRAMES].copy()

        return (in_data, paContinue)

    def listen(self):
        self.stream = self.pyaudio.open(
            format=paInt16,
            channels=1,
            rate=RATE,
            input=True,
            input_device_index=0,
            frames_per_buffer=CHUNK,
            stream_callback=self._callback,
        )
        self.stream.start_stream()

    def stop(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

    def get_eq_bins(self, max_height: int, num_bins: int):
        fft_data = np.fft.rfft(self.frame_buffer)
        fft_data = np.absolute(fft_data)
        with np.errstate(divide="ignore"):
            fft_data = np.log10(fft_data) * 10

        weights = [1.0 / 2.0**i for i in range(BUFFER_FRAMES)]
        fft_data = np.average(fft_data, axis=0, weights=weights)

        hz_per_data = int(RATE / len(fft_data))
        max_idx = int(MAX_HZ / hz_per_data)
        min_idx = int(MIN_HZ / hz_per_data)
        # round to nearest mutliple of bins
        max_idx = num_bins * ceil(max_idx / num_bins)
        min_idx = num_bins * floor(min_idx / num_bins)
        fft_data = fft_data[min_idx:max_idx]

        bins = []
        pos = 0
        for dim in BIN_DIMENSIONS:
            size, weight = dim
            vol = np.mean(fft_data[pos : pos + size]) * weight
            pos += size
            bins.append(vol)

        bins = np.array(bins)
        # Normalize and round
        min_val = bins.min() / 2
        max_val = max(MAX_VOL, bins.max())
        bins = np.interp(bins, (min_val, max_val), (0, max_height))
        bins = np.round(bins)

        return bins

    def _get_gradient_img(self, width, height, colors=None):
        colors_changed = (
            self._bar_colors is None
            or colors is None
            or set(colors) != set(self._bar_colors)
        )
        self._bar_colors = colors

        if self._gradient_img is not None and not colors_changed:
            return self._gradient_img

        self._gradient_img = get_gradient_img(width, height, colors)

        return self._gradient_img

    def draw_eq(
        self,
        canvas,
        x: int,
        y: int,
        bar_width: int,
        max_height: int,
        num_bars: int,
        colors=None,
    ):
        width = num_bars * bar_width
        img = self._get_gradient_img(width, max_height, colors).copy()
        draw = ImageDraw.Draw(img)

        bins = self.get_eq_bins(max_height, num_bars)

        bar_x = 0
        for bin_val in bins:
            bar_height = max_height - bin_val
            draw.rectangle(
                [(bar_x, 0), (bar_x + bar_width - 1, bar_height)], fill=BLACK.rgb
            )
            bar_x += bar_width

        canvas.SetImage(img, x, y)
