"""Punto de entrada del juego de plataformas procedural.

El módulo coordina la ventana de Pygame, la generación de niveles, el
personaje y la transición visual. La lógica especializada vive en
``personaje.py`` y ``transicion.py`` para mantener este archivo centrado en
el bucle principal del juego.
"""

import math
import os
import random

import cv2
import numpy as np
import pygame

from fondo import ParticulaAbstracta, dibujar_fondo_segmentado
from menu import MenuInicio
from personaje import PersonajeHumanoide
from plataformas import Plataforma, color_desde_hue
from transicion import TransicionCaricaturesca

# --------------------------------------------------------------------------
# Configuración general
# --------------------------------------------------------------------------
WIDTH, HEIGHT = 800, 600
FPS = 60

POS_SPAWN = pygame.Vector2(120, 235)  # centro del punto de aparición del jugador

ESTADO_MENU = "menu"
ESTADO_JUGANDO = "jugando"
ESTADO_TRANSICION = "transicion"
ESTADO_GAME_OVER = "game_over"


def opacidad_nivel(nivel):
    """Devuelve la intensidad de oscurecimiento acumulada por nivel.

    Se mantiene deliberadamente sutil: el efecto principal de progresión
    ahora lo lleva la pérdida de color (``saturacion_nivel``), no un velo
    negro sobre la pantalla.
    """
    return min(40, nivel * 3)


def saturacion_nivel(nivel):
    """Devuelve cuánto color se ha perdido acumuladamente por nivel.

    0.0 significa colores originales; 1.0 significa escala de grises total
    y homogénea. Se alcanza el gris completo hacia el nivel 12.
    """
    return min(1.0, nivel / 12)


def escala_grises(superficie, factor):
    """Mezcla ``superficie`` con su versión en escala de grises.

    Args:
        superficie: Superficie de Pygame a procesar.
        factor: 0.0 conserva los colores originales, 1.0 devuelve la
            superficie completamente desaturada; valores intermedios
            producen una mezcla proporcional.

    Returns:
        Una nueva superficie (o la misma, si ``factor`` es 0) con la
        desaturación aplicada.
    """
    if factor <= 0:
        return superficie
    factor = min(1.0, factor)

    colores = pygame.surfarray.array3d(superficie).astype(np.float32)
    pesos_luminosidad = np.array([0.299, 0.587, 0.114], dtype=np.float32)
    gris = (colores @ pesos_luminosidad)[:, :, None]

    mezcla = colores * (1 - factor) + gris * factor
    return pygame.surfarray.make_surface(mezcla.astype(np.uint8))


def cargar_gif(ruta, tamano):
    """Carga los fotogramas de un GIF para animarlo en Pygame."""
    captura = cv2.VideoCapture(ruta)
    if not captura.isOpened():
        return [], 0.1

    fps = captura.get(cv2.CAP_PROP_FPS) or 10.0
    fotogramas = []
    while True:
        ok, fotograma = captura.read()
        if not ok:
            break
        fotograma = cv2.cvtColor(fotograma, cv2.COLOR_BGR2RGB)
        fotograma = cv2.resize(fotograma, tamano, interpolation=cv2.INTER_NEAREST)
        superficie = pygame.image.frombuffer(fotograma.tobytes(), tamano, "RGB")
        fotogramas.append(superficie.convert() if pygame.display.get_surface() else superficie.copy())
    captura.release()
    return fotogramas, 1.0 / fps


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
    texto_boton = "VOLVER A INTENTAR"
    tamano_fuente = 36
    while tamano_fuente > 16 and pygame.font.SysFont(None, tamano_fuente, bold=True).size(texto_boton)[0] > boton_reintentar.width - 28:
        tamano_fuente -= 1
    fuente_boton = pygame.font.SysFont(None, tamano_fuente, bold=True)
    superficie_texto_boton = fuente_boton.render(texto_boton, True, (255, 245, 255))
    gifs_game_over = []
    for nombre_gif in ("image1.gif", "image2.gif", "image3.gif", "image4.gif"):
        fotogramas, duracion = cargar_gif(
            os.path.join("assets", nombre_gif), (WIDTH, HEIGHT)
        )
        if fotogramas:
            gifs_game_over.append((fotogramas, duracion))

    nivel = 0
    plataformas, hue_fondo, hue_jugador = generar_nivel(nivel)
    particulas = [ParticulaAbstracta(WIDTH, HEIGHT) for _ in range(12)]

    jugador = PersonajeHumanoide(*POS_SPAWN, color_desde_hue(hue_jugador))
    jugador.rect.center = POS_SPAWN

    estado = ESTADO_MENU
    transicion = None
    inicio_game_over = pygame.time.get_ticks()
    gif_game_over = []
    duracion_fotograma_gif = 0.1
    menu = MenuInicio(WIDTH, HEIGHT)
    jugando = True
    while jugando:
        clock.tick(FPS)
        tiempo = pygame.time.get_ticks() / 1000.0

        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                jugando = False
            if estado == ESTADO_MENU:
                accion_menu = menu.manejar_evento(evento)
                if accion_menu == "jugar":
                    estado = ESTADO_JUGANDO
                elif accion_menu == "salir":
                    jugando = False
            if estado == ESTADO_JUGANDO and evento.type == pygame.KEYDOWN and evento.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                jugador.saltar()
            elif estado == ESTADO_GAME_OVER and evento.type == pygame.KEYDOWN and evento.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
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
        if estado == ESTADO_MENU:
            menu.actualizar()
        elif estado == ESTADO_JUGANDO:
            jugador.mover(plataformas)
            alpha_overlay = 0

            plataforma_pisada = jugador.plataforma_actual
            if jugador.en_suelo and plataforma_pisada is not None and plataforma_pisada.es_trampa:
                plataforma_pisada.activar_trampa()
                jugador.iniciar_engullido(plataforma_pisada)
                inicio_game_over = pygame.time.get_ticks()
                if gifs_game_over:
                    gif_game_over, duracion_fotograma_gif = random.choice(gifs_game_over)
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
            if jugador.muriendo:
                jugador.actualizar_engullido()
            elif any(plataforma.trampa_activada for plataforma in plataformas):
                jugador.rect.y += 3

        elif estado == ESTADO_TRANSICION:
            if transicion.actualizar(jugador):
                estado = ESTADO_JUGANDO

        # --- Renderizado ---
        if estado == ESTADO_MENU:
            menu.dibujar(screen, pygame.mouse.get_pos())
        else:
            # La escena se dibuja aparte para poder desaturarla como un todo
            # antes de mezclarla con el resto de la interfaz.
            escena = pygame.Surface((WIDTH, HEIGHT))
            hay_gif_game_over = estado == ESTADO_GAME_OVER and bool(gif_game_over)

            if not hay_gif_game_over:
                dibujar_fondo_segmentado(escena, tiempo, hue_fondo, WIDTH, HEIGHT)

                for particula in particulas:
                    particula.actualizar()
                    particula.dibujar(escena, tiempo)

                for plataforma in plataformas:
                    if estado != ESTADO_GAME_OVER:
                        plataforma.actualizar()
                    plataforma.dibujar(escena, tiempo, nivel)

                jugador.dibujar(escena)

                if estado == ESTADO_TRANSICION:
                    transicion.dibujar(escena)

                # Los colores se van perdiendo a medida que suben los niveles.
                escena = escala_grises(escena, saturacion_nivel(nivel))
                screen.blit(escena, (0, 0))

            # La escena se vuelve progresivamente más opaca al avanzar.
            alpha_opacidad = opacidad_nivel(nivel)
            if alpha_opacidad > 0:
                capa_opacidad = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                capa_opacidad.fill((0, 0, 0, alpha_opacidad))
                screen.blit(capa_opacidad, (0, 0))

            panel_texto = pygame.Surface((110, 36), pygame.SRCALPHA)
            panel_texto.fill((0, 0, 0, 90))
            screen.blit(panel_texto, (6, 6))
            texto = font.render(f"Nivel: {nivel}", True, (255, 255, 255))
            screen.blit(texto, (14, 10))

            if estado == ESTADO_GAME_OVER:
                if gif_game_over:
                    indice_gif = int(
                        (pygame.time.get_ticks() - inicio_game_over)
                        / (duracion_fotograma_gif * 1000)
                    ) % len(gif_game_over)
                    fotograma_gif = gif_game_over[indice_gif]
                    screen.blit(fotograma_gif, (0, 0))

                ahora_boton = pygame.time.get_ticks() / 1000.0
                hover_boton = boton_reintentar.collidepoint(pygame.mouse.get_pos())
                pulso_boton = (math.sin(ahora_boton * 4.0) + 1.0) * 0.5
                escala_boton = 1.04 + pulso_boton * 0.025 if hover_boton else 1.0
                centro_boton = pygame.Vector2(boton_reintentar.center)
                ancho_boton = boton_reintentar.width * escala_boton
                alto_boton = boton_reintentar.height * escala_boton
                puntos_boton = [
                    (centro_boton.x - ancho_boton / 2 + 12, centro_boton.y - alto_boton / 2),
                    (centro_boton.x + ancho_boton / 2 - 8, centro_boton.y - alto_boton / 2),
                    (centro_boton.x + ancho_boton / 2, centro_boton.y - alto_boton / 2 + 12),
                    (centro_boton.x + ancho_boton / 2 - 10, centro_boton.y + alto_boton / 2),
                    (centro_boton.x - ancho_boton / 2 + 8, centro_boton.y + alto_boton / 2),
                    (centro_boton.x - ancho_boton / 2, centro_boton.y + alto_boton / 2 - 12),
                ]
                color_boton = (55, 30, 75) if hover_boton else (30, 22, 48)
                color_borde = (255, 170, 220) if hover_boton else (215, 125, 190)
                pygame.draw.polygon(screen, (8, 5, 18), [(x + 5, y + 7) for x, y in puntos_boton])
                pygame.draw.polygon(screen, color_boton, puntos_boton)
                pygame.draw.polygon(screen, color_borde, puntos_boton, 2)
                if hover_boton:
                    pygame.draw.line(
                        screen,
                        (255, int(150 + pulso_boton * 80), 235),
                        puntos_boton[0],
                        puntos_boton[1],
                        3,
                    )

                screen.blit(
                    superficie_texto_boton,
                    superficie_texto_boton.get_rect(center=boton_reintentar.center),
                )

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()