import logging

import pytest
import io
import json
import requests

import pycord


def json_to_bytes(data):
    return io.BytesIO(json.dumps(data).encode('utf-8'))


class TestWebSocketEvent():

    def test_parse(self):
        assert pycord.WebSocketEvent.parse(0) == pycord.WebSocketEvent.DISPATCH
        assert pycord.WebSocketEvent.parse(6) == pycord.WebSocketEvent.RESUME
        assert pycord.WebSocketEvent.parse('10') == pycord.WebSocketEvent.HELLO
        assert pycord.WebSocketEvent.parse(11.00000) == pycord.WebSocketEvent.HEARTBEAT_ACK
        assert pycord.WebSocketEvent.parse(-1) is None
        assert pycord.WebSocketEvent.parse(400) is None


class TestWebSocketKeepAlive():

    def test_exists(self):
        assert pycord.WebSocketKeepAlive


class TestWebSocketRunForeverWrapper():

    def test_exists(self):
        assert pycord.WebSocketRunForeverWrapper


class TestPycordLogger():

    def test_setup_logger(self):
        cord = pycord.Pycord('')
        assert len(cord.logger.handlers) == 2
        assert isinstance(cord.logger.handlers[0], logging.FileHandler)
        assert isinstance(cord.logger.handlers[1], logging.StreamHandler)

    def test_default_logging_level(self):
        cord = pycord.Pycord('')
        assert cord.logger.level == logging.DEBUG
        for handler in cord.logger.handlers:
            assert handler.level == logging.DEBUG

    def test_custom_logging_level(self):
        cord = pycord.Pycord('', logging_level=logging.WARNING)
        assert cord.logger.level == logging.WARNING
        for handler in cord.logger.handlers:
            assert handler.level == logging.WARNING

    def test_no_console_logger(self):
        cord = pycord.Pycord('', log_to_console=False)
        assert len(cord.logger.handlers) == 1
        assert isinstance(cord.logger.handlers[0], logging.FileHandler)


class TestPycordUserAgent():

    def test_default_useragent(self):
        cord = pycord.Pycord('')
        assert cord.user_agent == f'Pycord (github.com/Celeo/Pycord, {pycord.__version__})'

    def test_override_useragent(self):
        agent = 'Hello world, this is a test'
        cord = pycord.Pycord('', user_agent=agent)
        assert cord.user_agent == agent


class TestPycordToken():

    def test_instantiate_no_token(self):
        with pytest.raises(TypeError):
            pycord.Pycord()

    def test_instantiate_blank_token(self):
        # for now, this is allowed
        assert pycord.Pycord('')


class TestPycordRestApi():

    def test_build_headers(self):
        cord = pycord.Pycord('foo.bar.baz', user_agent='hello world')
        headers = cord._build_headers()
        assert len(headers) == 3
        assert headers['Authorization'] == 'Bot foo.bar.baz'
        assert headers['User-Agent'] == 'hello world'
        assert headers['Content-Type'] == 'application/json'

    def test_get_websocket_address(self, monkeypatch):

        url = 'foobar'

        def mock(path, headers):
            r = requests.Response()
            r.status_code = 200
            r.raw = json_to_bytes({
                'url': url
            })
            return r

        monkeypatch.setattr(requests, 'get', mock)
        cord = pycord.Pycord('')
        assert cord._get_websocket_address() == url

    def test_rest_get_api_calls(self, monkeypatch):

        data = {"foo": "bar"}

        def mock(path, headers):
            r = requests.Response()
            r.status_code = 200
            r.raw = json_to_bytes(data)
            return r

        monkeypatch.setattr(requests, 'get', mock)
        cord = pycord.Pycord('')
        funcs = (
            (cord.get_basic_bot_info, ()),
            (cord.get_connected_guilds, ()),
            (cord.get_guild_info, ('', )),
            (cord.get_channels_in, ('', )),
            (cord.get_channel_info, ('', ))
        )
        for func in funcs:
            assert func[0](*func[1]) == data

    def test_register_command(self):
        cord = pycord.Pycord('')
        assert len(cord._commands) == 0
        cord.register_command('', lambda x: x)
        assert len(cord._commands) == 1

    def test_command_decorator(self):
        cord = pycord.Pycord('')
        assert len(cord._commands) == 0

        @cord.command('')
        def _():
            pass

        assert len(cord._commands) == 1
