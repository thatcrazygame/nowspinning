import asyncio
from datetime import datetime
from math import floor

from PIL import Image, ImageDraw
from rgbmatrix.graphics import DrawText

from constants import (
    PANEL_HEIGHT,
    PANEL_WIDTH,
    ALERT,
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

from constants.colors import BLACK, CRIMSON, WHITE
from constants.fonts import FONT_4X6, FONT_5X8, FONT_8X13, FONT_10X20
from data import Data
from scrollingtext import ScrollingText
from view.viewbase import View, register


@register
class Weather(View):
    sort = 1

    def __init__(self) -> None:
        super().__init__()

        self.alert_title_scroll = ScrollingText(
            font=FONT_5X8,
            color=WHITE,
            starting_x=2,
            y=PANEL_HEIGHT - 14 - FONT_5X8.height,
            left_bound=2,
            right_bound=PANEL_WIDTH * 2,
            num_spaces=3,
            scroll_speed=2,
        )

        self.alert_scroll = ScrollingText(
            font=FONT_5X8,
            color=WHITE,
            starting_x=2,
            y=PANEL_HEIGHT - 2,
            left_bound=2,
            right_bound=PANEL_WIDTH * 2,
            num_spaces=3,
            scroll_speed=2,
        )

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

    def draw_alert_triangle(self, img: Image.Image, alert) -> Image.Image:
        if alert["total"] > 0:
            alert_img = img.copy()
            draw = ImageDraw.Draw(alert_img)
            triangle = [(21, 31), (31, 31), (26, 23)]
            draw.polygon(triangle, fill=CRIMSON.rgb)
            exclamation = [(26, 25), (26, 28)]
            draw.line(exclamation, fill=BLACK.rgb, width=1)
            draw.point([26, 30], fill=BLACK.rgb)
            return alert_img
        else:
            return img

    def draw_current_weather(self, canvas, weather):
        condition = weather.get("condition")
        condition_img = self.get_condition_img(condition, BIG)
        x = 2
        y = 0
        if condition_img:
            alert = weather.get("alert")
            condition_img = self.draw_alert_triangle(condition_img, alert)
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
        y = FONT_10X20.height - 4
        temp_width = FONT_10X20.str_width(str(temperature))
        DrawText(canvas, FONT_10X20, x, y, WHITE, str(temperature))

        daily = weather.get("forecast_daily")
        if daily:
            today = daily[0]
            high = today.get("temperature")
            low = today.get("templow")
            high_low = f"{high}° {low}°"
            y = condition_img.height - 2
            DrawText(canvas, FONT_5X8, x + 1, y, WHITE, high_low)

        x += temp_width
        y = FONT_5X8.height + 1
        temp_unit_width = FONT_5X8.str_width(temperature_unit)
        DrawText(canvas, FONT_5X8, x, y, WHITE, temperature_unit)

        x += temp_unit_width + 10
        y = FONT_8X13.height - 3
        hum = f"{humidity}%"
        DrawText(canvas, FONT_8X13, x, y, WHITE, hum)

        wind_compass = self.get_compass(wind_bearing)
        wind = f"{round(wind_speed)} {wind_speed_unit} {wind_compass}"
        y += FONT_5X8.height + 2
        DrawText(canvas, FONT_5X8, x, y, WHITE, wind)

        press = f"{round(pressure, 1)} {pressure_unit}"
        y += FONT_5X8.height + 2
        DrawText(canvas, FONT_5X8, x, y, WHITE, press)

    def draw_forecast(
        self, canvas, x: int, y: int, width: int, forecast: dict, forecast_type: str
    ):
        if forecast_type not in FORECAST_TYPE:
            f_types = ",".join(FORECAST_TYPE)
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

        label_x = x + round(width / 2) - round(FONT_5X8.str_width(label) / 2)
        label_y = y + FONT_5X8.height - 2
        DrawText(canvas, FONT_5X8, label_x, label_y, WHITE, label)

        img_x = x + round(width / 2) - (condition_img.width / 2)
        img_y = label_y + 1
        canvas.SetImage(condition_img, img_x, img_y)

        info_x = x + round(width / 2) - round(FONT_4X6.str_width(info) / 2) + 1
        info_y = img_y + condition_img.height + FONT_4X6.height + 1
        DrawText(canvas, FONT_4X6, info_x, info_y, WHITE, info)

    def draw_alert(self, canvas, alert):
        if alert["total"] > 0:
            self.alert_title_scroll.draw(canvas, alert["title"])

            expire_date = datetime.fromisoformat(alert["event_expires"])
            expire_x = 2
            expire_y = PANEL_HEIGHT - 4 - FONT_5X8.height
            expire_txt = f"Expires: {expire_date.strftime('%x %I:%M %p')}"
            if alert["total"] > 1:
                count = f"({alert['selected']}/{alert['total']})"
                expire_txt = f"{expire_txt} {count}"

            DrawText(canvas, FONT_4X6, expire_x, expire_y, WHITE, expire_txt)

            self.alert_scroll.draw(canvas, alert["spoken_desc"])
        else:
            self.alert_title_scroll.draw(canvas, "No active alerts")
            self.alert_scroll.draw(canvas, "")

    async def draw(self, canvas, data: Data):
        self.update_last_drawn()
        weather = data.weather_forecast

        if not weather:
            return

        self.draw_current_weather(canvas, weather)

        forecast_type = data.forecast_type
        alert = weather.get("alert")
        if forecast_type == ALERT and alert:
            self.draw_alert(canvas, alert)
            return

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
