# Pycord

Super simple Discord API layer. If you want something full-featured, this isn't it. Try [discord.py](https://github.com/Rapptz/discord.py).

This library is suitable for simple bots that allow users to send commands.

## Installation for development

1. Clone from GitHub
2. Setup virtual environment: `virtualenv env -p python3.6`
3. Activate: `source env/bin/activate`
4. Install libraries: `pip install -r requirements.txt`

## Installation for use

1. Use pip: `pip install pycordlib`

## Making a bot

Import the Pycord object and instantiate it, passing in your bot token ([need a token?](https://discordapp.com/developers/applications/me)):

```python
from pycord import Pycord


pycord = Pycord('your.token.here')
```

From there, you'll want to start the websocket connection:

```python
pycord.connect_to_websocket()
```

Next, you'll want to register some command callbacks. There are two ways to do this, depending on how you want to lay out your code (you can mix and match):

```python
# immediate registeration via decorator

@pycord.command('hello')
def hello(data):
    # do stuff


# delayed registeration
def hello(data):
    # do stuff

# later
pycord.register_command('hello', hello)
```

The method names don't matter; the string you register the callback with is what determines what the bot listens for.

All commands start with `!`. Examples:

> !hello bob

```python
@pycord.command('hello')
def do_hello_command(data):
    pycord.send_message(data['channel_id'], 'Hello '+ data['author']['username'])
```

## Callbacks

In addition to registering commands, you can also register some methods to be called whenever specific events are dispatched to the client.

These events can reached through adding entries in the `Pycord.callbacks` dictionary. The keys should be `PycordCallback` enums, and the values should be callables that take a single parameter.

Example:

```python
from pycord import Pycord, PycordCallback


def user_first_joins_server(data):
    bot.send_message('some_channel_id', data['d']['user']['username'] + ' just joined for the first time!')


cord = Pycord('my.bot.token')
cord.callbacks = {
    PycordCallback.USER_FIRST_TIME_JOIN: user_first_joins_server
}
cord.connect_to_websocket()
cord.keep_running()

```

## Adding your bot to your Discord server

Per [the OAuth2 documentation](https://discordapp.com/developers/docs/topics/oauth2#adding-bots-to-guilds), you'll need to generate a link and then
have someone who is an admin on the desired server click it, log in, and accept the bot.

The link will look like this:

https://discordapp.com/api/oauth2/authorize?client_id=[id]&scope=bot&permissions=[perms]

* [id] is the bot's "Client Id", accessible on [your app's page](https://discordapp.com/developers/applications/me)
* [perms] is the bot's required permissions.

For bots made with this library, you'll likely need the "Read Messages" and "Send Messages" permissions. That's permission code `3072`.

There's a super-handy [permissions calculator here](https://discordapi.com/permissions.html) if I add more to the library and you want to use it.
