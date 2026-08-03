#!/usr/bin/env python3
# Main game file for Blue Planet Defense

import pygame
import sys
import os
from game.core import Game
from ui.ui import UI

class BluePlanetDefense:
    def __init__(self):
        # Initialize pygame
        pygame.init()
        
        # Set up display
        self.width, self.height = 1024, 768
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Blue Planet Defense")
        
        # Set up clock
        self.clock = pygame.time.Clock()
        self.fps = 60
        
        # Initialize game components
        self.game = Game(self.width, self.height)
        self.ui = UI(self.width, self.height)
        
        # Game state
        self.running = True
        self.game_state = "menu"  # menu, game, game_over
    
    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                
                # Handle events based on game state
                if self.game_state == "menu":
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        x, y = pygame.mouse.get_pos()
                        if self.ui.start_button.collidepoint(x, y):
                            self.game_state = "game"
                
                elif self.game_state == "game":
                    # Handle game events
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        x, y = pygame.mouse.get_pos()
                        # Handle tower placement
                        self.game.handle_click(x, y)
            
            # Update game
            if self.game_state == "game":
                self.game.update()
                if self.game.game_over:
                    self.game_state = "game_over"
            
            # Draw
            self.screen.fill((10, 30, 60))  # Deep blue background
            
            if self.game_state == "menu":
                self.ui.draw_menu(self.screen)
            elif self.game_state == "game":
                self.game.draw(self.screen)
                self.ui.draw_game_ui(self.screen, self.game)
            elif self.game_state == "game_over":
                self.ui.draw_game_over(self.screen, self.game.score)
            
            # Update display
            pygame.display.flip()
            
            # Control fps
            self.clock.tick(self.fps)
    
    def quit(self):
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    game = BluePlanetDefense()
    game.run()