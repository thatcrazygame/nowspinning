from math import ceil, floor

import numpy as np
from PIL import Image, ImageDraw
from pyaudio import paContinue, paInt16, PyAudio, Stream

CHUNK = 256  # Samples: 1024,  512, 256, 128
RATE = 44100  # Equivalent to Human Hearing at 40 kHz
MAX_HZ = 20000  # Commonly referenced upper limit for "normal" audio range
MAX_VOL = 200
BUFFER_FRAMES = 4

class EQStream(object):
    def __init__(self) -> None:
        self.pyaudio = PyAudio()
        self.stream: Stream = None
        self.frame_buffer = None
        self.max_val = None
        self.listen()

    def __callback(self, in_data, frame_count, time_info, status):
        frame = np.frombuffer(in_data, dtype=np.int16).reshape((1,CHUNK))
        
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
            self.max_val =  max(bins)

        # Convert to numpy array:
        bins = np.array(bins)
        # Normalize and round
        bins = np.interp(bins, (bins.min(), max(MAX_VOL, bins.max())), (0, max_height))
        bins = np.round(bins)

        return bins


    def draw_eq(self, canvas, x: int, y: int, bar_width: int,
                max_height: int, num_bars: int):
        width = num_bars * bar_width
        background = (0, 0, 0)
        img = Image.new("RGB", (width, max_height), background)
        draw = ImageDraw.Draw(img)
        
        bins = self.get_eq_bins(max_height, num_bars)
        
        bar_x = 0
        for bin_val in bins:
            
            draw.rectangle([(bar_x,0),(bar_x+bar_width-1, bin_val)], 
                           fill=(255,255,255))
            
            bar_x += bar_width
            
        # y coordinates are top to bottom in PIL images
        img = img.transpose(method=Image.Transpose.FLIP_TOP_BOTTOM)
        
        canvas.SetImage(img, x, y)
