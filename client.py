import sys
import socket
import pygame
import math
from common.game_objects import Player, Enemy, Bullet, Wall, LootBox, Mine
from common.network import NetworkProtocol, GameState

SCREEN_WIDTH = 800 
SCREEN_HEIGHT = 600

class GameClient:
    def __init__(self, server_ip, port=5555):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Boxhead Multiplayer")
        self.clock = pygame.time.Clock()
        self.running = True
        
        # Connect to server
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((server_ip, port))
        
        # Game state
        self.game_state = GameState()
        self.player_id = None
        self.keys = {
            'w': False,
            'a': False,
            's': False,
            'd': False
        }
        self.auto_shoot = False
        self.mouse_aim_enabled = True
        self.keyboard_target_pos = [SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2]
        self._keyboard_target_speed = 10

    def handle_input(self):
        for event in pygame.event.get():
            if getattr(self.game_state, 'game_over', False):
                if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    NetworkProtocol.send_message(self.socket, {'type': 'restart_game', 'data': {}})
                    return
            if self.player_id is not None and self.player_id in self.game_state.players:
                player = self.game_state.players[self.player_id]
                if getattr(player, 'dead', False):
                    return  # nie przetwarzaj inputu martwego gracza
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in [pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d]:
                    self.keys[event.unicode] = True
                # Toggle auto-shoot
                if event.key == pygame.K_z:
                    self.auto_shoot = not self.auto_shoot
                # Toggle mouse/keyboard aim
                if event.key == pygame.K_c:
                    self.mouse_aim_enabled = not self.mouse_aim_enabled
                # Weapon switching
                if self.player_id is not None and self.player_id in self.game_state.players:
                    player = self.game_state.players[self.player_id]
                    if pygame.K_1 <= event.key <= pygame.K_9:
                        idx = event.key - pygame.K_1
                        if idx < len(player.weapons):
                            NetworkProtocol.send_message(self.socket, {
                                'type': 'switch_weapon',
                                'data': {'selected_weapon_index': idx}
                            })
            elif event.type == pygame.KEYUP:
                if event.key in [pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d]:
                    self.keys[event.unicode] = False

        # Calculate movement from both WASD and arrow keys
        dx = dy = 0
        keys = pygame.key.get_pressed()
        
        # WASD movement
        if self.keys['w'] or keys[pygame.K_UP]: dy -= 1
        if self.keys['s'] or keys[pygame.K_DOWN]: dy += 1
        if self.keys['a'] or keys[pygame.K_LEFT]: dx -= 1
        if self.keys['d'] or keys[pygame.K_RIGHT]: dx += 1

        # Normalize diagonal movement
        if dx != 0 and dy != 0:
            dx *= 0.7071
            dy *= 0.7071

        # Calculate keyboard aim movement
        kbd_target_dx = kbd_target_dy = 0
        if not self.mouse_aim_enabled:
            keys_pressed = pygame.key.get_pressed()
            if keys_pressed[pygame.K_LEFT]: 
                kbd_target_dx -= 1
            if keys_pressed[pygame.K_RIGHT]: 
                kbd_target_dx += 1
            if keys_pressed[pygame.K_UP]: 
                kbd_target_dy -= 1
            if keys_pressed[pygame.K_DOWN]: 
                kbd_target_dy += 1

            # Update keyboard target position (screen coordinates)
            self.keyboard_target_pos[0] += kbd_target_dx * self._keyboard_target_speed
            self.keyboard_target_pos[1] += kbd_target_dy * self._keyboard_target_speed

            # Clamp keyboard target position to screen bounds
            self.keyboard_target_pos[0] = max(0, min(SCREEN_WIDTH, self.keyboard_target_pos[0]))
            self.keyboard_target_pos[1] = max(0, min(SCREEN_HEIGHT, self.keyboard_target_pos[1]))

        # Get mouse position for aiming (convert to world coordinates)
        mouse_x, mouse_y = pygame.mouse.get_pos()
        angle = 0
        shooting = False
        world_mouse_x, world_mouse_y = mouse_x, mouse_y

        if self.player_id is not None and self.player_id in self.game_state.players:
            player = self.game_state.players[self.player_id]
            camera_offset = self.get_camera_offset(player)

            if self.auto_shoot:
                # Auto-aim and shoot at the nearest enemy
                alive_enemies = [e for e in self.game_state.enemies if e.health > 0]
                if alive_enemies:
                    nearest_enemy = min(alive_enemies, key=lambda e: ((e.x - player.x) ** 2 + (e.y - player.y) ** 2) ** 0.5)
                    angle = math.degrees(math.atan2(nearest_enemy.y - player.y, nearest_enemy.x - player.x))
                    shooting = True
                    world_mouse_x, world_mouse_y = nearest_enemy.x, nearest_enemy.y
                else:
                    shooting = False
                    angle = player.angle

            elif not self.mouse_aim_enabled:
                world_mouse_x = self.keyboard_target_pos[0] + camera_offset[0]
                world_mouse_y = self.keyboard_target_pos[1] + camera_offset[1]
                angle = math.degrees(math.atan2(world_mouse_y - player.y, world_mouse_x - player.x))
                keys_pressed = pygame.key.get_pressed()
                shooting = keys_pressed[pygame.K_SPACE] or keys_pressed[pygame.K_LSHIFT]

            else:
                world_mouse_x = mouse_x + camera_offset[0]
                world_mouse_y = mouse_y + camera_offset[1]
                angle = math.degrees(math.atan2(world_mouse_y - player.y, world_mouse_x - player.x))
                shooting = pygame.mouse.get_pressed()[0] or pygame.key.get_pressed()[pygame.K_SPACE]

        NetworkProtocol.send_message(self.socket, {
            'type': 'player_input',
            'data': {
                'dx': dx,
                'dy': dy,
                'angle': angle,
                'shoot': shooting,
                'mouse_x': world_mouse_x,
                'mouse_y': world_mouse_y
            }
        })

    def update(self):
        message = NetworkProtocol.receive_message(self.socket)
        if message:
            if message['type'] == 'game_state':
                self.game_state = GameState.from_dict(message['data'])
                if self.player_id is None and self.game_state.players:
                    self.player_id = max(self.game_state.players.keys())
            elif message['type'] == 'switch_weapon_ack':
                pass

    def get_camera_offset(self, player):
        cx = player.x - SCREEN_WIDTH // 2
        cy = player.y - SCREEN_HEIGHT // 2
        return (cx, cy)

    def draw_minimap(self, screen, players, enemies, walls, world_view_size=2000):
        minimap_size = 220  # było 200, zwiększone o 10%
        margin = 10
        minimap_surface = pygame.Surface((minimap_size, minimap_size), pygame.SRCALPHA)
        minimap_surface.fill((30, 30, 30, 255))  # solid dark background

        # Center on the local player
        if self.player_id is not None and self.player_id in self.game_state.players:
            player = self.game_state.players[self.player_id]
            center_x, center_y = player.x, player.y
        else:
            center_x, center_y = world_view_size // 2, world_view_size // 2

        # Scaling factor: how many world units per minimap pixel
        scale = minimap_size / world_view_size

        # Helper to convert world coordinates to minimap coordinates (centered)
        def to_minimap_coords(x, y):
            mx = int((x - center_x) * scale + minimap_size // 2)
            my = int((y - center_y) * scale + minimap_size // 2)
            return mx, my

        # Draw walls (gray)
        for wall in walls:
            wx, wy = to_minimap_coords(wall.rect.x, wall.rect.y)
            ww = max(2, int(wall.rect.width * scale))
            wh = max(2, int(wall.rect.height * scale))
            pygame.draw.rect(minimap_surface, (128, 128, 128), (wx, wy, ww, wh))

        # Draw enemies (red)
        for enemy in enemies:
            ex, ey = to_minimap_coords(enemy.x, enemy.y)
            pygame.draw.circle(minimap_surface, (255, 0, 0), (ex, ey), 4)

        # Draw players (blue)
        for p in players:
            px, py = to_minimap_coords(p.x, p.y)
            pygame.draw.circle(minimap_surface, (0, 0, 255), (px, py), 5)

        # Draw the local player in white (on top)
        if self.player_id is not None and self.player_id in self.game_state.players:
            pygame.draw.circle(minimap_surface, (255, 255, 255), (minimap_size // 2, minimap_size // 2), 6, 2)

        # Draw white border
        pygame.draw.rect(minimap_surface, (255,255,255), (0,0,minimap_size,minimap_size), 2)

        # Blit minimap to lower-left corner
        screen_height = screen.get_height()
        screen.blit(minimap_surface, (10, screen_height - minimap_size - 10))

    def draw(self):
        self.screen.fill((0, 0, 0))  # Black background

        # Camera offset
        camera_offset = (0, 0)
        if self.player_id is not None and self.player_id in self.game_state.players:
            player = self.game_state.players[self.player_id]
            camera_offset = self.get_camera_offset(player)

        # Draw pickups
        if hasattr(self.game_state, 'pickups'):
            for pickup in self.game_state.pickups:
                pickup.draw(self.screen, camera_offset)

        # Draw walls
        if hasattr(self.game_state, 'walls'):
            for wall in self.game_state.walls:
                wall.draw(self.screen, camera_offset)

        # Draw lootboxes
        if hasattr(self.game_state, 'lootboxes'):
            for lootbox in self.game_state.lootboxes:
                lootbox.draw(self.screen, camera_offset)

        # Draw mines
        if hasattr(self.game_state, 'mines'):
            for mine in self.game_state.mines:
                mine.draw(self.screen, camera_offset)

        # Draw enemies
        for enemy in self.game_state.enemies:
            enemy.draw(self.screen, camera_offset)

        # Draw bullets
        for bullet in self.game_state.bullets:
            bullet.draw(self.screen, camera_offset)

        # Draw players
        for player in self.game_state.players.values():
            if not getattr(player, 'dead', False):
                player.draw(self.screen, camera_offset)

        # Draw HUD
        font = pygame.font.SysFont(None, 24)
        
        # Draw scores
        if hasattr(self.game_state, 'scores'):
            score_y = 10
            score_x = SCREEN_WIDTH - 200
            font_score = pygame.font.SysFont(None, 28)
            
            # Draw score header
            header = font_score.render("SCORES:", True, (255, 255, 0))
            self.screen.blit(header, (score_x, score_y))
            score_y += 30
            
            # Sort players by score
            sorted_scores = sorted(self.game_state.scores.items(), key=lambda x: x[1], reverse=True)
            
            # Display each player's score
            for player_id, score in sorted_scores:
                color = (0, 255, 0) if player_id == self.player_id else (255, 255, 255)
                score_text = font_score.render(f"Player {player_id + 1}: {score}", True, color)
                self.screen.blit(score_text, (score_x, score_y))
                score_y += 25

        # Draw wave info
        if hasattr(self.game_state, 'wave'):
            wave_y = score_y + 20 if 'score_y' in locals() else 10
            text = font.render(f"Wave: {self.game_state.wave}", True, (255,255,255))
            self.screen.blit(text, (SCREEN_WIDTH-180, wave_y))
            
        if hasattr(self.game_state, 'wave_cooldown') and self.game_state.wave_cooldown > 0:
            wave_cooldown_y = wave_y + 40 if 'wave_y' in locals() else 50
            text = font.render(f"Break: {int(self.game_state.wave_cooldown)+1}s", True, (255,255,0))
            self.screen.blit(text, (SCREEN_WIDTH-180, wave_cooldown_y))

        # Draw HUD
        if self.player_id is not None and self.player_id in self.game_state.players:
            player = self.game_state.players[self.player_id]
            
            # Draw health bar
            health_width = 100
            health_height = 10
            health_x = 10
            health_y = 10
            pygame.draw.rect(self.screen, (255, 0, 0), (health_x, health_y, health_width, health_height))
            current_health_width = (player.health / 500) * health_width
            pygame.draw.rect(self.screen, (0, 255, 0), (health_x, health_y, current_health_width, health_height))
            
            # Draw armor bar
            armor_y = health_y + health_height + 5
            pygame.draw.rect(self.screen, (100, 100, 100), (health_x, armor_y, health_width, health_height))
            current_armor_width = (player.armor / player.max_armor) * health_width
            pygame.draw.rect(self.screen, (0, 128, 255), (health_x, armor_y, current_armor_width, health_height))
            
            # Draw health and armor text
            health_text = font.render(f"HP: {int(player.health)}", True, (255,255,255))
            armor_text = font.render(f"Armor: {int(player.armor)}", True, (255,255,255))
            self.screen.blit(health_text, (health_x + health_width + 10, health_y))
            self.screen.blit(armor_text, (health_x + health_width + 10, armor_y))

            # Draw weapon inventory
            icon_size = 40
            icon_spacing = 10
            text_offset_y = icon_size + 5
            start_x = 10
            start_y = 90

            # Draw weapon slots
            for i, weapon in enumerate(player.weapons):
                x = start_x + i * (icon_size + icon_spacing)
                y = start_y
                
                # Draw weapon slot background
                rect = pygame.Rect(x, y, icon_size, icon_size)
                if i == player.selected_weapon_index:
                    pygame.draw.rect(self.screen, (255,255,0), rect, 3)  # Yellow border for selected
                else:
                    pygame.draw.rect(self.screen, (100,100,100), rect, 1)  # Gray border for others
                
                # Draw weapon icon
                pygame.draw.rect(self.screen, weapon.icon_color, rect.inflate(-10, -10))
                
                # Draw weapon number
                font_small = pygame.font.SysFont(None, 20)
                number_text = font_small.render(str(i+1), True, (255,255,255))
                number_rect = number_text.get_rect(center=(x + icon_size // 2, y + icon_size // 2))
                self.screen.blit(number_text, number_rect)
                
                # Draw weapon name and ammo
                font_medium = pygame.font.SysFont(None, 18)
                name_text = font_medium.render(weapon.name, True, (255,255,255))
                ammo_text = font_medium.render(f"Ammo: {player.ammo.get(weapon.name, 0)}", True, (255,255,255))
                self.screen.blit(name_text, (x, y + text_offset_y))
                self.screen.blit(ammo_text, (x, y + text_offset_y + 15))

            # Draw current weapon ammo in larger font
            current_weapon = player.weapons[player.selected_weapon_index]
            ammo_text = font.render(f"Ammo: {player.ammo.get(current_weapon.name, 0)}", True, (255,255,255))
            self.screen.blit(ammo_text, (10, 60))

        # Death message
        if getattr(player, 'dead', False):
            font_big = pygame.font.SysFont(None, 48)
            text = font_big.render(f"UMARŁEŚ! Respawn za {int(max(0, player.respawn_timer))}s", True, (255,0,0))
            self.screen.blit(text, (SCREEN_WIDTH//2-200, SCREEN_HEIGHT//2-50))

        # Game over message
        if getattr(self.game_state, 'game_over', False):
            font_big = pygame.font.SysFont(None, 64)
            text = font_big.render("KONIEC GRY! Wciśnij R by zrestartować", True, (255,255,0))
            self.screen.blit(text, (SCREEN_WIDTH//2-300, SCREEN_HEIGHT//2))

        # Draw minimap (after everything else)
        players = [p for p in self.game_state.players.values() if not getattr(p, 'dead', False)]
        enemies = self.game_state.enemies if hasattr(self.game_state, 'enemies') else []
        walls = self.game_state.walls if hasattr(self.game_state, 'walls') else []
        self.draw_minimap(self.screen, players, enemies, walls, world_view_size=2000)

        pygame.display.flip()

    def run(self):
        while self.running:
            self.handle_input()
            self.update()
            self.draw()
            self.clock.tick(60)

        self.socket.close()
        pygame.quit()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python client.py <server_ip>")
        sys.exit(1)
    
    client = GameClient(sys.argv[1])
    client.run() 