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
__author__ = 'Matt "Celeo" Boulanger'
__email__ = 'celeodor@gmail.com'
__license__ = 'MIT'
__version__ = '1.0.0'


class WebSocketEvent(enum.Enum):
    """Enum for the different websocket events

    Attributes:
        name: name of the event
        value: int value of the event
    """

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
        """Gets the enum for the op code

        Args:
            op: value of the op code (will be casted to int)

        Returns:
            The enum that matches the op code
        """
        for event in cls:
            if event.value == int(op):
                return event
        return None


class WebSocketKeepAlive(threading.Thread):
    """Keep alive thread for sending websocket heartbeats

    Attributes:
        logger: a copy of the Pycord object's logger
        ws: a copy of the Pycord object's websocket connection
        interval: the set heartbeat interval
    """

    def __init__(self, logger: logging.Logger, ws: websocket.WebSocketApp, interval: float) -> None:
        super().__init__(name='Thread-ws_keep_alive')
        self.logger = logger
        self.ws = ws
        self.interval = interval

    def run(self):
        """Runs the thread

        This method handles sending the heartbeat to the Discord websocket server, so the connection
        can remain open and the bot remain online for those commands that require it to be.

        Args:
            None
        """
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
    """Wrapper thread for the ``websocket.WebSocketApp.run_forever`` methods

    Runs the ``run_forever`` method of the websocket app.
    """

    def __init__(self, ws: websocket.WebSocketApp) -> None:
        super().__init__(name='Thread-ws_run_forever')
        self.ws = ws

    def run(self):
        """Runs the thread

        Args:
            None
        """
        self.ws.run_forever()


class Pycord:
    """Main library class; handles connecting and accessing the Discord APIs

    Attributes:
        token: the user-supplied token used for authentication
        user_agent: the user-supplied or defaulted HTTP user agent
        connected: a bool value if the websocket connection is open
    """

    url_base = 'https://discordapp.com/api/'

    def __init__(self, token: str, user_agent: str=None, logging_level: int=logging.DEBUG, log_to_console: bool=True) -> None:
        """Class init method

        Only sets up the class, does not start the websocket connection. For that, you'll need to
        call ``connect_to_websocket`` on the resulting object.

        Args:
            token: the bot authentication token
            user_agent: your selected user agent for HTTP requests see
                https://discordapp.com/developers/docs/reference for more information
            logging_level: the desired logging level for the internal logger
            log_to_console: whether or not to log to the console as well as the file
        """
        self.token = token
        self.user_agent = user_agent or f'Pycord (github.com/Celeo/Pycord, {__version__})'
        self._setup_logger(logging_level, log_to_console)
        self.connected = False
        self._commands = []

    # =================================================
    # Private methods
    # =================================================

    def _setup_logger(self, logging_level: int, log_to_console: bool):
        """Sets up the internal logger

        Args:
            logging_level: what logging level to use
            log_to_console: whether or not to log to the console
        """
        self.logger = logging.getLogger('discord')
        self.logger.setLevel(logging_level)
        formatter = logging.Formatter(style='{', fmt='{asctime} [{levelname}] {message}', datefmt='%Y-%m-%d %H:%M:%S')
        file_handler = logging.FileHandler('pycord.log')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging_level)
        self.logger.addHandler(file_handler)
        if log_to_console:
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(formatter)
            stream_handler.setLevel(logging_level)
            self.logger.addHandler(stream_handler)

    # =====================
    # REST API
    # =====================

    def __build_headers(self) -> Dict[str, str]:
        """Creates the headers required for HTTP requests

        Args:
            None

        Returns:
            Dictionary of header keys and values
        """
        return {
            'Authorization': f'Bot {self.token}',
            'User-Agent': self.user_agent,
            'Content-Type': 'application/json'
        }

    def __get(self, path: str) -> Dict[str, Any]:
        """Makes an HTTP GET request to the Discord REST API

        Args:
            path: the URI path (not including the base url, start with the first
                uri segment, like 'users/...')

        Returns:
            Dictionary from the JSON response
        """
        url = Pycord.url_base + path
        self.logger.debug(f'Making GET request to "{url}"')
        r = requests.get(url, headers=self.__build_headers())
        self.logger.debug(f'GET response from "{url}" was "{r.status_code}"')
        if r.status_code != 200:
            raise ValueError(f'Non-200 GET response from Discord API ({r.status_code}): {r.text}')
        return r.json()

    def __post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Makes an HTTP POST request to the Discord REST API

        Args:
            path: the URI path (not including the base url, start with the first
                uri segment, like 'users/...')
            data: the data to send as JSON data

        Returns:
            Dictionary from the JSON response
        """
        url = Pycord.url_base + path
        self.logger.debug(f'Making POST request to "{url}"')
        r = requests.post(url, headers=self.__build_headers(), json=data)
        self.logger.debug(f'POST response from "{url}" was "{r.status_code}"')
        if r.status_code != 200:
            raise ValueError(f'Non-200 POST response from Discord API ({r.status_code}): {r.text}')
        return r.json()

    def _get_websocket_address(self) -> str:
        """Queries the Discord REST API for the websocket URL

        Args:
            None

        Returns:
            The URL of websocket connection
        """
        return self.__get('gateway')['url']

    # =====================
    # Websocket API
    # =====================

    def _ws_on_message(self, ws: websocket.WebSocketApp, message: Union[str, bytes]):
        """Callback for receiving messages from the websocket connection

        This method receives ALL events from the websocket connection, some of which
        are used for the initial authentication flow, some of which are used for maintaining
        the connection, some of which are for notifying this client of user states, etc.
        Only a few of the events are really worth listening to by "downstream" clients,
        mostly chat events (``WebSocketEvent.DISPATCH`` with element ``t`` == 'MESSAGE_CREATE'),
        and those can be accessed by clients using this library via the command registration,
        which is handled by this method.

        Args:
            ws: websocket connection
            message: message received from the connection; either string or bytes, the latter
                is a zlip-compressed string. Either way, the end result of formatting is JSON
        """
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
        """Callback for receiving errors from the websocket connection

        Args:
            ws: websocket connection
            error: exception raised
        """
        self.logger.error(f'Got error from websocket connection: {str(error)}')

    def _ws_on_close(self, ws: websocket.WebSocketApp):
        """Callback for closing the websocket connection

        Args:
            ws: websocket connection (now closed)
        """
        self.connected = False
        self.logger.error('Websocket closed')

    def _ws_on_open(self, ws: websocket.WebSocketApp):
        """Callback for sending the initial authentication data

        This "payload" contains the required data to authenticate this websocket
        client as a suitable bot connection to the Discord websocket.

        Args:
            ws: websocket connection
        """
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
        """Call this method to make the connection to the Discord websocket

        This method is not blocking, so you'll probably want to call it after
        initializating your Pycord object, and then move on with your code. When
        you want to block on just maintaining the websocket connection, then call
        ``keep_running``, and it'll block until your application is interrupted.

        Args:
            None
        """
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
        """Call this method to block on the maintenance of the websocket connection.

        Unless you interrupt this method, it will block continuously, as the websocket
        connection is simply maintained with keep alives. This method should be called
        at the end of your bot setup, as registered commands will be heard by the client
        from Discord users and processed here.

        Args:
            None
        """
        self.__ws_run_forever_wrapper.join()

    def get_basic_bot_info(self) -> Dict[str, Any]:
        """Gets bot info (REST query)

        Args:
            None

        Returns:
            Dictionary of information about the bot. You're responsible for accessing
            which attribute(s) you want.

            Example:
                {
                    "id": "80351110224678912",
                    "username": "Nelly",
                    "discriminator": "1337",
                    "avatar": "8342729096ea3675442027381ff50dfe",
                    "verified": true,
                    "email": "nelly@discordapp.com"
                }
        """
        return self.__get('users/@me')

    def get_connected_guilds(self) -> Dict[str, Any]:
        """Get connected guilds (REST query)

        As your bot is added to guilds, it will need to know what's it's
        connected to. Call this method to get a list of Guild objects.

        Args:
            None

        Returns:
            List of dictionary objects of guilds your bot is connected to.

            Example:
                [
                    {
                        "id": "41771983423143937",
                        "name": "Discord Developers",
                        "icon": "SEkgTU9NIElUUyBBTkRSRUkhISEhISEh",
                        "splash": null,
                        "owner_id": "80351110224678912",
                        "region": "us-east",
                        "afk_channel_id": "42072017402331136",
                        "afk_timeout": 300,
                        "embed_enabled": true,
                        "embed_channel_id": "41771983444115456",
                        "verification_level": 1,
                        "roles": [],
                        "emojis": [],
                        "features": ["INVITE_SPLASH"],
                        "unavailable": false
                    },
                    {
                        "id": "41771983423143937",
                        "name": "Discord Developers",
                        "icon": "SEkgTU9NIElUUyBBTkRSRUkhISEhISEh",
                        "splash": null,
                        "owner_id": "80351110224678912",
                        "region": "us-east",
                        "afk_channel_id": "42072017402331136",
                        "afk_timeout": 300,
                        "embed_enabled": true,
                        "embed_channel_id": "41771983444115456",
                        "verification_level": 1,
                        "roles": [],
                        "emojis": [],
                        "features": ["INVITE_SPLASH"],
                        "unavailable": false
                    }
                ]
        """
        return self.__get('users/@me/guilds')

    def get_guild_info(self, id: str) -> Dict[str, Any]:
        """Get a guild's information by its id

        Args:
            id: snowflake id of the guild

        Returns:
            Dictionary data for the guild API object

            Example:
                {
                    "id": "41771983423143937",
                    "name": "Discord Developers",
                    "icon": "SEkgTU9NIElUUyBBTkRSRUkhISEhISEh",
                    "splash": null,
                    "owner_id": "80351110224678912",
                    "region": "us-east",
                    "afk_channel_id": "42072017402331136",
                    "afk_timeout": 300,
                    "embed_enabled": true,
                    "embed_channel_id": "41771983444115456",
                    "verification_level": 1,
                    "roles": [],
                    "emojis": [],
                    "features": ["INVITE_SPLASH"],
                    "unavailable": false
                }
        """
        return self.__get(f'guilds/{id}')

    def get_channels_in(self, guild_id: str) -> Dict[str, Any]:
        """Get a list of channels in the guild

        Args:
            guild_id: id of the guild to fetch channels from

        Returns:
            List of dictionary objects of channels in the guild. Note the different
            types of channels: text, voice, DM, group DM.

            https://discordapp.com/developers/docs/resources/channel#channel-object

            Example:
                [
                    {
                        "id": "41771983423143937",
                        "guild_id": "41771983423143937",
                        "name": "general",
                        "type": 0,
                        "position": 6,
                        "permission_overwrites": [],
                        "topic": "24/7 chat about how to gank Mike #2",
                        "last_message_id": "155117677105512449"
                    },
                    {
                        "id": "155101607195836416",
                        "guild_id": "41771983423143937",
                        "name": "ROCKET CHEESE",
                        "type": 2,
                        "position": 5,
                        "permission_overwrites": [],
                        "bitrate": 64000,
                        "user_limit": 0
                    },
                    {
                        "last_message_id": "3343820033257021450",
                        "type": 1,
                        "id": "319674150115610528",
                        "recipients": [
                            {
                                "username": "test",
                                "discriminator": "9999",
                                "id": "82198898841029460",
                                "avatar": "33ecab261d4681afa4d85a04691c4a01"
                            }
                        ]
                    }
                ]
        """
        return self.__get(f'guilds/{guild_id}/channels')

    def get_channel_info(self, id: str) -> Dict[str, Any]:
        """Get a chanel's information by its id

        Args:
            id: snowflake id of the chanel

        Returns:
            Dictionary data for the chanel API object

            Example:
                {
                    "id": "41771983423143937",
                    "guild_id": "41771983423143937",
                    "name": "general",
                    "type": 0,
                    "position": 6,
                    "permission_overwrites": [],
                    "topic": "24/7 chat about how to gank Mike #2",
                    "last_message_id": "155117677105512449"
                }
        """
        return self.__get(f'channels/{id}')

    def send_message(self, id: str, message: str) -> Dict[str, Any]:
        """Send a message to a channel

        For formatting options, see the documentation:
            https://discordapp.com/developers/docs/resources/channel#create-message

        Args:
            id: channel snowflake id
            message: your message (string)

        Returns:
            Dictionary object of the new message
        """
        if not self.connected:
            raise ValueError('Websocket not connected')
        return self.__post(f'channels/{id}/messages', {'content': message})

    def command(self, name: str) -> Callable:
        """Decorator to wrap methods to register them as commands

        The argument to this method is the command that you want to trigger your
        callback. If you want users to send "!hello bob" and your method "command_hello"
        to get called when someone does, then your setup will look like:

            @pycord.command('hello')
            def command_hello(data):
                # do stuff here

        The ``data`` argument that your method will receive is the message object.

        Example:
            {
                "reactions": [
                    {
                        "count": 1,
                        "me": false,
                        "emoji": {
                            "id": null,
                            "name": "🔥"
                        }
                    }
                ],
                "attachments": [],
                "tts": false,
                "embeds": [],
                "timestamp": "2017-07-11T17:27:07.299000+00:00",
                "mention_everyone": false,
                "id": "334385199974967042",
                "pinned": false,
                "edited_timestamp": null,
                "author": {
                    "username": "Mason",
                    "discriminator": "9999",
                    "id": "53908099506183680",
                    "avatar": "a_bab14f271d565501444b2ca3be944b25"
                },
                "mention_roles": [],
                "content": "Supa Hot",
                "channel_id": "290926798999357250",
                "mentions": [],
                "type": 0
            }

        Args:
            name: command name

        Returns:
            Method decorator
        """
        def inner(f: Callable):
            self._commands.append((name, f))
        return inner

    def register_command(self, name: str, f: Callable):
        """Registers an existing callable object as a command callback

        This method can be used instead of the ``@command`` decorator. Both
        do the same thing, but this method is useful for registering callbacks
        for methods defined before or outside the scope of your bot object,
        allowing you to define methods in another file or wherever, import them,
        and register them.

        See the documentation for the ``@command`` decorator for more information
        on what you method will receive.

        Example:

            def process_hello(data):
                # do stuff

            # later, somewhere else, etc.

            pycord.register_command('hello', process_hello)

        Args:
            name: the command to trigger the callback (see ``@command`` documentation)
            f: callable that will be triggered on command processing
        """
        self._commands.append((name, f))
