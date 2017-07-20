import sys
import logging
from typing import Dict, Any

import requests


class Pycord:

    url_base = 'https://discordapp.com/api/'
    version = '0.0.1'

    def __init__(self, token: str, user_agent: str=None) -> None:
        self.token = token
        self.user_agent = user_agent or f'Pycord (github.com/Celeo/Pycord, {Pycord.version})'
        self.__setup_logger()

    def connect(self):
        # TODO
        pass

    def disconnect(self):
        # TODO
        pass

    @property
    def connected(self):
        # TODO
        return False

    def __setup_logger(self):
        self.logger = logging.getLogger('discord')
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter(style='{', fmt='{asctime} [{levelname}] {message}', datefmt='%Y-%m-%d %H:%M:%S')
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        handler.setLevel(logging.DEBUG)
        self.logger.addHandler(handler)
        handler = logging.FileHandler('pycord.log')
        handler.setFormatter(formatter)
        handler.setLevel(logging.DEBUG)
        self.logger.addHandler(handler)

    def __build_headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Bot {self.token}',
            'User-Agent': self.user_agent,
            'Content-Type': 'application/json'
        }

    def __get(self, path: str) -> Dict[str, Any]:
        url = Pycord.url_base + path
        self.logger.debug(f'Making GET request to "{url}"')
        r = requests.get(url, headers=self.__build_headers())
        self.logger.debug(f'GET response from "{url}" was "{r.status_code}"')
        if r.status_code != 200:
            raise ValueError(f'Non-200 GET response from Discord API ({r.status_code}): {r.text}')
        return r.json()

    def __post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        url = Pycord.url_base + path
        self.logger.debug(f'Making POST request to "{url}"')
        r = requests.post(url, headers=self.__build_headers(), json=data)
        self.logger.debug(f'POST response from "{url}" was "{r.status_code}"')
        if r.status_code != 200:
            raise ValueError(f'Non-200 POST response from Discord API ({r.status_code}): {r.text}')
        return r.json()

    def get_basic_bot_info(self) -> Dict[str, Any]:
        return self.__get('users/@me')

    def get_connected_guilds(self) -> Dict[str, Any]:
        return self.__get('users/@me/guilds')

    def get_guild_info(self, id: str) -> Dict[str, Any]:
        return self.__get(f'guilds/{id}')

    def get_channels_in(self, guild_id: str) -> Dict[str, Any]:
        return self.__get(f'guilds/{guild_id}/channels')

    def get_channel_info(self, id: str) -> Dict[str, Any]:
        return self.__get(f'channels/{id}')

    def send_message(self, id: str, message: str):
        if self.connected:
            return self.__post(f'channels/{id}/messages', {'content': message})
        raise ValueError('Websocket not connected')
