import sys
import logging
from typing import Dict, Any

import requests


class Pycord:

    url_base = 'https://discordapp.com/api/'
    version = '0.0.1'

    def __init__(self, client_id: str, token: str, user_agent: str=None) -> None:
        self.client_id = client_id
        self.token = token
        self.user_agent = user_agent or f'Pycord (github.com/Celeo/Pycord, {Pycord.version})'
        self.__setup_logger()

    def __setup_logger(self):
        self.logger = logging.getLogger('discord')
        self.logger.setLevel(20)
        formatter = logging.Formatter(style='{', fmt='{asctime} [{levelname}] {message}', datefmt='%Y-%m-%d %H:%M:%S')
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        handler.setLevel(20)
        self.logger.addHandler(handler)
        handler = logging.FileHandler(20)
        handler.setFormatter(formatter)
        handler.setLevel(20)
        self.logger.addHandler(handler)

    def __build_headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Bot {self.token}',
            'User-Agent': self.user_agent
        }

    def __query(self, path: str) -> Dict[str, Any]:
        url = Pycord.url_base + path
        self.logger.debug(f'Making request to {url}')
        r = requests.get(url, headers=self.__build_headers())
        self.logger.debug(f'Response from {url} was {r.status_code}')
        if r.status_code != 200:
            raise ValueError(f'Non-200 response from Discord API ({r.status_code}): {r.text}')
        return r.json()

    def get_basic_bot_info(self) -> Dict[str, Any]:
        return self.__query('users/@me')

    def get_connected_guilds(self):
        pass

    def get_guild_info(self, id):
        pass

    def get_channels_in(self, guild_id):
        pass

    def get_channel_info(self, id):
        pass
