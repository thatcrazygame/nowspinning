from io import BytesIO

from PIL import Image
import requests

class SportBase(object):
    def __init__(self, abbr:str) -> None:    
        self.abbr = abbr
        self._logo_img:Image.Image = None
        self._logo_url = ""

        
    def get_logo(self, size:tuple) -> Image.Image:
        if not self._logo_img and self._logo_url != "":
            background = Image.new("RGBA", size, (0,0,0))
            response = requests.get(self._logo_url.lower())
            if response.status_code == requests.codes.ok:
                img = Image.open(BytesIO(response.content))
                img.thumbnail(size, Image.Resampling.LANCZOS)
                img = Image.alpha_composite(background, img)
                img = img.convert("RGB")
                self._logo_img = img
            # else:
            #     print(vars(response))
            
        return self._logo_img


class Team(SportBase):
    def __init__(self, abbr:str, league:str):
        super().__init__(abbr)
        self.attributes = {}
        self.last_changes = {}
        self.league = league
        self.game_state = ""
        self._logo_url = f"https://a.espncdn.com/i/teamlogos/{league}/500/scoreboard/{abbr}.png?nocache=12312312412414214"
    
    
    @property
    def friendly_name(self) -> str:
        friendly_name = ""
        if self.game_state != "":
            team_name = self.attributes.get("team_name")
            if team_name:
                friendly_name = f"{self.abbr} - {team_name}"
            else:
                friendly_name = f"{self.abbr} - {self.league}"
        
        return friendly_name

class League(SportBase):
    def __init__(self, abbr:str):
        super().__init__(abbr)
        self.sport = ""
        self._logo_url = f"https://a.espncdn.com/i/teamlogos/leagues/500/{abbr}.png"
        self.teams: dict[str, Team] = {}
        
    def team(self, team_abbr:str, attributes:dict=None, changes:dict=None,
             game_state:str=None) -> Team:
        if team_abbr not in self.teams:
            team = Team(team_abbr, self.abbr)
            self.teams[team_abbr] = team
            
        if attributes:
            self.teams[team_abbr].attributes = attributes
        if changes:
            self.teams[team_abbr].last_changes = changes
        if game_state:
            self.teams[team_abbr].game_state = game_state
            
        return self.teams[team_abbr]
            
    @property
    def friendly_team_names(self) -> list[str]:
        team_names = []
        if self.teams:
            team_names = [team.friendly_name
                          for team in self.teams.values()
                          if team.friendly_name != ""]
        return team_names