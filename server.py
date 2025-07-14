import socket
import threading
import time
import random
import math
import pygame
import heapq
from common.game_objects import Player, Enemy, Bullet, Wall, LootBox, get_random_weapon, Mine, Pickup, get_weapon_by_name
from common.network import NetworkProtocol, GameState

class GameServer:
    def __init__(self, host='0.0.0.0', port=5555):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((host, port))
        self.server.listen(3)  # Allow up to 3 players
        self.game_state = GameState()
        self.clients = {}
        self.running = True
        self.last_enemy_spawn = 0
        self.enemy_spawn_delay = 3  # seconds
        self.player_inputs = {}  # Store latest input for each player
        self.last_shot_times = {}  # For special weapons
        self.game_over = False
        self.wave = 1
        self.wave_in_progress = False
        self.wave_cooldown = 0
        self.zombies_to_spawn = 0

        # Initialize scores in game state
        self.game_state.scores = {}

        # Create some walls (simple maze)
        self.game_state.walls = [
            # Border walls (indestructible)
            Wall(0, 0, 4000, 20, is_indestructible=True),
            Wall(0, 2980, 4000, 20, is_indestructible=True),
            Wall(0, 0, 20, 3000, is_indestructible=True),
            Wall(3980, 0, 20, 3000, is_indestructible=True),

            # Main corridors and rooms (indestructible)
            # Central hub
            Wall(1800, 1300, 400, 400, is_indestructible=True),
            
            # Corridors from central hub
            Wall(1800, 1100, 400, 20, is_indestructible=True),  # North corridor
            Wall(1800, 1700, 400, 20, is_indestructible=True),  # South corridor
            Wall(1600, 1300, 20, 400, is_indestructible=True),  # West corridor
            Wall(2180, 1300, 20, 400, is_indestructible=True),  # East corridor
            
            # Side rooms
            Wall(800, 800, 400, 400, is_indestructible=True),  # North-west room
            Wall(2800, 800, 400, 400, is_indestructible=True),  # North-east room
            Wall(800, 1800, 400, 400, is_indestructible=True),  # South-west room
            Wall(2800, 1800, 400, 400, is_indestructible=True),  # South-east room
            
            # Boss rooms (green)
            Wall(400, 400, 300, 300, is_indestructible=True),  # North-west boss room
            Wall(3300, 400, 300, 300, is_indestructible=True),  # North-east boss room
            Wall(400, 2300, 300, 300, is_indestructible=True),  # South-west boss room
            
            # Additional corridors
            Wall(800, 1100, 20, 200, is_indestructible=True),  # North-west entrance
            Wall(3180, 1100, 20, 200, is_indestructible=True),  # North-east entrance
            Wall(800, 1700, 20, 200, is_indestructible=True),  # South-west entrance
            Wall(3180, 1700, 20, 200, is_indestructible=True),  # South-east entrance
            
            # Boss room entrances
            Wall(400, 700, 200, 20, is_indestructible=True),  # North-west boss entrance
            Wall(3400, 700, 200, 20, is_indestructible=True),  # North-east boss entrance
            Wall(400, 2000, 200, 20, is_indestructible=True),  # South-west boss entrance
            
            # Additional maze corridors
            Wall(1200, 600, 20, 400, is_indestructible=True),
            Wall(1200, 2000, 20, 400, is_indestructible=True),
            Wall(2800, 600, 20, 400, is_indestructible=True),
            Wall(2800, 2000, 20, 400, is_indestructible=True),
            Wall(600, 1200, 400, 20, is_indestructible=True),
            Wall(600, 1600, 400, 20, is_indestructible=True),
            Wall(3000, 1200, 400, 20, is_indestructible=True),
            Wall(3000, 1600, 400, 20, is_indestructible=True),
            
            # Additional connecting corridors
            Wall(1400, 800, 20, 200, is_indestructible=True),
            Wall(2600, 800, 20, 200, is_indestructible=True),
            Wall(1400, 2000, 20, 200, is_indestructible=True),
            Wall(2600, 2000, 20, 200, is_indestructible=True),
        ]
        self.game_state.lootboxes = []
        self.game_state.mines = []

        # Define enemy spawn points
        self.enemy_spawn_points = [
            (500, 500),     # North-west boss room
            (3400, 500),    # North-east boss room
            (500, 2400),    # South-west boss room
            (900, 900),     # North-west room
            (2900, 900),    # North-east room
            (900, 1900),    # South-west room
            (2900, 1900),   # South-east room
            (1900, 1100),   # North corridor
            (1900, 1700),   # South corridor
            (1700, 1400),   # West corridor
            (2100, 1400),   # East corridor
        ]

        # Define boss spawn points
        self.boss_spawn_points = [
            (550, 550),     # North-west boss room
            (3450, 550),    # North-east boss room
            (550, 2450),    # South-west boss room
        ]

        print(f"Server started on {host}:{port}")
        print("Waiting for players to connect...")

    def handle_client(self, client_socket, address):
        player_id = len(self.clients)
        
        # Znajdź bezpieczne miejsce do spawnu
        spawn_successful = False
        spawn_attempts = 0
        spawn_x, spawn_y = 400, 300  # Domyślna pozycja spawnu
        
        while not spawn_successful and spawn_attempts < 50:
            # Sprawdź czy pozycja spawnu nie koliduje ze ścianą
            player_rect = pygame.Rect(spawn_x - 30, spawn_y - 30, 60, 60)  # 30 to rozmiar gracza
            collision = False
            
            for wall in self.game_state.walls:
                if wall.rect.colliderect(player_rect):
                    collision = True
                    break
            
            if not collision:
                spawn_successful = True
            else:
                # Spróbuj znaleźć nowe miejsce wokół centralnego punktu
                angle = random.uniform(0, 2 * math.pi)
                distance = random.uniform(50, 200)  # Szukaj w promieniu 50-200 pikseli
                spawn_x = 400 + math.cos(angle) * distance
                spawn_y = 300 + math.sin(angle) * distance
                spawn_attempts += 1
        
        # Jeśli nie znaleziono bezpiecznego miejsca, użyj domyślnej pozycji
        if not spawn_successful:
            print(f"Warning: Could not find safe spawn location for player {player_id}")
            spawn_x, spawn_y = 400, 300
        
        player = Player(spawn_x, spawn_y, player_id)
        self.game_state.players[player_id] = player
        self.clients[player_id] = client_socket
        self.player_inputs[player_id] = {'dx': 0, 'dy': 0, 'angle': 0, 'shoot': False, 'mouse_x': 0, 'mouse_y': 0}
        self.last_shot_times[player_id] = 0

        try:
            while self.running:
                message = NetworkProtocol.receive_message(client_socket)
                if message is None:
                    break
                if message['type'] == 'player_input':
                    if self.game_state.players[player_id].dead:
                        continue
                    data = message['data']
                    self.player_inputs[player_id] = data
                elif message['type'] == 'switch_weapon':
                    idx = message['data']['selected_weapon_index']
                    player = self.game_state.players.get(player_id)
                    if player and 0 <= idx < len(player.weapons):
                        player.selected_weapon_index = idx
                        NetworkProtocol.send_message(client_socket, {
                            'type': 'switch_weapon_ack',
                            'data': {'selected_weapon_index': idx}
                        })
                elif message['type'] == 'restart_game':
                    for p in self.game_state.players.values():
                        p.respawn()
                        # Reset input state for all players
                        for pid in self.player_inputs:
                            self.player_inputs[pid] = {'dx': 0, 'dy': 0, 'angle': 0, 'shoot': False, 'mouse_x': 0, 'mouse_y': 0}
                    self.game_over = False
                    self.wave = 1
                    self.wave_cooldown = 0
                    self.wave_in_progress = False
                    self.zombies_to_spawn = 0
                    self.game_state.scores = {}  # Reset scores on game restart
        except Exception as e:
            print(f"Error handling client {address}: {e}")
        finally:
            if player_id in self.game_state.players:
                del self.game_state.players[player_id]
            if player_id in self.clients:
                del self.clients[player_id]
            if player_id in self.player_inputs:
                del self.player_inputs[player_id]
            if player_id in self.last_shot_times:
                del self.last_shot_times[player_id]
            client_socket.close()

    def has_line_of_sight(self, x1, y1, x2, y2):
        # Sprawdź czy między dwoma punktami nie ma ściany
        # Użyj kilku punktów na linii dla lepszej dokładności
        steps = 10
        for i in range(steps + 1):
            t = i / steps
            check_x = x1 + (x2 - x1) * t
            check_y = y1 + (y2 - y1) * t
            
            for wall in self.game_state.walls:
                if wall.rect.collidepoint(check_x, check_y):
                    return False
        return True

    def is_safe_spawn_position(self, x, y, size):
        # Sprawdź czy pozycja jest bezpieczna (nie koliduje ze ścianami)
        # Dodaj margines bezpieczeństwa
        margin = 10
        entity_rect = pygame.Rect(x - size - margin, y - size - margin, (size + margin)*2, (size + margin)*2)
        for wall in self.game_state.walls:
            if wall.rect.colliderect(entity_rect):
                return False
        return True

    def find_safe_spawn_position(self, base_x, base_y, size, max_attempts=100):
        # Próbuj znaleźć bezpieczną pozycję wokół podanego punktu
        for _ in range(max_attempts):
            # Losowe odchylenie w promieniu 50-300 pikseli
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(50, 300)
            spawn_x = base_x + math.cos(angle) * distance
            spawn_y = base_y + math.sin(angle) * distance
            
            # Upewnij się, że pozycja jest w granicach mapy
            if 50 < spawn_x < 3950 and 50 < spawn_y < 2950:
                if self.is_safe_spawn_position(spawn_x, spawn_y, size):
                    return spawn_x, spawn_y
        
        # Jeśli nie znaleziono bezpiecznej pozycji, spróbuj znaleźć miejsce w większej odległości
        for _ in range(max_attempts):
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(300, 500)
            spawn_x = base_x + math.cos(angle) * distance
            spawn_y = base_y + math.sin(angle) * distance
            
            if 50 < spawn_x < 3950 and 50 < spawn_y < 2950:
                if self.is_safe_spawn_position(spawn_x, spawn_y, size):
                    return spawn_x, spawn_y
        
        # Jeśli nadal nie znaleziono, zwróć oryginalną pozycję
        return base_x, base_y

    def find_path_around_wall(self, enemy, target_x, target_y, wall):
        # Znajdź punkty narożne ściany z większym marginesem
        margin = enemy.size * 2
        corners = [
            (wall.rect.left - margin, wall.rect.top - margin),
            (wall.rect.right + margin, wall.rect.top - margin),
            (wall.rect.left - margin, wall.rect.bottom + margin),
            (wall.rect.right + margin, wall.rect.bottom + margin)
        ]
        
        # Znajdź narożnik, który prowadzi najbliżej do celu
        best_corner = None
        best_score = float('inf')
        
        for corner in corners:
            # Oblicz odległość do narożnika
            dist_to_corner = ((corner[0] - enemy.x) ** 2 + (corner[1] - enemy.y) ** 2) ** 0.5
            # Oblicz odległość od narożnika do celu
            dist_to_target = ((corner[0] - target_x) ** 2 + (corner[1] - target_y) ** 2) ** 0.5
            # Połączone odległości (ważymy bardziej odległość do celu)
            score = dist_to_corner + dist_to_target * 1.5
            
            if score < best_score:
                best_score = score
                best_corner = corner
        
        if best_corner:
            # Oblicz kąt do najlepszego narożnika
            angle_to_corner = math.atan2(best_corner[1] - enemy.y, best_corner[0] - enemy.x)
            
            # Dodaj bardzo małe losowe odchylenie
            angle_to_corner += random.uniform(-0.05, 0.05)
            
            # Sprawdź czy nowa pozycja jest bezpieczna
            new_x = enemy.x + math.cos(angle_to_corner) * enemy.speed * (1/60)
            new_y = enemy.y + math.sin(angle_to_corner) * enemy.speed * (1/60)
            new_rect = pygame.Rect(new_x - enemy.size, new_y - enemy.size, enemy.size*2, enemy.size*2)
            
            # Sprawdź kolizje ze wszystkimi ścianami
            collision = False
            for other_wall in self.game_state.walls:
                if other_wall.rect.colliderect(new_rect):
                    collision = True
                    break
            
            if not collision:
                return math.cos(angle_to_corner) * enemy.speed, math.sin(angle_to_corner) * enemy.speed
        
        # Jeśli nie znaleziono dobrej ścieżki, spróbuj znaleźć alternatywną drogę
        # Znajdź najbliższą ścianę do celu
        target_angle = math.atan2(target_y - enemy.y, target_x - enemy.x)
        # Spróbuj obejść ścianę w przeciwnym kierunku
        target_angle += math.pi/2 if random.random() > 0.5 else -math.pi/2
        
        return math.cos(target_angle) * enemy.speed, math.sin(target_angle) * enemy.speed

    def get_grid(self, cell_size=40):
        width, height = 4000, 3000
        grid_w = width // cell_size
        grid_h = height // cell_size
        grid = [[0 for _ in range(grid_h)] for _ in range(grid_w)]
        for wall in self.game_state.walls:
            x0 = wall.rect.left // cell_size
            x1 = (wall.rect.right-1) // cell_size
            y0 = wall.rect.top // cell_size
            y1 = (wall.rect.bottom-1) // cell_size
            for gx in range(x0, x1+1):
                for gy in range(y0, y1+1):
                    if 0 <= gx < grid_w and 0 <= gy < grid_h:
                        grid[gx][gy] = 1  # Blocked
        return grid, cell_size, grid_w, grid_h

    def astar(self, start, goal, grid, grid_w, grid_h):
        def heuristic(a, b):
            return abs(a[0]-b[0]) + abs(a[1]-b[1])
        open_set = []
        heapq.heappush(open_set, (0+heuristic(start, goal), 0, start, [start]))
        closed = set()
        while open_set:
            _, cost, current, path = heapq.heappop(open_set)
            if current == goal:
                return path
            if current in closed:
                continue
            closed.add(current)
            for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                nx, ny = current[0]+dx, current[1]+dy
                if 0 <= nx < grid_w and 0 <= ny < grid_h and grid[nx][ny]==0:
                    heapq.heappush(open_set, (cost+1+heuristic((nx,ny), goal), cost+1, (nx,ny), path+[(nx,ny)]))
        return None

    def get_astar_path(self, x0, y0, x1, y1):
        grid, cell_size, grid_w, grid_h = self.get_grid()
        start = (int(x0)//cell_size, int(y0)//cell_size)
        goal = (int(x1)//cell_size, int(y1)//cell_size)
        path = self.astar(start, goal, grid, grid_w, grid_h)
        if path and len(path) > 1:
            # Return next cell center
            next_cell = path[1]
            return next_cell[0]*cell_size+cell_size//2, next_cell[1]*cell_size+cell_size//2
        return x1, y1

    def update_game_state(self):
        while self.running:
            # --- Fale zombie ---
            if not self.wave_in_progress and self.wave_cooldown <= 0:
                self.wave_in_progress = True
                self.zombies_to_spawn = 5 + self.wave
                self.spawned_this_wave = 0
            if self.wave_in_progress and self.zombies_to_spawn > 0:
                if len(self.game_state.enemies) < 10:
                    # Wybierz losowy punkt spawnu
                    if self.wave % 5 == 0:  # Co 5 fal spawnuj bossa
                        spawn_point = random.choice(self.boss_spawn_points)
                        enemy_type = 5  # Boss
                        is_boss_room_boss = True
                    else:
                        spawn_point = random.choice(self.enemy_spawn_points)
                        enemy_type = random.randint(1, 4)
                        is_boss_room_boss = False
                    
                    base_x, base_y = spawn_point
                    
                    # Stwórz tymczasowego przeciwnika aby sprawdzić jego rozmiar
                    temp_enemy = Enemy(base_x, base_y, enemy_type)
                    
                    # Znajdź bezpieczną pozycję spawnu
                    spawn_x, spawn_y = self.find_safe_spawn_position(base_x, base_y, temp_enemy.size)
                    
                    if self.wave % 5 == 0:
                        self.game_state.enemies = []  # Usuń wszystkich innych przeciwników
                        boss = Enemy(spawn_x, spawn_y, enemy_type)
                        boss.is_boss_room_boss = is_boss_room_boss
                        self.game_state.enemies.append(boss)
                        self.zombies_to_spawn = 0
                    else:
                        self.game_state.enemies.append(Enemy(spawn_x, spawn_y, enemy_type))
                        self.zombies_to_spawn -= 1

            if self.wave_in_progress and self.zombies_to_spawn == 0 and len(self.game_state.enemies) == 0:
                self.wave_in_progress = False
                self.wave_cooldown = 5
                self.wave += 1
            if not self.wave_in_progress and self.wave_cooldown > 0:
                self.wave_cooldown -= 1/60
                if self.wave_cooldown < 0:
                    self.wave_cooldown = 0
            self.game_state.wave = self.wave
            self.game_state.wave_cooldown = self.wave_cooldown

            all_dead = True
            for player in self.game_state.players.values():
                if player.dead:
                    if player.respawn_timer > 0:
                        player.respawn_timer -= 1/60
                        if player.respawn_timer <= 0:
                            player.respawn()
                    continue
                all_dead = False
            if all_dead and len(self.game_state.players) > 0:
                self.game_over = True
            else:
                self.game_over = False
            self.game_state.game_over = self.game_over

            # Update player positions based on input
            for pid, player in self.game_state.players.items():
                if player.dead:
                    continue
                input_data = self.player_inputs.get(pid, {'dx': 0, 'dy': 0, 'angle': 0, 'shoot': False, 'mouse_x': player.x, 'mouse_y': player.y})
                dx = input_data['dx']
                dy = input_data['dy']
                angle = input_data['angle']
                shoot = input_data['shoot']
                mouse_x = input_data.get('mouse_x', player.x)
                mouse_y = input_data.get('mouse_y', player.y)

                # Normalize diagonal movement
                if dx != 0 and dy != 0:
                    dx *= 0.7071
                    dy *= 0.7071

                # Ruch gracza z kolizją ścian
                new_x = player.x + dx * player.speed * 2.0  # Stała, wyższa prędkość
                new_y = player.y + dy * player.speed * 2.0  # Stała, wyższa prędkość
                player_rect = pygame.Rect(new_x - player.size, new_y - player.size, player.size*2, player.size*2)
                collision = False
                for wall in self.game_state.walls:
                    if wall.rect.colliderect(player_rect):
                        collision = True
                        break
                if not collision:
                    player.x = new_x
                    player.y = new_y
                player.angle = angle

                # Special weapon logic
                weapon = getattr(player, 'current_weapon', None)
                now = time.time() * 1000
                if shoot and weapon:
                    if weapon.special_type == 'wall':
                        if now - self.last_shot_times.get(pid, 0) > weapon.fire_rate and player.ammo.get(weapon.name, 0) > 0:
                            self.last_shot_times[pid] = now
                            wall_w, wall_h = 40, 40
                            self.game_state.walls.append(Wall(mouse_x - wall_w//2, mouse_y - wall_h//2, wall_w, wall_h, is_player_wall=True))
                            player.ammo[weapon.name] -= 1 # Consume ammo for wall spawner

                    elif weapon.special_type == 'mine':
                        if now - self.last_shot_times.get(pid, 0) > weapon.fire_rate and player.ammo.get(weapon.name, 0) > 0:
                            self.last_shot_times[pid] = now
                            # Sprawdź czy miejsce na minę nie koliduje ze ścianą
                            mine_size = 12  # Rozmiar miny
                            mine_rect = pygame.Rect(mouse_x - mine_size, mouse_y - mine_size, mine_size*2, mine_size*2)
                            can_place = True
                            for wall in self.game_state.walls:
                                if wall.rect.colliderect(mine_rect):
                                    can_place = False
                                    break
                            
                            if can_place:
                                self.game_state.mines.append(Mine(mouse_x, mouse_y, pid, weapon.damage))
                                player.ammo[weapon.name] -= 1 # Consume ammo for mine placer

                    elif weapon.name == "Shotgun": # Handle Shotgun
                         if now - self.last_shot_times.get(pid, 0) > weapon.fire_rate and player.ammo.get(weapon.name, 0) > 0:
                             self.last_shot_times[pid] = now
                             player.ammo[weapon.name] -= 1 # Consume ammo
                             # Create multiple bullets with spread
                             spread_angle = 15 # Degrees total spread
                             num_bullets = 3
                             for i in range(num_bullets):
                                 angle_offset = (i - (num_bullets - 1) / 2) * (spread_angle / num_bullets)
                                 bullet_angle = player.angle + angle_offset
                                 # Use a different color for shotgun bullets to distinguish them
                                 shotgun_bullet = Bullet(player.x, player.y, bullet_angle, player.player_id, weapon)
                                 shotgun_bullet.color = (255, 165, 0) # Orange color for shotgun bullets
                                 self.game_state.bullets.append(shotgun_bullet)

                    else: # Handle regular bullets (Pistol, Weapon 2, Weapon 3)
                        if now - self.last_shot_times.get(pid, 0) > weapon.fire_rate and player.ammo.get(weapon.name, 0) > 0: # Check ammo for regular guns too
                            self.last_shot_times[pid] = now
                            player.ammo[weapon.name] -= 1 # Consume ammo
                            bullet = Bullet(player.x, player.y, player.angle, player.player_id, weapon)
                            self.game_state.bullets.append(bullet)

            # Update bullets
            for bullet in self.game_state.bullets[:]:
                bullet.update()
                if bullet.lifetime <= 0:
                    self.game_state.bullets.remove(bullet)
                    continue

                # Check bullet collisions with walls
                for wall in self.game_state.walls[:]:
                    if wall.rect.collidepoint(bullet.x, bullet.y):
                        if not wall.is_indestructible:
                            wall.health -= bullet.damage
                            if wall.health <= 0:
                                self.game_state.walls.remove(wall)
                        if bullet in self.game_state.bullets:
                            self.game_state.bullets.remove(bullet)
                        break

                # Check bullet collisions with enemies
                for enemy in self.game_state.enemies[:]:
                    if bullet.player_id >= 0 and ((bullet.x - enemy.x) ** 2 + (bullet.y - enemy.y) ** 2) ** 0.5 < enemy.size:
                        # Damage the enemy
                        enemy.health -= bullet.damage if hasattr(bullet, 'damage') else 25
                        if enemy.health <= 0:
                            # Award points based on enemy type
                            points = {
                                1: 100,  # Basic zombie
                                2: 200,  # Stronger zombie
                                3: 500,  # Boss zombie
                                4: 300,  # Shooter zombie
                                5: 2000  # Boss zombie (więcej punktów)
                            }.get(enemy.type, 100)
                            
                            # Initialize score for player if not exists
                            if bullet.player_id not in self.game_state.scores:
                                self.game_state.scores[bullet.player_id] = 0
                            
                            # Add points to player's score
                            self.game_state.scores[bullet.player_id] += points
                            
                            # Chance to drop health, armor or weapon
                            drop_roll = random.random()
                            if drop_roll < 0.2:  # 20% chance for health
                                self.game_state.pickups.append(Pickup(enemy.x, enemy.y, 'health', 50))
                            elif drop_roll < 0.3:  # 10% chance for armor
                                self.game_state.pickups.append(Pickup(enemy.x, enemy.y, 'armor', 100))
                            else:  # 70% chance for weapon
                                # Boss z pokoju bossa zawsze upuszcza bazookę
                                if enemy.type == 5 and getattr(enemy, 'is_boss_room_boss', False):
                                    bazooka = get_weapon_by_name("Bazooka")
                                    self.game_state.lootboxes.append(LootBox(enemy.x, enemy.y, bazooka))
                                else:
                                    self.game_state.lootboxes.append(LootBox(enemy.x, enemy.y))
                            
                            self.game_state.enemies.remove(enemy)
                        
                        # Handle explosive bullets
                        if bullet.is_explosive:
                            # Apply explosion damage to all enemies within radius
                            for other_enemy in self.game_state.enemies[:]:
                                if other_enemy != enemy:  # Skip the directly hit enemy
                                    distance = ((bullet.x - other_enemy.x) ** 2 + (bullet.y - other_enemy.y) ** 2) ** 0.5
                                    if distance < bullet.explosion_radius:
                                        # Damage decreases with distance
                                        damage_multiplier = 1 - (distance / bullet.explosion_radius)
                                        explosion_damage = int(bullet.damage * damage_multiplier)
                                        other_enemy.health -= explosion_damage
                                        if other_enemy.health <= 0:
                                            self.game_state.enemies.remove(other_enemy)
                        
                        # Remove the bullet
                        if bullet in self.game_state.bullets:
                            self.game_state.bullets.remove(bullet)
                            break

                # Check bullet collisions with players
                for player in self.game_state.players.values():
                    # Pociski wrogów (player_id == -1) kolidują z graczami
                    # Pociski graczy (player_id >= 0) nie kolidują z własnymi graczami (sprawdzane przez player.player_id != bullet.player_id)
                    if bullet.player_id == -1 or (bullet.player_id >= 0 and player.player_id != bullet.player_id):
                        if not player.dead:
                            if ((bullet.x - player.x) ** 2 + (bullet.y - player.y) ** 2) ** 0.5 < player.size:
                                # Gracz otrzymał obrażenia od pocisku wroga lub innego gracza
                                player.take_damage(bullet.damage)
                                if player.health <= 0 and not player.dead:
                                    player.kill()
                                if bullet in self.game_state.bullets:
                                    self.game_state.bullets.remove(bullet)
                                break # Pocisk trafił w gracza, usuń pocisk

            # Player picks up items
            for player in self.game_state.players.values():
                if player.dead:
                    continue
                
                # Check for pickup collisions
                for pickup in self.game_state.pickups[:]:
                    if ((player.x - pickup.x) ** 2 + (player.y - pickup.y) ** 2) ** 0.5 < player.size + pickup.size:
                        if pickup.pickup_type == 'health':
                            player.add_health(pickup.value)
                        else:  # armor
                            player.add_armor(pickup.value)
                        self.game_state.pickups.remove(pickup)

                # Check for lootbox collisions
                for lootbox in self.game_state.lootboxes[:]:
                    if ((player.x - lootbox.x) ** 2 + (player.y - lootbox.y) ** 2) ** 0.5 < player.size + lootbox.size:
                        player.add_weapon(lootbox.weapon)
                        self.game_state.lootboxes.remove(lootbox)

            # Update mines and check for explosions
            for mine in self.game_state.mines[:]:
                # Check for player or enemy contact to activate mine
                if not mine.active:
                    # Check player contact
                    for player in self.game_state.players.values():
                        if not player.dead and ((mine.x - player.x) ** 2 + (mine.y - player.y) ** 2) ** 0.5 < player.size + mine.size:
                            mine.active = True
                            mine.activation_timer = mine.activation_delay
                            break
                    
                    # Check enemy contact
                    if not mine.active:
                        for enemy in self.game_state.enemies:
                            if ((mine.x - enemy.x) ** 2 + (mine.y - enemy.y) ** 2) ** 0.5 < enemy.size + mine.size:
                                mine.active = True
                                mine.activation_timer = mine.activation_delay
                                break
                
                # Update activation timer if mine is active
                if mine.active:
                    mine.activation_timer -= 1/60
                    if mine.activation_timer <= 0:
                        # Mine explodes
                        # Apply damage to players
                        for player in self.game_state.players.values():
                            if not player.dead:
                                distance = ((mine.x - player.x) ** 2 + (mine.y - player.y) ** 2) ** 0.5
                                if distance < mine.explosion_radius:
                                    # Damage decreases with distance
                                    damage_multiplier = 1 - (distance / mine.explosion_radius)
                                    damage = int(mine.damage * damage_multiplier)
                                    player.take_damage(damage)
                        
                        # Apply damage to enemies
                        for enemy in self.game_state.enemies[:]:
                            distance = ((mine.x - enemy.x) ** 2 + (mine.y - enemy.y) ** 2) ** 0.5
                            if distance < mine.explosion_radius:
                                # Damage decreases with distance
                                damage_multiplier = 1 - (distance / mine.explosion_radius)
                                damage = int(mine.damage * damage_multiplier)
                                enemy.health -= damage
                                if enemy.health <= 0:
                                    # Award points for mine kills
                                    points = {
                                        1: 150,  # Extra points for mine kills
                                        2: 300,
                                        3: 750,
                                        4: 450
                                    }.get(enemy.type, 150)
                                    
                                    # Initialize score for player if not exists
                                    if mine.owner_id not in self.game_state.scores:
                                        self.game_state.scores[mine.owner_id] = 0
                                    
                                    # Add points to player's score
                                    self.game_state.scores[mine.owner_id] += points
                                    
                                    self.game_state.lootboxes.append(LootBox(enemy.x, enemy.y))
                                    self.game_state.enemies.remove(enemy)
                        
                        # Remove the exploded mine
                        self.game_state.mines.remove(mine)
                        break  # Break since we modified the list we're iterating over

            # Update enemy movement and actions
            dt = 1/60
            now = time.time() * 1000
            for enemy in self.game_state.enemies[:]:
                # Sprawdź czy przeciwnik nie utknął w ścianie
                enemy_rect = pygame.Rect(enemy.x - enemy.size, enemy.y - enemy.size, enemy.size*2, enemy.size*2)
                stuck = False
                for wall in self.game_state.walls:
                    if wall.rect.colliderect(enemy_rect):
                        stuck = True
                        # Zamiast teleportować, spróbuj delikatnie przesunąć przeciwnika
                        angle = math.atan2(enemy.y - wall.rect.centery, enemy.x - wall.rect.centerx)
                        enemy.x += math.cos(angle) * 5
                        enemy.y += math.sin(angle) * 5
                        break
                
                if stuck:
                    continue  # Pomiń resztę logiki dla tej klatki

                alive_players = [p for p in self.game_state.players.values() if not p.dead]
                target_player = None
                
                if alive_players:
                    target_player = min(alive_players, key=lambda p: ((p.x - enemy.x) ** 2 + (p.y - enemy.y) ** 2) ** 0.5)
                    distance_to_player = ((enemy.x - target_player.x) ** 2 + (enemy.y - target_player.y) ** 2) ** 0.5
                    has_los = self.has_line_of_sight(enemy.x, enemy.y, target_player.x, target_player.y)
                    if enemy._is_shooter and distance_to_player < 300 and has_los:
                        target_dx, target_dy = 0, 0
                        target_angle_deg = math.degrees(math.atan2(target_player.y - enemy.y, target_player.x - enemy.x))
                        
                        if now - enemy._last_shot > enemy._fire_rate:
                            enemy._last_shot = now
                            enemy_bullet = Bullet(enemy.x, enemy.y, target_angle_deg, -1)
                            enemy_bullet.damage = enemy._bullet_damage
                            enemy_bullet.speed = enemy._bullet_speed
                            enemy_bullet.color = (255, 0, 0)
                            enemy_bullet.start_x = enemy.x
                            enemy_bullet.start_y = enemy.y
                            self.game_state.bullets.append(enemy_bullet)
                    
                    elif getattr(enemy, '_is_miner', False) and distance_to_player < 200 and has_los:
                        target_dx, target_dy = 0, 0
                        target_angle_deg = math.degrees(math.atan2(target_player.y - enemy.y, target_player.x - enemy.x))
                        
                        if now - enemy._last_shot > enemy._fire_rate:
                            enemy._last_shot = now
                            self.game_state.mines.append(Mine(enemy.x, enemy.y, -1, enemy._mine_damage))
                    
                    else:
                        # Jeśli nie ma LOS, użyj A*
                        if not has_los:
                            next_x, next_y = self.get_astar_path(enemy.x, enemy.y, target_player.x, target_player.y)
                            angle = math.atan2(next_y - enemy.y, next_x - enemy.x)
                        else:
                            angle = math.atan2(target_player.y - enemy.y, target_player.x - enemy.x)
                        target_dx = math.cos(angle) * enemy.speed
                        target_dy = math.sin(angle) * enemy.speed
                        target_angle_deg = math.degrees(angle)
                        future_x = enemy.x + target_dx * dt
                        future_y = enemy.y + target_dy * dt
                        enemy_rect = pygame.Rect(future_x - enemy.size, future_y - enemy.size, enemy.size*2, enemy.size*2)
                        for wall in self.game_state.walls:
                            if wall.rect.colliderect(enemy_rect):
                                target_dx, target_dy = self.find_path_around_wall(enemy, target_player.x, target_player.y, wall)
                                target_angle_deg = math.degrees(math.atan2(target_dy, target_dx))
                                break
                else:
                    # Patrolowanie gdy nie ma graczy
                    dx, dy = enemy.get_patrol_vector(dt)
                    target_dx = dx * enemy.speed
                    target_dy = dy * enemy.speed
                    target_angle_deg = math.degrees(math.atan2(dy, dx))

                enemy.look_angle = target_angle_deg

                # Zastosuj ruch z płynnym przejściem
                enemy.x += target_dx * dt
                enemy.y += target_dy * dt

                # Sprawdź kolizje z graczem
                if target_player and ((enemy.x - target_player.x) ** 2 + (enemy.y - target_player.y) ** 2) ** 0.5 < enemy.size + target_player.size:
                    target_player.take_damage(enemy.damage)
                    if target_player.health <= 0 and not target_player.dead:
                        target_player.kill()

            # Usuń zniszczone ściany po przetworzeniu wszystkich wrogów
            self.game_state.walls = [wall for wall in self.game_state.walls if wall.health > 0]

            time.sleep(1/60)  # 60 FPS

    def broadcast_game_state(self):
        while self.running:
            for client in self.clients.values():
                try:
                    NetworkProtocol.send_message(client, {
                        'type': 'game_state',
                        'data': self.game_state.to_dict()
                    })
                except:
                    pass
            time.sleep(1/30)  # 30 FPS for network updates

    def run(self):
        # Start game state update thread
        update_thread = threading.Thread(target=self.update_game_state)
        update_thread.start()

        # Start broadcast thread
        broadcast_thread = threading.Thread(target=self.broadcast_game_state)
        broadcast_thread.start()

        try:
            while self.running:
                client_socket, address = self.server.accept()
                print(f"New connection from {address}")
                client_thread = threading.Thread(target=self.handle_client,
                                              args=(client_socket, address))
                client_thread.start()
        except KeyboardInterrupt:
            self.running = False
            self.server.close()

    def is_in_boss_room(self, x, y):
        # Sprawdź czy pozycja jest w jednym z pokoi bossa
        boss_rooms = [
            pygame.Rect(400, 400, 300, 300),  # North-west boss room
            pygame.Rect(3300, 400, 300, 300),  # North-east boss room
            pygame.Rect(400, 2300, 300, 300),  # South-west boss room
        ]
        
        for room in boss_rooms:
            if room.collidepoint(x, y):
                return True
        return False

if __name__ == "__main__":
    server = GameServer()
    server.run() 