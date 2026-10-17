
"""Constantes globales del juego."""
 
import pygame
 
# Pantalla lógica (el lienzo se escala a la resolución real al presentarlo)
WIDTH, HEIGHT = 800, 600
FPS = 60
 
# Margen que se resta a la altura máxima de salto al generar plataformas
MARGEN_SALTO_SEGURO = 20
 
# Centro del punto de aparición del jugador
POS_SPAWN = pygame.Vector2(120, 235)
 
# Hitos de progresión por nivel
NIVEL_TRAMPAS = 10        # aparecen trampas y rutas opcionales
NIVEL_SALTOS_LARGOS = 17  # menos plataformas, más separadas
NIVEL_DESPERTAR = 30      # animación de catarsis; desaparecen enemigos/trampas
NIVEL_FINAL = 40          # créditos
 