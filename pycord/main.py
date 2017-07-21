import sys
import logging
import json
import zlib
import threading
import time
import enum
from typing import Dict, Any, Union, Callable

import requests
import websocket


last_sequence = 'null'

__all__ = ['Pycord']


class WebSocketEvent(enum.Enum):

    DISPATCH = 0
    HEARTBEAT = 1
    IDENTIFY = 2
    STATUS_UPDATE = 3
    VOICE_STATE_UPDATE = 4
    VOICE_SERVER_PING = 5
    RESUME = 6
    RECONNECT = 7
    REQUEST_GUILD_MEMBERS = 8
    INVALID_SESSION = 9
    HELLO = 10
    HEARTBEAT_ACK = 11

    @classmethod
    def parse(cls, op):
        for event in cls:
            if event.value == int(op):
                return event
        return None


class WebSocketKeepAlive(threading.Thread):

    def __init__(self, logger: logging.Logger, ws: websocket.WebSocketApp, interval: float) -> None:
        super().__init__(name='Thread-ws_keep_alive')
        self.logger = logger
        self.ws = ws
        self.interval = interval

    def run(self):
        while True:
            try:
                self.logger.debug('Sending heartbeat, seq ' + last_sequence)
                self.ws.send(json.dumps({
                    'op': 1,
                    'd': last_sequence
                }))
            except Exception as e:
                self.logger.error(f'Got error in heartbeat: {str(e)}')
            finally:
                time.sleep(self.interval)


class WebSocketRunForeverWrapper(threading.Thread):

    def __init__(self, ws: websocket.WebSocketApp) -> None:
        super().__init__(name='Thread-ws_run_forever')
        self.ws = ws

    def run(self):
        self.ws.run_forever()


class Pycord:

    url_base = 'https://discordapp.com/api/'
    version = '0.0.1'

    def __init__(self, token: str, user_agent: str=None, logging_level: int=logging.DEBUG) -> None:
        self.token = token
        self.user_agent = user_agent or f'Pycord (github.com/Celeo/Pycord, {Pycord.version})'
        self._setup_logger(logging_level)
        self.connected = False
        self._commands = []

    # =================================================
    # Private methods
    # =================================================

    def _setup_logger(self, logging_level: int):
        self.logger = logging.getLogger('discord')
        self.logger.setLevel(logging_level)
        formatter = logging.Formatter(style='{', fmt='{asctime} [{levelname}] {message}', datefmt='%Y-%m-%d %H:%M:%S')
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(logging_level)
        self.logger.addHandler(stream_handler)
        file_handler = logging.FileHandler('pycord.log')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging_level)
        self.logger.addHandler(file_handler)

    # =====================
    # REST API
    # =====================

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

    def _get_websocket_address(self) -> str:
        return self.__get('gateway')['url']

    # =====================
    # Websocket API
    # =====================

    def _ws_on_message(self, ws: websocket.WebSocketApp, message: Union[str, bytes]):
        if isinstance(message, bytes):
            message = zlib.decompress(message, 15, 10490000).decode('utf-8')
        data = json.loads(message)
        if data.get('s') is not None:
            global last_sequence
            last_sequence = str(data['s'])
            self.logger.debug('Set last_sequence to ' + last_sequence)
        event = WebSocketEvent.parse(data['op'])
        self.logger.debug('Received event {} (op #{})'.format(
            event.name,
            data['op']
        ))
        if event == WebSocketEvent.HELLO:
            interval = float(data['d']['heartbeat_interval']) / 1000
            self.logger.debug(f'Starting heartbeat thread at {interval} seconds')
            self.__ws_keep_alive = WebSocketKeepAlive(self.logger, ws, interval)
            self.__ws_keep_alive.start()
        elif event == WebSocketEvent.DISPATCH:
            self.logger.debug('Got dispatch ' + data['t'])
            if data['t'] == 'MESSAGE_CREATE':
                message = data['d']['content']
                if message.startswith('!') and self._commands:
                    cmd_str = message[1:].split(' ')[0].lower()
                    self.logger.debug(f'Got new message, checking for callback for command "{cmd_str}"')
                    for command_obj in self._commands:
                        if command_obj[0].lower() == cmd_str:
                            self.logger.debug(f'Found matching command "{command_obj[0]}", invoking callback')
                            command_obj[1](data)

    def _ws_on_error(self, ws: websocket.WebSocketApp, error: Exception):
        self.logger.error(f'Got error from websocket connection: {str(error)}')

    def _ws_on_close(self, ws: websocket.WebSocketApp):
        self.connected = False
        self.logger.error('Websocket closed')

    def _ws_on_open(self, ws: websocket.WebSocketApp):
        payload = {
            'op': WebSocketEvent.IDENTIFY.value,
            'd': {
                'token': self.token,
                'properties': {
                    '$os': sys.platform,
                    '$browser': 'Pycord',
                    '$device': 'Pycord',
                    '$referrer': '',
                    '$referring_domain': ''
                },
                'compress': True,
                'large_threshold': 250
            }
        }
        self.logger.debug('Sending identify payload')
        ws.send(json.dumps(payload))
        self.connected = True

    # =================================================
    # Public methods
    # =================================================

    def connect_to_websocket(self):
        ws = websocket.WebSocketApp(
            self._get_websocket_address() + '?v=5&encoding=json',
            on_message=self._ws_on_message,
            on_error=self._ws_on_error,
            on_close=self._ws_on_close
        )
        ws.on_open = self._ws_on_open
        self.__ws_run_forever_wrapper = WebSocketRunForeverWrapper(ws)
        self.__ws_run_forever_wrapper.start()

    def keep_running(self):
        self.__ws_run_forever_wrapper.join()

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

    def send_message(self, id: str, message: str) -> Dict[str, Any]:
        if not self.connected:
            raise ValueError('Websocket not connected')
        return self.__post(f'channels/{id}/messages', {'content': message})

    def command(self, name: str) -> Callable:
        def inner(f: Callable):
            self._commands.append((name, f))
        return inner

    def add_command(self, name: str, f: Callable):
        self._commands.append((name, f))
