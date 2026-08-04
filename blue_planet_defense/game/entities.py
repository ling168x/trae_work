#!/usr/bin/env python3
# Game entities module for Blue Planet Defense

import pygame
import math

class Tower:
    def __init__(self, x, y, type, stats):
        self.x = x
        self.y = y
        self.type = type
        self.stats = stats
        self.last_fire_time = 0
        self.range = stats["range"]
        self.damage = stats["damage"]
        self.fire_rate = stats["fire_rate"]
        
    def update(self, enemies, projectiles):
        current_time = pygame.time.get_ticks() / 1000
        
        # Find target
        target = self.find_target(enemies)
        
        # Fire if ready and has target
        if target and current_time - self.last_fire_time > self.fire_rate:
            projectile = Projectile(self.x, self.y, target, self.damage, self.type)
            projectiles.append(projectile)
            self.last_fire_time = current_time
    
    def find_target(self, enemies):
        for enemy in enemies:
            distance = math.sqrt((self.x - enemy.x)**2 + (self.y - enemy.y)**2)
            if distance <= self.range and enemy.alive:
                return enemy
        return None
    
    def draw(self, screen):
        # Draw tower base
        pygame.draw.circle(screen, (0, 150, 255), (self.x, self.y), 30)
        
        # Draw tower type indicator
        if self.type == "basic":
            pygame.draw.circle(screen, (255, 255, 255), (self.x, self.y), 15)
        elif self.type == "ice":
            pygame.draw.circle(screen, (100, 200, 255), (self.x, self.y), 15)
        elif self.type == "cannon":
            pygame.draw.circle(screen, (255, 150, 50), (self.x, self.y), 15)
        
        # Draw range indicator
        pygame.draw.circle(screen, (0, 255, 0, 50), (self.x, self.y), self.range, 1)

class Enemy:
    def __init__(self, path):
        self.path = path
        self.path_index = 0
        self.x, self.y = path[0]
        self.speed = 1.0
        self.health = 100
        self.alive = True
        self.reached_end = False
        self.color = (255, 100, 100)
    
    def update(self):
        if not self.alive:
            return
        
        # Move along path
        if self.path_index < len(self.path) - 1:
            target_x, target_y = self.path[self.path_index + 1]
            dx = target_x - self.x
            dy = target_y - self.y
            distance = math.sqrt(dx**2 + dy**2)
            
            if distance < self.speed:
                self.x, self.y = target_x, target_y
                self.path_index += 1
            else:
                self.x += (dx / distance) * self.speed
                self.y += (dy / distance) * self.speed
        else:
            self.reached_end = True
            self.alive = False
    
    def take_damage(self, damage):
        self.health -= damage
        if self.health <= 0:
            self.alive = False
    
    def draw(self, screen):
        if self.alive:
            # Draw enemy
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), 20)
            
            # Draw health bar
            health_percent = self.health / 100
            pygame.draw.rect(screen, (255, 0, 0), (self.x - 20, self.y - 30, 40, 5))
            pygame.draw.rect(screen, (0, 255, 0), (self.x - 20, self.y - 30, 40 * health_percent, 5))

class Projectile:
    def __init__(self, x, y, target, damage, type):
        self.x = x
        self.y = y
        self.target = target
        self.damage = damage
        self.type = type
        self.speed = 5.0
        self.out_of_bounds = False
        
        # Set color based on type
        if type == "basic":
            self.color = (255, 255, 0)
        elif type == "ice":
            self.color = (100, 200, 255)
        elif type == "cannon":
            self.color = (255, 150, 50)
    
    def update(self):
        if not self.target or not self.target.alive:
            self.out_of_bounds = True
            return
        
        # Move towards target
        dx = self.target.x - self.x
        dy = self.target.y - self.y
        distance = math.sqrt(dx**2 + dy**2)
        
        if distance < self.speed:
            # Hit target
            self.target.take_damage(self.damage)
            self.out_of_bounds = True
        else:
            self.x += (dx / distance) * self.speed
            self.y += (dy / distance) * self.speed
    
    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), 5)