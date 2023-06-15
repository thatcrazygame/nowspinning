from math import ceil, floor

import numpy as np
from PIL import Image, ImageDraw
from pyaudio import paContinue, paInt16, PyAudio, Stream

CHUNK = 256  # Samples: 1024,  512, 256, 128
RATE = 44100  # Equivalent to Human Hearing at 40 kHz
MAX_HZ = 20000  # Commonly referenced upper limit for "normal" audio range
MAX_VOL = 200
BUFFER_FRAMES = 4
IS_HORIZONTAL = (True, True, True)
IS_VERTICAL = (False, False, False)


class EQStream(object):
    def __init__(self) -> None:
        self.pyaudio = PyAudio()
        self.stream: Stream = None
        self.frame_buffer = None
        self.max_val = None
        self.__gradient_img = None
        self.__bar_colors = None

    def __callback(self, in_data, frame_count, time_info, status):
        frame = np.frombuffer(in_data, dtype=np.int16).reshape((1, CHUNK))

        if self.frame_buffer is None:
            self.frame_buffer = frame
        else:
            new_buffer = np.concatenate((frame, self.frame_buffer))
            self.frame_buffer = new_buffer[0:BUFFER_FRAMES].copy()

        return (in_data, paContinue)

    def listen(self):
        self.stream = self.pyaudio.open(format=paInt16,
                                        channels=1,
                                        rate=RATE,
                                        input=True,
                                        input_device_index=0,
                                        frames_per_buffer=CHUNK,
                                        stream_callback=self.__callback)
        self.stream.start_stream()

    def stop(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

    def get_eq_bins(self, max_height: int, num_bins: int):
        fft_data = np.fft.rfft(self.frame_buffer)
        fft_data = np.absolute(fft_data)
        fft_data = np.log10(fft_data) * 10

        weights = [1.0/2.0**i for i in range(BUFFER_FRAMES)]
        fft_data = np.average(fft_data, axis=0, weights=weights)

        hz_per_data = int(RATE / len(fft_data))
        max_idx = int(MAX_HZ / hz_per_data)
        # round up to nearest mutliple of bins
        max_idx = num_bins * ceil(max_idx / num_bins)
        fft_data = fft_data[:max_idx]

        data_per_bin = int(len(fft_data) / num_bins)

        bins = [sum(fft_data[bin:bin+data_per_bin])
                for bin in range(0, len(fft_data), data_per_bin)]

        if self.max_val is not None:
            self.max_val = max(self.max_val, max(bins))
        else:
            self.max_val = max(bins)

        # Convert to numpy array:
        bins = np.array(bins)
        # Normalize and round
        min_val = 0  # bins.min()
        max_val = max(MAX_VOL, bins.max())
        bins = np.interp(bins, (min_val, max_val), (0, max_height))
        bins = np.round(bins)

        return bins

    def __get_gradient_2d(self, start, stop, width, height, is_horizontal):
        if is_horizontal:
            return np.tile(np.linspace(start, stop, width), (height, 1))
        else:
            return np.tile(np.linspace(start, stop, height), (width, 1)).T

    def __get_gradient_3d(self, width, height, start_list, stop_list,
                          is_horizontal_list):
        result = np.zeros((height, width, len(start_list)), dtype=np.float64)

        gradient_components = enumerate(zip(start_list, stop_list,
                                            is_horizontal_list))
        for i, (start, stop, is_horizontal) in gradient_components:
            result[:, :, i] = self.__get_gradient_2d(start, stop, width,
                                                     height, is_horizontal)

        return result

    def __get_gradient_img(self, width, height, colors=None):
        colors_changed = (self.__bar_colors is None or colors is None
                          or set(colors) != set(self.__bar_colors))
        self.__bar_colors = colors

        if self.__gradient_img is not None and not colors_changed:
            return self.__gradient_img

        one_color = None
        if type(colors) is list and len(colors) == 1:
            colors = colors[0]

        if type(colors) is tuple and len(colors) == 3:
            one_color = colors

        if colors is None:
            one_color = (255, 255, 255)

        if one_color is not None:
            img = Image.new("RGB", (width, height), one_color)
            self.__gradient_img = img
            return self.__gradient_img

        num_gradients = len(colors) - 1
        gradient_height, extra = divmod(height, num_gradients)
        gradient_array = None
        for i in range(num_gradients):
            if i == num_gradients - 1:
                gradient_height += extra

            gradient = self.__get_gradient_3d(width, gradient_height,
                                              colors[i+1], colors[i],
                                              IS_VERTICAL)
            if gradient_array is None:
                gradient_array = gradient
            else:
                gradient_array = np.concatenate((gradient, gradient_array))

        img = Image.fromarray(np.uint8(gradient_array))

        self.__gradient_img = img
        return self.__gradient_img

    def draw_eq(self, canvas, x: int, y: int, bar_width: int,
                max_height: int, num_bars: int, colors=None):
        width = num_bars * bar_width
        img = self.__get_gradient_img(width, max_height, colors).copy()
        draw = ImageDraw.Draw(img)

        bins = self.get_eq_bins(max_height, num_bars)

        bar_x = 0
        for bin_val in bins:
            bar_height = max_height - bin_val
            draw.rectangle([(bar_x, 0), (bar_x+bar_width-1, bar_height)],
                           fill=(0, 0, 0))

            bar_x += bar_width

        canvas.SetImage(img, x, y)
