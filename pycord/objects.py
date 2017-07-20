class DiscordObject:

    def __init__(self, id, name):
        self.id = id
        self.name = name


class Guild(DiscordObject):

    def __init__(self, id, name, roles):
        super().__init__(id, name)
        self.roles = roles


class Channel(DiscordObject):

    def __init__(self, id, name):
        super().__init__(id, name)


class User(DiscordObject):

    def __init__(self, id, name):
        super().__init__(id, name)
