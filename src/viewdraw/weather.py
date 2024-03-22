import asyncio
from datetime import datetime
from math import floor

from PIL import Image
from rgbmatrix.graphics import DrawText

from constants import (
    PANEL_WIDTH,
    HOURLY,
    DAILY,
    FORECAST_TYPE,
    CONDITION,
    SMALL,
    BIG,
    CONDITION_SIZE,
    IMG_PATH,
    COMPASS,
    TOTAL_DEGREES,
    SECTION_DEGREES,
    NUM_FORECASTS,
    UTC,
    LOCALTZ,
)

from constants.colors import WHITE
from constants.fonts import FONT_4x6, FONT_5x8, FONT_8x13, FONT_10x20
from . import ViewDrawer


class Weather(ViewDrawer):
    def __init__(self) -> None:
        super().__init__()

        self.cached_conditions: dict[str, Image.Image] = {}

    def get_condition_img(self, condition: str, size: int) -> Image.Image:
        if condition not in CONDITION:
            raise ValueError(f"'{condition}' is not a valid weather condition")

        if size not in CONDITION_SIZE:
            raise ValueError("Condition img size must be 16 or 32")

        condition_path = f"{IMG_PATH}/{size}/{condition}.png"
        condition_img = None
        if condition_path in self.cached_conditions:
            condition_img = self.cached_conditions[condition_path]
        else:
            condition_img = Image.open(condition_path)
            if not condition_img:
                return None
            condition_img = condition_img.convert("RGB")
            self.cached_conditions[condition_path] = condition_img

        return condition_img

    def get_compass(self, degrees) -> str:
        return COMPASS[round((degrees % TOTAL_DEGREES) / SECTION_DEGREES)]

    def draw_current_weather(self, canvas, weather):
        condition = weather.get("condition")
        condition_img = self.get_condition_img(condition, BIG)
        x = 2
        y = 0
        if condition_img:
            canvas.SetImage(condition_img, x, y)

        temperature = weather.get("temperature")
        temperature_unit = weather.get("temperature_unit")
        humidity = weather.get("humidity")
        cloud_coverage = weather.get("cloud_coverage")
        pressure = weather.get("pressure")
        pressure_unit = weather.get("pressure_unit")
        wind_bearing = weather.get("wind_bearing")
        wind_speed = weather.get("wind_speed")
        wind_speed_unit = weather.get("wind_speed_unit")

        x += condition_img.width + 2
        y = FONT_10x20.height - 4
        temp_width = len(str(temperature)) * FONT_10x20.char_width
        DrawText(canvas, FONT_10x20, x, y, WHITE, str(temperature))

        daily = weather.get("forecast_daily")
        if daily:
            today = daily[0]
            high = today.get("temperature")
            low = today.get("templow")
            high_low = f"{high}° {low}°"
            y = condition_img.height - 2
            DrawText(canvas, FONT_5x8, x + 1, y, WHITE, high_low)

        x += temp_width
        y = FONT_5x8.height + 1
        temp_unit_width = len(temperature_unit) * FONT_5x8.char_width
        DrawText(canvas, FONT_5x8, x, y, WHITE, temperature_unit)

        x += temp_unit_width + 10
        y = FONT_8x13.height - 3
        hum = f"{humidity}%"
        DrawText(canvas, FONT_8x13, x, y, WHITE, hum)

        wind_compass = self.get_compass(wind_bearing)
        wind = f"{round(wind_speed)} {wind_speed_unit} {wind_compass}"
        y += FONT_5x8.height + 2
        DrawText(canvas, FONT_5x8, x, y, WHITE, wind)

        press = f"{round(pressure, 1)} {pressure_unit}"
        y += FONT_5x8.height + 2
        DrawText(canvas, FONT_5x8, x, y, WHITE, press)

    def draw_forecast(
        self, canvas, x: int, y: int, width: int, forecast: dict, forecast_type: str
    ):
        if forecast_type not in FORECAST_TYPE:
            f_types = ",".join(list(FORECAST_TYPE))
            raise ValueError(
                f"'{forecast_type}' is not a valid forecast type ({f_types})"
            )

        condition = forecast.get("condition")
        condition_img = self.get_condition_img(condition, SMALL)

        forecast_dt = datetime.fromisoformat(forecast.get("datetime"))
        forecast_dt = forecast_dt.replace(tzinfo=UTC)
        forecast_dt = forecast_dt.astimezone(LOCALTZ)

        high = forecast.get("temperature")
        low = forecast.get("templow")
        humidity = forecast.get("humidity")

        label = ""
        info = ""
        if forecast_type == DAILY:
            label = forecast_dt.strftime("%a")
            info = f"{high}° {low}°"
        elif forecast_type == HOURLY:
            label = forecast_dt.strftime("%-I%p")
            info = f"{high}° {humidity}%"

        label_x = x + round(width / 2) - round(len(label) * FONT_5x8.char_width / 2)
        label_y = y + FONT_5x8.height - 2
        DrawText(canvas, FONT_5x8, label_x, label_y, WHITE, label)

        img_x = x + round(width / 2) - (condition_img.width / 2)
        img_y = label_y + 1
        canvas.SetImage(condition_img, img_x, img_y)

        info_x = x + round(width / 2) - round(len(info) * FONT_4x6.char_width / 2) + 1
        info_y = img_y + condition_img.height + FONT_4x6.height + 1
        DrawText(canvas, FONT_4x6, info_x, info_y, WHITE, info)

    async def draw(self, canvas, data):
        self.update_last_drawn()
        weather = data.weather_forecast

        if not weather:
            return

        self.draw_current_weather(canvas, weather)

        forecast_type = data.forecast_type
        forecasts = weather.get(f"forecast_{forecast_type.lower()}")
        # exclude first since that data is already in current weather
        forecasts = forecasts[1 : NUM_FORECASTS + 1]
        x = 0
        y = 34
        f_width = floor(PANEL_WIDTH * 2.0 / NUM_FORECASTS)
        for forecast in forecasts:
            self.draw_forecast(canvas, x, y, f_width, forecast, forecast_type)
            x += f_width

        await asyncio.sleep(0.25)
