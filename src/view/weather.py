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
    SECONDARY_TYPE,
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
from constants.fonts import FONT_4X6, FONT_5X8, FONT_8X13, FONT_9X18, FONT_10X20
from constants.secondaryinfo import POP, RH, SECONDARY_DEFAULT, SecondaryInfo
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
            speed=0.02,
        )

        self.alert_scroll = ScrollingText(
            font=FONT_5X8,
            color=WHITE,
            starting_x=2,
            y=PANEL_HEIGHT - 2,
            left_bound=2,
            right_bound=PANEL_WIDTH * 2,
            num_spaces=3,
            speed=0.02,
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

    def draw_current_weather(self, canvas, weather, secondary_type):
        condition = weather.get("condition")
        condition_img = self.get_condition_img(condition, BIG)
        x = 2
        y = 0
        if condition_img:
            alert = weather.get("alert")
            condition_img = self.draw_alert_triangle(condition_img, alert)
            canvas.SetImage(condition_img, x, y)

        temperature = str(weather.get("temperature"))
        temperature_unit = weather.get("temperature_unit")
        humidity = weather.get("humidity")
        pop = ""
        cloud_coverage = weather.get("cloud_coverage")
        pressure = weather.get("pressure")
        pressure_unit = weather.get("pressure_unit")
        wind_bearing = weather.get("wind_bearing")
        wind_speed = weather.get("wind_speed")
        wind_speed_unit = weather.get("wind_speed_unit")

        temp_font = FONT_10X20
        if len(temperature) == 3:
            temp_font = FONT_9X18

        x += condition_img.width + 2
        y = temp_font.height - 4
        temp_width = temp_font.str_width(str(temperature))
        DrawText(canvas, temp_font, x, y, WHITE, str(temperature))

        x += temp_width
        y = FONT_5X8.height + 1
        FONT_5X8.str_width(temperature_unit)
        DrawText(canvas, FONT_5X8, x, y, WHITE, temperature_unit)

        daily = weather.get("forecast_daily")
        if daily:
            today = daily[0]
            high = today.get("temperature")
            low = today.get("templow")
            high_low = f"{high}° {low}°"
            y = condition_img.height - 2
            DrawText(canvas, FONT_5X8, condition_img.width + 3, y, WHITE, high_low)

        hourly = weather.get("forecast_hourly")
        if hourly:
            now = hourly[0]
            pop = now.get("precipitation_probability")

        press = f"{round(pressure, 1)} {pressure_unit}"
        press_width = FONT_5X8.str_width(press)

        wind_compass = self.get_compass(wind_bearing)
        wind = f"{round(wind_speed)} {wind_speed_unit} {wind_compass}"
        wind_width = FONT_5X8.str_width(wind)

        x = (PANEL_WIDTH * 2) - 51
        y = FONT_8X13.height - 3

        sec_type: SecondaryInfo = POP
        secondary_val = pop

        if secondary_type != SECONDARY_DEFAULT.name:
            sec_type = SECONDARY_TYPE[secondary_type]
            if sec_type == RH:
                secondary_val = humidity
            elif sec_type == POP:
                secondary_val = pop

        secondary_info = f"{secondary_val}{sec_type.unit}"
        secondary_abbr = sec_type.abbr

        DrawText(canvas, FONT_8X13, x, y, WHITE, secondary_info)
        secondary_width = FONT_8X13.str_width(secondary_info)
        DrawText(canvas, FONT_5X8, x + secondary_width + 2, y, WHITE, secondary_abbr)

        y += FONT_5X8.height + 2
        DrawText(canvas, FONT_5X8, x, y, WHITE, wind)

        y += FONT_5X8.height + 2
        DrawText(canvas, FONT_5X8, x, y, WHITE, press)

    def info_str(self, value, unit: str) -> str:
        val = str(value)
        return f"{val}{unit if len(val) < 3 else ''}"

    def draw_forecast(
        self,
        canvas,
        x: int,
        y: int,
        width: int,
        forecast: dict,
        forecast_type: str,
        secondary_type: str,
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
        pop = forecast.get("precipitation_probability")

        label = ""
        info = ""
        primary = self.info_str(high, "°")
        secondary = ""
        secondary_val = ""
        secondary_unit = ""

        if forecast_type == DAILY:
            label = forecast_dt.strftime("%a")
            secondary_val = low
            secondary_unit = "°"
        elif forecast_type == HOURLY:
            label = forecast_dt.strftime("%-I%p")
            secondary_val = pop
            secondary_unit = POP.unit

        sec_type: SecondaryInfo = SECONDARY_TYPE[secondary_type]
        if sec_type != SECONDARY_DEFAULT:
            if sec_type == RH:
                secondary_val = humidity
            elif sec_type == POP:
                secondary_val = pop
            secondary_unit = sec_type.unit

        secondary = self.info_str(secondary_val, secondary_unit)

        info = f"{primary} {secondary}"

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
        weather = data.weather_forecast

        if not weather:
            return

        forecast_type = data.forecast_type
        secondary_type = data.secondary_type

        self.draw_current_weather(canvas, weather, secondary_type)

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
            self.draw_forecast(
                canvas, x, y, f_width, forecast, forecast_type, secondary_type
            )
            x += f_width
