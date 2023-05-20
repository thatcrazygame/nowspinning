import numpy as np
from PIL import Image, ImageDraw
from pyaudio import paContinue, paInt16, PyAudio, Stream

CHUNK = 256  # Samples: 1024,  512, 256, 128
RATE = 44100  # Equivalent to Human Hearing at 40 kHz
NUM_BINS = 16

class EQStream(object):
    def __init__(self) -> None:
        self.pyaudio = PyAudio()
        self.stream: Stream = None
        self.audio_data: np.array([])
        self.listen()
    

    def __callback(self, in_data, frame_count, time_info, status):
        self.audio_data = np.frombuffer(in_data, dtype=np.int16)
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

   
    def get_eq_bins(self, num_bins: int, max: int):
        fft_data = np.fft.rfft(self.audio_data)
        fft_data = np.absolute(fft_data)
        data_per_bin = int(len(fft_data) / num_bins)

        # attenuate first BIN:
        fft_data[0:data_per_bin-1] = fft_data[0:data_per_bin-1]/20
        
        bins = [sum(fft_data[current: current+data_per_bin])
                for current in range(0, len(fft_data), data_per_bin)]
        # Convert to numpy array:
        bins = np.array(bins)
        # Normalize and round
        bins = np.interp(bins, (bins.min(), bins.max()), (0, max))
        bins = np.round(bins)
        bins = bins[0:num_bins]
        
        return bins


    def draw_eq(self, canvas, x: int, y: int, num_bars: int, bar_width: int,
                max_height: int):
        width = num_bars * bar_width
        background = (0, 0, 0)
        img = Image.new("RGB", (width, max_height), background)
        draw = ImageDraw.Draw(img)
        
        bins = self.get_eq_bins(num_bars, max_height)
        bar_x = 0
        for bin_val in bins:
            
            draw.rectangle([(bar_x,0),(bar_x+bar_width-1, bin_val)], 
                           fill=(255,255,255))
            
            bar_x += bar_width
            
        # y coordinates are top to bottom in PIL images
        img = img.transpose(method=Image.Transpose.FLIP_TOP_BOTTOM)
        
        canvas.SetImage(img, x, y)
        