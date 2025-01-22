from dataclasses import dataclass


@dataclass
class SecondaryInfo:
    name: str
    abbr: str
    unit: str


SECONDARY_DEFAULT = SecondaryInfo(name="Default", abbr="DFT", unit="")
RH = SecondaryInfo(name="Relative Humidity", abbr="RH", unit="%")
POP = SecondaryInfo(name="Probability of Precipitation", abbr="PoP", unit="%")
