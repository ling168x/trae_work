#!/usr/bin/env python3
# Game levels module for Blue Planet Defense

import pygame

class Level:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.path = self.generate_path()
        self.buildable_areas = self.generate_buildable_areas()
    
    def generate_path(self):
        # Simple S-shaped path
        path = []
        
        # Start from left side
        start_x = 50
        start_y = self.height // 2
        
        # First segment: right
        for x in range(start_x, self.width // 2, 50):
            path.append((x, start_y))
        
        # Second segment: down
        for y in range(start_y, self.height - 100, 50):
            path.append((self.width // 2, y))
        
        # Third segment: right
        for x in range(self.width // 2, self.width - 50, 50):
            path.append((x, self.height - 100))
        
        return path
    
    def generate_buildable_areas(self):
        # Define buildable areas (not on path)
        buildable = []
        
        # Grid size
        grid_size = 60
        
        for x in range(0, self.width, grid_size):
            for y in range(0, self.height, grid_size):
                # Check if this spot is on the path
                on_path = False
                for (path_x, path_y) in self.path:
                    if abs(x - path_x) < 40 and abs(y - path_y) < 40:
                        on_path = True
                        break
                
                if not on_path:
                    buildable.append((x, y, grid_size, grid_size))
        
        return buildable
    
    def is_buildable(self, x, y):
        # Check if the position is buildable
        for (bx, by, bw, bh) in self.buildable_areas:
            if bx <= x <= bx + bw and by <= y <= by + bh:
                return True
        return False
    
    def draw(self, screen):
        # Draw path
        for i in range(len(self.path) - 1):
            pygame.draw.line(screen, (100, 100, 100), self.path[i], self.path[i+1], 40)
        
        # Draw buildable areas (for debugging)
        for (x, y, w, h) in self.buildable_areas:
            pygame.draw.rect(screen, (0, 100, 0, 50), (x, y, w, h), 1)