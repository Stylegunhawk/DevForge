from pydoc import describe


class Player:
    game_version = "1.0"  # Class attribute (shared)
    description = "A player in the game"
    count = 0
    def __init__(self, name):
        self.name = name     # Instance attribute (unique)
        self.score = 0
        Player.count += 1

p1 = Player("Alice")
p2 = Player("Bob")
p3 = Player("c")
p1.score = 100
print(p1.game_version, p1.score)  # 1.0 100
print(p2.game_version, p2.score)  # 1.0 0 (score unique!)
print(Player.count)