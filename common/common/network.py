import json
import socket
import pickle
import struct
from common.game_objects import Player, Enemy, Bullet, Wall, LootBox, Mine, get_weapon_by_name

class NetworkProtocol:
    @staticmethod
    def create_message(message_type, data):
        message = {
            'type': message_type,
            'data': data
        }
        return pickle.dumps(message)

    @staticmethod
    def send_message(sock, message):
        message_data = NetworkProtocol.create_message(message['type'], message['data'])
        message_length = len(message_data)
        sock.sendall(struct.pack('!I', message_length))
        sock.sendall(message_data)

    @staticmethod
    def receive_message(sock):
        # Read message length
        length_data = sock.recv(4)
        if not length_data:
            return None
        message_length = struct.unpack('!I', length_data)[0]
        
        # Read message data
        message_data = b''
        while len(message_data) < message_length:
            chunk = sock.recv(min(message_length - len(message_data), 4096))
            if not chunk:
                return None
            message_data += chunk
        
        return pickle.loads(message_data)

class GameState:
    def __init__(self):
        self.players = {}
        self.enemies = []
        self.walls = []
        self.bullets = []
        self.lootboxes = []
        self.mines = []
        self.game_over = False
        self.wave = 1
        self.wave_cooldown = 0
        self.scores = {}  # Dictionary to store player scores

    def to_dict(self):
        return {
            'players': {pid: {
                'x': p.x,
                'y': p.y,
                'angle': p.angle,
                'health': p.health,
                'weapons': [w.name for w in p.weapons],
                'selected_weapon_index': p.selected_weapon_index,
                'dead': getattr(p, 'dead', False),
                'respawn_timer': getattr(p, 'respawn_timer', 0),
                'ammo': getattr(p, 'ammo', {})
            } for pid, p in self.players.items()},
            'enemies': [{'x': e.x, 'y': e.y, 'health': e.health, 'type': getattr(e, 'type', 1), 'look_angle': getattr(e, 'look_angle', 0)} for e in self.enemies],
            'bullets': [{'x': b.x, 'y': b.y, 'angle': b.angle, 'player_id': b.player_id, 'color': getattr(b, 'color', (255,255,0))} for b in self.bullets],
            'lootboxes': [{'x': l.x, 'y': l.y, 'weapon': l.weapon.name} for l in self.lootboxes],
            'mines': [{'x': m.x, 'y': m.y, 'owner_id': m.owner_id, 'damage': m.damage, 'active': m.active} for m in self.mines],
            'walls': [{'x': w.rect.x, 'y': w.rect.y, 'width': w.rect.width, 'height': w.rect.height, 'is_player_wall': w.is_player_wall, 'health': w.health} for w in self.walls],
            'game_over': self.game_over,
            'wave': self.wave,
            'wave_cooldown': self.wave_cooldown,
            'scores': self.scores
        }

    @classmethod
    def from_dict(cls, data):
        from common.game_objects import Player, Enemy, Bullet, LootBox, Mine, get_weapon_by_name, Wall
        state = cls()

        for pid, p_data in data['players'].items():
            player = Player(p_data['x'], p_data['y'], pid)
            player.angle = p_data['angle']
            player.health = p_data['health']
            player.weapons = [get_weapon_by_name(name) for name in p_data.get('weapons', ['Pistol'])]
            player.selected_weapon_index = p_data.get('selected_weapon_index', 0)  # Always deserialize the selected index
            player.dead = p_data.get('dead', False)
            player.respawn_timer = p_data.get('respawn_timer', 0)
            # Properly deserialize ammo state
            player.ammo = {}
            for weapon_name, ammo_count in p_data.get('ammo', {}).items():
                player.ammo[weapon_name] = ammo_count
            state.players[pid] = player
        for e_data in data['enemies']:
            enemy = Enemy(e_data['x'], e_data['y'], e_data.get('type', 1))
            enemy.health = e_data['health']
            enemy.look_angle = e_data.get('look_angle', 0) # Deserialize look_angle
            state.enemies.append(enemy)
        for b_data in data['bullets']:
            bullet = Bullet(b_data['x'], b_data['y'], b_data['angle'], b_data['player_id'])
            if 'color' in b_data:
                bullet.color = b_data['color']
            state.bullets.append(bullet)
        for l_data in data.get('lootboxes', []):
            weapon = get_weapon_by_name(l_data['weapon'])
            lootbox = LootBox(l_data['x'], l_data['y'], weapon)
            state.lootboxes.append(lootbox)
        for m_data in data.get('mines', []):
            mine = Mine(m_data['x'], m_data['y'], m_data['owner_id'], m_data['damage'])
            mine.active = m_data.get('active', True)
            state.mines.append(mine)
        for w_data in data.get('walls', []):
            wall = Wall(w_data['x'], w_data['y'], w_data['width'], w_data['height'], w_data.get('is_player_wall', False), w_data.get('health', 100))
            state.walls.append(wall)
        state.game_over = data.get('game_over', False)
        state.wave = data.get('wave', 1)
        state.wave_cooldown = data.get('wave_cooldown', 0)
        state.scores = data.get('scores', {})
        return state 