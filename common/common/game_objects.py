import math
import pygame
import random

class Weapon:
    def __init__(self, name, damage, fire_rate, bullet_speed, icon_color=(255,255,0), special_type=None, max_ammo=100):
        self.name = name
        self.damage = damage
        self.fire_rate = fire_rate  # milliseconds between shots
        self.bullet_speed = bullet_speed
        self.icon_color = icon_color
        self.special_type = special_type  # None, 'wall', 'mine'
        self.max_ammo = max_ammo

# Predefined weapons (icons will be colored rectangles for now)
WEAPON_LIST = [
    Weapon("Pistol", damage=25, fire_rate=250, bullet_speed=10, icon_color=(255,255,0), max_ammo=100), # Weakest
    Weapon("Weapon 3", damage=25, fire_rate=100, bullet_speed=15, icon_color=(255,0,255), max_ammo=150), # Same damage as Pistol
    Weapon("Wall Spawner", damage=0, fire_rate=1000, bullet_speed=0, icon_color=(150,75,0), special_type='wall', max_ammo=10),
    Weapon("Mine Placer", damage=150, fire_rate=1000, bullet_speed=0, icon_color=(255,0,0), special_type='mine', max_ammo=5), # More damage than Shotgun total
    Weapon("Shotgun", damage=40, fire_rate=750, bullet_speed=12, icon_color=(255,165,0), max_ammo=50), # 40 damage per bullet, 3 bullets = 120 total
]

def get_random_weapon():
    other_weapons = [w for w in WEAPON_LIST if w.name != "Pistol"]
    return random.choice(other_weapons) if other_weapons else WEAPON_LIST[0]

def get_weapon_by_name(name):
    for w in WEAPON_LIST:
        if w.name == name:
            return w
    return WEAPON_LIST[0]

class Player:
    def __init__(self, x, y, player_id):
        self.x = x
        self.y = y
        self.player_id = player_id
        self.angle = 0
        self.health = 500  # 500% życia
        self.speed = 5
        self.size = 30
        self.color = (0, 255, 0)  # Green for players
        self.bullets = []
        self.last_shot = 0
        basic_weapon = get_weapon_by_name("Pistol")
        self.weapons = [basic_weapon]
        self.selected_weapon_index = 0
        self.dead = False
        self.respawn_timer = 0
        self.ammo = {basic_weapon.name: basic_weapon.max_ammo}

    @property
    def current_weapon(self):
        return self.weapons[self.selected_weapon_index]

    def add_weapon(self, weapon):
        # Dodaj broń tylko jeśli jej jeszcze nie ma
        if all(w.name != weapon.name for w in self.weapons):
            self.weapons.append(weapon)
        # Niezależnie od tego, czy broń jest nowa, uzupełnij amunicję
        self.ammo[weapon.name] = weapon.max_ammo

    def switch_weapon(self, index):
        if 0 <= index < len(self.weapons):
            self.selected_weapon_index = index

    def move(self, dx, dy):
        self.x += dx * self.speed
        self.y += dy * self.speed

    def rotate(self, target_x, target_y):
        self.angle = math.degrees(math.atan2(target_y - self.y, target_x - self.x))

    def shoot(self, current_time):
        weapon = self.current_weapon
        if current_time - self.last_shot > weapon.fire_rate and self.ammo.get(weapon.name, 0) > 0:
            self.last_shot = current_time
            
            # Consume ammo for all weapon types
            self.ammo[weapon.name] -= 1
            
            if weapon.special_type is None:
                return Bullet(self.x, self.y, self.angle, self.player_id, weapon)
            elif weapon.special_type == 'wall' or weapon.special_type == 'mine':
                return None
        return None

    def kill(self):
        self.dead = True
        self.respawn_timer = 5  # 5 sekund

    def respawn(self):
        self.dead = False
        self.health = 500  # 500% życia
        self.x, self.y = 400, 300
        self.respawn_timer = 0
        # Reset weapon inventory to basic weapon
        basic_weapon = get_weapon_by_name("Pistol")
        self.weapons = [basic_weapon]
        self.selected_weapon_index = 0
        self.ammo = {basic_weapon.name: basic_weapon.max_ammo}

    def draw(self, screen, camera_offset=(0,0)):
        cx, cy = camera_offset
        # Draw player body
        pygame.draw.circle(screen, self.color, (int(self.x-cx), int(self.y-cy)), self.size)
        # Draw direction indicator
        end_x = self.x + math.cos(math.radians(self.angle)) * self.size
        end_y = self.y + math.sin(math.radians(self.angle)) * self.size
        pygame.draw.line(screen, (255, 0, 0), (self.x-cx, self.y-cy), (end_x-cx, end_y-cy), 3)

class Bullet:
    def __init__(self, x, y, angle, player_id, weapon=None):
        self.x = x
        self.y = y
        self.angle = angle
        self.player_id = player_id
        self.size = 5
        self.lifetime = 60  # frames
        if weapon:
            self.speed = weapon.bullet_speed
            self.damage = weapon.damage
            self.color = weapon.icon_color
        else:
            self.speed = 10
            self.damage = 25
            self.color = (255, 255, 0)

    def update(self):
        self.x += math.cos(math.radians(self.angle)) * self.speed
        self.y += math.sin(math.radians(self.angle)) * self.speed
        self.lifetime -= 1

    def draw(self, screen, camera_offset=(0,0)):
        cx, cy = camera_offset
        pygame.draw.circle(screen, self.color, (int(self.x-cx), int(self.y-cy)), self.size)

class Enemy:
    def __init__(self, x, y, enemy_type=1):
        self.x = x
        self.y = y
        self.type = enemy_type
        # Base speeds: Type 1: 15.0, Type 2: 10.0, Type 3: 7.0 (from last change)
        # Multiply by 5
        if self.type == 1:
            self.health = 100
            self.speed = 75.0 # 15.0 * 5
            self.size = 20
            self.color = (0, 255, 0)  # Zielony
            self.damage = 2
            self._initial_health = 100 # Do obliczania paska zdrowia
            self._is_shooter = False
            self._last_shot = 0
            self._fire_rate = 0
            self._bullet_damage = 0
            self._bullet_speed = 0
            
        elif self.type == 2:
            self.health = 200
            self.speed = 50.0 # 10.0 * 5
            self.size = 28
            self.color = (0, 128, 255)  # Niebieski
            self.damage = 5
            self._initial_health = 200
            self._is_shooter = False
            self._last_shot = 0
            self._fire_rate = 0
            self._bullet_damage = 0
            self._bullet_speed = 0

        elif self.type == 3:
            self.health = 400
            self.speed = 35.0 # 7.0 * 5
            self.size = 36
            self.color = (255, 0, 0)  # Czerwony
            self.damage = 12
            self._initial_health = 400
            self._is_shooter = False
            self._last_shot = 0
            self._fire_rate = 0
            self._bullet_damage = 0
            self._bullet_speed = 0

        elif self.type == 4: # Nowy typ: Strzelający wróg
             self.health = 150
             self.speed = 30.0 # Nieco wolniejszy niż biegacze
             self.size = 25
             self.color = (128, 0, 128) # Fioletowy
             self.damage = 5 # Obrażenia w kontakcie (jeśli dojdzie)
             self._initial_health = 150
             self._is_shooter = True # Ten wróg strzela
             self._last_shot = 0
             self._fire_rate = 1000 # Millisekundy między strzałami (np. 1 strzał na sekundę)
             self._bullet_damage = 15 # Obrażenia pocisku
             self._bullet_speed = 8 # Prędkość pocisku

        # Pola do patrolowania
        self._patrol_target = (self.x, self.y) # Cel patrolowania
        self._patrol_timer = 0 # Czas do zmiany celu
        self._patrol_duration = 2 # Sekundy na jeden kierunek patrolowania
        self.look_angle = 0 # Kąt, w którym patrzy wróg (synchronizowany)

    def move_towards(self, target_x, target_y):
        angle = math.atan2(target_y - self.y, target_x - self.x)
        dx = math.cos(angle) * self.speed
        dy = math.sin(angle) * self.speed
        return dx, dy, math.degrees(angle) # Zwróć wektor ruchu i kąt w stopniach

    def get_patrol_vector(self, dt):
        if self._patrol_timer <= 0:
            # Wylosuj nowy cel patrolowania w pobliżu
            target_angle_rad = random.uniform(0, 2 * math.pi)
            distance = random.uniform(50, 150)
            self._patrol_target = (self.x + math.cos(target_angle_rad) * distance, self.y + math.sin(target_angle_rad) * distance)
            self._patrol_timer = self._patrol_duration
        
        # Sprawdź czy dotarto do celu, jeśli tak, wylosuj nowy cel
        dist_to_target = ((self._patrol_target[0] - self.x)**2 + (self._patrol_target[1] - self.y)**2)**0.5
        if dist_to_target < self.speed * dt * 2: # Jeśli blisko celu (uwzględnij prędkość)
             self._patrol_timer = 0 # Wymuś wylosowanie nowego celu
             return self.get_patrol_vector(dt) # Wylosuj nowy cel i zwróc nowy wektor/kąt

        self._patrol_timer -= dt
        return self.move_towards(self._patrol_target[0], self._patrol_target[1]) # move_towards teraz zwraca kąt

    def draw(self, screen, camera_offset=(0,0)):
        cx, cy = camera_offset
        # Draw enemy body
        pygame.draw.circle(screen, self.color, (int(self.x-cx), int(self.y-cy)), self.size)
        
        # Draw HP bar above the enemy
        bar_width = self.size * 2
        bar_height = 5
        hp_bar_x = int(self.x - cx - bar_width / 2)
        hp_bar_y = int(self.y - cy - self.size - 15)
        current_hp_width = (self.health / self._initial_health) * bar_width # Użyj _initial_health do obliczeń
        
        # Rysuj tło paska zdrowia
        pygame.draw.rect(screen, (255, 0, 0), (hp_bar_x, hp_bar_y, bar_width, bar_height)) # Czerwone tło
        # Rysuj aktualne zdrowie
        pygame.draw.rect(screen, (0, 255, 0), (hp_bar_x, hp_bar_y, current_hp_width, bar_height)) # Zielony pasek

        # Draw eyes (simple dots based on look_angle)
        angle_rad = math.radians(self.look_angle) # Użyj look_angle z obiektu
        eye_distance = self.size // 3
        eye_offset_angle_rad = math.radians(30) # Rozstawienie oczu w radianach

        # Lewe oko
        eye1_angle = angle_rad - eye_offset_angle_rad
        eye1_x = self.x + math.cos(eye1_angle) * eye_distance
        eye1_y = self.y + math.sin(eye1_angle) * eye_distance
        pygame.draw.circle(screen, (0, 0, 0), (int(eye1_x - cx), int(eye1_y - cy)), max(1, self.size // 6)) # Czarne oko

        # Prawe oko
        eye2_angle = angle_rad + eye_offset_angle_rad
        eye2_x = self.x + math.cos(eye2_angle) * eye_distance
        eye2_y = self.y + math.sin(eye2_angle) * eye_distance
        pygame.draw.circle(screen, (0, 0, 0), (int(eye2_x - cx), int(eye2_y - cy)), max(1, self.size // 6)) # Czarne oko

class Wall:
    def __init__(self, x, y, width, height, is_player_wall=False, health=100):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = (255, 255, 0) if not is_player_wall else (0, 200, 255)  # Jasnożółty dla zwykłych, Cyan dla stawianych
        self.is_player_wall = is_player_wall
        self.health = health

    def draw(self, screen, camera_offset=(0,0)):
        cx, cy = camera_offset
        r = self.rect.move(-cx, -cy)
        pygame.draw.rect(screen, self.color, r)
        if self.is_player_wall:
            pygame.draw.rect(screen, (255,255,255), r, 2)  # White border for player walls

class LootBox:
    def __init__(self, x, y, weapon=None):
        self.x = x
        self.y = y
        self.size = 15
        self.color = (255, 215, 0)  # Gold
        self.weapon = weapon if weapon else get_random_weapon()

    def draw(self, screen, camera_offset=(0,0)):
        cx, cy = camera_offset
        pygame.draw.rect(screen, self.color, (int(self.x - self.size/2 - cx), int(self.y - self.size/2 - cy), self.size, self.size))
        pygame.draw.rect(screen, self.weapon.icon_color, (int(self.x - self.size/2 - cx), int(self.y - self.size/2 - cy), self.size, 5))
        font = pygame.font.SysFont(None, 16)
        text = font.render(self.weapon.name, True, (0,0,0))
        screen.blit(text, (self.x - self.size/2 - cx, self.y - self.size/2 - 10 - cy))

class Mine:
    def __init__(self, x, y, owner_id, damage=50):
        self.x = x
        self.y = y
        self.size = 12
        self.owner_id = owner_id
        self.damage = damage
        self.color = (255, 0, 0)
        self.active = True

    def draw(self, screen, camera_offset=(0,0)):
        cx, cy = camera_offset
        pygame.draw.circle(screen, self.color, (int(self.x-cx), int(self.y-cy)), self.size)
        pygame.draw.circle(screen, (0,0,0), (int(self.x-cx), int(self.y-cy)), self.size-4) 