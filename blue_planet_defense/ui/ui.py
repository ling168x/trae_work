#!/usr/bin/env python3
# UI module for Blue Planet Defense

import pygame

class UI:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        
        # Initialize fonts
        pygame.font.init()
        self.font = pygame.font.Font(None, 36)
        self.title_font = pygame.font.Font(None, 72)
        
        # UI elements
        self.start_button = pygame.Rect(width // 2 - 100, height // 2, 200, 50)
    
    def draw_menu(self, screen):
        # Draw title
        title_text = self.title_font.render("Blue Planet Defense", True, (255, 255, 255))
        title_rect = title_text.get_rect(center=(self.width // 2, self.height // 3))
        screen.blit(title_text, title_rect)
        
        # Draw start button
        pygame.draw.rect(screen, (0, 150, 255), self.start_button)
        start_text = self.font.render("Start Game", True, (255, 255, 255))
        start_rect = start_text.get_rect(center=self.start_button.center)
        screen.blit(start_text, start_rect)
        
        # Draw instructions
        instructions = [
            "Build towers to defend your planet",
            "Click on buildable areas to place towers",
            "Earn money by defeating enemies",
            "Survive as many waves as possible"
        ]
        
        for i, instruction in enumerate(instructions):
            text = self.font.render(instruction, True, (200, 200, 200))
            text_rect = text.get_rect(center=(self.width // 2, self.height // 2 + 80 + i * 40))
            screen.blit(text, text_rect)
    
    def draw_game_ui(self, screen, game):
        # Draw stats
        stats = [
            f"Score: {game.score}",
            f"Lives: {game.lives}",
            f"Money: ${game.money}",
            f"Wave: {game.wave}"
        ]
        
        for i, stat in enumerate(stats):
            text = self.font.render(stat, True, (255, 255, 255))
            screen.blit(text, (20, 20 + i * 40))
        
        # Draw tower info
        tower_info = [
            "Basic Tower: $50",
            "Ice Tower: $100",
            "Cannon Tower: $150"
        ]
        
        for i, info in enumerate(tower_info):
            text = self.font.render(info, True, (255, 255, 255))
            screen.blit(text, (self.width - 200, 20 + i * 40))
    
    def draw_game_over(self, screen, score):
        # Draw game over screen
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
        
        # Draw game over text
        game_over_text = self.title_font.render("Game Over", True, (255, 100, 100))
        game_over_rect = game_over_text.get_rect(center=(self.width // 2, self.height // 3))
        screen.blit(game_over_text, game_over_rect)
        
        # Draw score
        score_text = self.font.render(f"Final Score: {score}", True, (255, 255, 255))
        score_rect = score_text.get_rect(center=(self.width // 2, self.height // 2))
        screen.blit(score_text, score_rect)
        
        # Draw restart button
        restart_button = pygame.Rect(self.width // 2 - 100, self.height // 2 + 50, 200, 50)
        pygame.draw.rect(screen, (0, 150, 255), restart_button)
        restart_text = self.font.render("Play Again", True, (255, 255, 255))
        restart_rect = restart_text.get_rect(center=restart_button.center)
        screen.blit(restart_text, restart_rect)