"""Punto de entrada del juego de plataformas procedural.

El módulo coordina la ventana de Pygame, la generación de niveles, el
personaje y la transición visual. La lógica especializada vive en
``personaje.py`` y ``transicion.py`` para mantener este archivo centrado en
el bucle principal del juego.
"""

import math
import random

import pygame

from personaje import PersonajeHumanoide
from plataformas import Plataforma, color_desde_hue
from transicion import TransicionCaricaturesca

# --------------------------------------------------------------------------
# Configuración general
# --------------------------------------------------------------------------
WIDTH, HEIGHT = 800, 600
FPS = 60

POS_SPAWN = pygame.Vector2(120, 235)  # centro del punto de aparición del jugador

ESTADO_JUGANDO = "jugando"
ESTADO_TRANSICION = "transicion"
ESTADO_GAME_OVER = "game_over"


# --------------------------------------------------------------------------
# Elementos visuales
# --------------------------------------------------------------------------
class ParticulaAbstracta:
    """Mancha de color translúcida que flota lentamente por el fondo,
    aportando el efecto de "lienzo vivo" característico del arte abstracto."""

    def __init__(self):
        self.pos = pygame.Vector2(random.uniform(0, WIDTH), random.uniform(0, HEIGHT))
        self.radio = random.uniform(24, 90)
        self.hue = random.random()
        self.vel = pygame.Vector2(random.uniform(-0.25, 0.25), random.uniform(-0.15, 0.15))
        self.fase = random.uniform(0, math.tau)

    def actualizar(self):
        """Mueve la partícula y la devuelve al borde opuesto de la pantalla."""
        self.pos.x = (self.pos.x + self.vel.x) % WIDTH
        self.pos.y = (self.pos.y + self.vel.y) % HEIGHT

    def dibujar(self, superficie, tiempo):
        """Pinta la partícula con tamaño y color animados."""
        hue = (self.hue + tiempo * 0.015) % 1.0
        color = color_desde_hue(hue, saturacion=0.5, valor=0.85)
        radio = self.radio + math.sin(tiempo * 2 + self.fase) * 6
        capa = pygame.Surface((radio * 2, radio * 2), pygame.SRCALPHA)
        pygame.draw.circle(capa, (*color, 40), (radio, radio), radio)
        superficie.blit(capa, self.pos - pygame.Vector2(radio, radio))


# --------------------------------------------------------------------------
# Generación de niveles
# --------------------------------------------------------------------------
def generar_nivel(nivel):
    """Genera las plataformas y los matices de color (fondo y jugador) de un
    nivel. La disposición de las plataformas conserva la misma lógica que
    el original; solo cambia cómo se representan visualmente."""
    """Crea un nivel y devuelve sus plataformas y colores base.

    Args:
        nivel: Número del nivel actual; aumenta gradualmente la cantidad de
            plataformas.

    Returns:
        Una tupla ``(plataformas, hue_fondo, hue_jugador)``.
    """
    plataformas = [Plataforma(50, 300, 150, 20, random.random())]

    cantidad_plataformas = min(6 + nivel // 2, 14)  # ahora sí escala con el nivel
    for _ in range(cantidad_plataformas):
        x = random.randint(0, WIDTH - 100)
        y = random.randint(100, HEIGHT - 50)
        w = random.randint(50, 200)
        h = 20
        if not (x < 200 and 250 < y < 350):  # evita tapar el punto de aparición
            plataformas.append(Plataforma(x, y, w, h, random.random(), random.random() < 0.28))

    hue_fondo = random.random()
    hue_jugador = random.random()
    return plataformas, hue_fondo, hue_jugador


# --------------------------------------------------------------------------
# Juego
# --------------------------------------------------------------------------
def main():
    """Inicializa Pygame y ejecuta el bucle de eventos, física y renderizado."""
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Plataformas Procedurales - Lienzo Abstracto")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 36)
    boton_reintentar = pygame.Rect(WIDTH // 2 - 110, HEIGHT // 2 + 45, 220, 52)

    nivel = 0
    plataformas, hue_fondo, hue_jugador = generar_nivel(nivel)
    particulas = [ParticulaAbstracta() for _ in range(12)]

    jugador = PersonajeHumanoide(*POS_SPAWN, color_desde_hue(hue_jugador))
    jugador.rect.center = POS_SPAWN

    estado = ESTADO_JUGANDO
    transicion = None

    jugando = True
    while jugando:
        clock.tick(FPS)
        tiempo = pygame.time.get_ticks() / 1000.0

        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                jugando = False
            if evento.type == pygame.KEYDOWN:
                if estado == ESTADO_JUGANDO and evento.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                    jugador.saltar()
                elif estado == ESTADO_GAME_OVER and evento.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                    nivel = 0
                    plataformas, hue_fondo, hue_jugador = generar_nivel(nivel)
                    jugador = PersonajeHumanoide(*POS_SPAWN, color_desde_hue(hue_jugador))
                    jugador.rect.center = POS_SPAWN
                    transicion = None
                    estado = ESTADO_JUGANDO
            if (
                evento.type == pygame.MOUSEBUTTONDOWN
                and evento.button == pygame.BUTTON_LEFT
                and estado == ESTADO_GAME_OVER
                and boton_reintentar.collidepoint(evento.pos)
            ):
                nivel = 0
                plataformas, hue_fondo, hue_jugador = generar_nivel(nivel)
                jugador = PersonajeHumanoide(*POS_SPAWN, color_desde_hue(hue_jugador))
                jugador.rect.center = POS_SPAWN
                transicion = None
                estado = ESTADO_JUGANDO

        # Durante la transición se bloquean los controles y solo se actualiza
        # la entrada visual del jugador al nuevo nivel.
        if estado == ESTADO_JUGANDO:
            jugador.mover(plataformas)
            alpha_overlay = 0

            plataforma_pisada = jugador.plataforma_actual
            if jugador.en_suelo and plataforma_pisada is not None and plataforma_pisada.es_trampa:
                plataforma_pisada.activar_trampa()
                estado = ESTADO_GAME_OVER

            salio_de_pantalla = (
                jugador.rect.top > HEIGHT
                or jugador.rect.right < 0
                or jugador.rect.left > WIDTH
                or jugador.rect.bottom < 0
            )
            if salio_de_pantalla:
                nivel += 1
                color_origen = jugador.color
                pos_origen = pygame.Vector2(jugador.rect.center)

                plataformas, hue_fondo, hue_jugador = generar_nivel(nivel)
                color_destino = color_desde_hue(hue_jugador)

                transicion = TransicionCaricaturesca(
                    color_origen,
                    color_destino,
                    pos_origen,
                    POS_SPAWN,
                )
                jugador.vel_y = 0
                estado = ESTADO_TRANSICION

        elif estado == ESTADO_GAME_OVER:
            for plataforma in plataformas:
                plataforma.actualizar()
            if any(plataforma.trampa_activada for plataforma in plataformas):
                jugador.rect.y += 3

        elif estado == ESTADO_TRANSICION:
            if transicion.actualizar(jugador):
                estado = ESTADO_JUGANDO

        # --- Renderizado ---
        color_fondo = color_desde_hue((hue_fondo + math.sin(tiempo * 0.3) * 0.04) % 1.0, 0.4, 0.9)
        screen.fill(color_fondo)

        for particula in particulas:
            particula.actualizar()
            particula.dibujar(screen, tiempo)

        for plataforma in plataformas:
            if estado != ESTADO_GAME_OVER:
                plataforma.actualizar()
            plataforma.dibujar(screen, tiempo, nivel)

        jugador.dibujar(screen)

        if estado == ESTADO_TRANSICION:
            transicion.dibujar(screen)

        panel_texto = pygame.Surface((110, 36), pygame.SRCALPHA)
        panel_texto.fill((0, 0, 0, 90))
        screen.blit(panel_texto, (6, 6))
        texto = font.render(f"Nivel: {nivel}", True, (255, 255, 255))
        screen.blit(texto, (14, 10))

        if estado == ESTADO_GAME_OVER:
            mensaje = font.render("FELICIDADES - la trampa te ha tragado", True, (255, 245, 245))
            screen.blit(mensaje, mensaje.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 25)))

            color_boton = (36, 28, 55)
            if boton_reintentar.collidepoint(pygame.mouse.get_pos()):
                color_boton = (65, 45, 92)
            pygame.draw.rect(screen, color_boton, boton_reintentar, border_radius=8)
            pygame.draw.rect(screen, (255, 245, 245), boton_reintentar, 2, border_radius=8)
            texto_boton = font.render("VOLVER A INTENTAR", True, (255, 255, 255))
            screen.blit(texto_boton, texto_boton.get_rect(center=boton_reintentar.center))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()