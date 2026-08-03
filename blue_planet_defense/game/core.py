#!/usr/bin/env python3
# Game core module for Blue Planet Defense

import pygame
import random
from .entities import Tower, Enemy, Projectile
from .levels import Level

class Game:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        
        # Game state
        self.score = 0
        self.lives = 10
        self.money = 100
        self.wave = 1
        self.game_over = False
        
        # Game objects
        self.towers = []
        self.enemies = []
        self.projectiles = []
        
        # Level setup
        self.level = Level(width, height)
        self.path = self.level.path
        
        # Wave management
        self.enemies_spawned = 0
        self.enemies_to_spawn = 10
        self.spawn_delay = 1.0
        self.last_spawn_time = 0
        
        # Tower types
        self.tower_types = {
            "basic": {"cost": 50, "damage": 20, "range": 150, "fire_rate": 1.0},
            "ice": {"cost": 100, "damage": 10, "range": 120, "fire_rate": 0.8, "slow": 0.5},
            "cannon": {"cost": 150, "damage": 50, "range": 200, "fire_rate": 2.0, "area": 50}
        }
    
    def update(self):
        # Update projectiles
        for projectile in self.projectiles[:]:
            projectile.update()
            if projectile.out_of_bounds or projectile.target is None or not projectile.target.alive:
                self.projectiles.remove(projectile)
        
        # Update enemies
        for enemy in self.enemies[:]:
            enemy.update()
            if enemy.reached_end:
                self.lives -= 1
                self.enemies.remove(enemy)
            elif not enemy.alive:
                self.score += 10
                self.money += 5
                self.enemies.remove(enemy)
        
        # Update towers
        for tower in self.towers:
            tower.update(self.enemies, self.projectiles)
        
        # Spawn enemies
        current_time = pygame.time.get_ticks() / 1000
        if self.enemies_spawned < self.enemies_to_spawn and current_time - self.last_spawn_time > self.spawn_delay:
            self.spawn_enemy()
            self.last_spawn_time = current_time
        
        # Check for game over
        if self.lives <= 0:
            self.game_over = True
        
        # Check for wave complete
        if len(self.enemies) == 0 and self.enemies_spawned >= self.enemies_to_spawn:
            self.start_new_wave()
    
    def spawn_enemy(self):
        enemy = Enemy(self.path)
        self.enemies.append(enemy)
        self.enemies_spawned += 1
    
    def start_new_wave(self):
        self.wave += 1
        self.enemies_spawned = 0
        self.enemies_to_spawn = 10 + (self.wave - 1) * 5
        self.money += 20
    
    def handle_click(self, x, y):
        # Check if clicking on buildable area
        if self.level.is_buildable(x, y):
            # Build basic tower if enough money
            if self.money >= self.tower_types["basic"]["cost"]:
                tower = Tower(x, y, "basic", self.tower_types["basic"])
                self.towers.append(tower)
                self.money -= self.tower_types["basic"]["cost"]
    
    def draw(self, screen):
        # Draw background
        screen.fill((10, 30, 60))
        
        # Draw path
        self.level.draw(screen)
        
        # Draw towers
        for tower in self.towers:
            tower.draw(screen)
        
        # Draw enemies
        for enemy in self.enemies:
            enemy.draw(screen)
        
        # Draw projectiles
        for projectile in self.projectiles:
            projectile.draw(screen)