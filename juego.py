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
from enemigo import generar_entidades
from idioma import texto
from menu import MenuInicio
from opciones import MenuOpciones
from pausa import MenuPausa
from personaje import PersonajeHumanoide
from plataformas import Plataforma, color_desde_hue
from transicion import TransicionCaricaturesca

# --------------------------------------------------------------------------
# Configuración general
# --------------------------------------------------------------------------
WIDTH, HEIGHT = 800, 600
FPS = 60
PESOS_LUMINOSIDAD = np.array([0.299, 0.587, 0.114], dtype=np.float32)

POS_SPAWN = pygame.Vector2(120, 235)  # centro del punto de aparición del jugador

ESTADO_MENU = "menu"
ESTADO_OPCIONES = "opciones"
ESTADO_PAUSA = "pausa"
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

    Rendimiento: esto se ejecuta en TODA la pantalla, en TODOS los
    fotogramas a partir de nivel 1 (``pygame.surfarray.array3d`` +
    operación numpy + ``make_surface`` sobre 800x600). Es de las
    operaciones más caras del bucle principal. Se reduce el coste
    procesando una copia más pequeña (1/3 de tamaño) y reescalando el
    resultado de vuelta: el numpy trabaja sobre ~9 veces menos píxeles,
    y como esto es una mezcla de color suave (no detalle fino), la
    pérdida de nitidez es imperceptible en movimiento.
    """
    if factor <= 0:
        return superficie
    factor = min(1.0, factor)

    ancho, alto = superficie.get_size()
    reduccion = 3
    tam_chico = (max(1, ancho // reduccion), max(1, alto // reduccion))
    chica = pygame.transform.scale(superficie, tam_chico)

    colores = pygame.surfarray.array3d(chica).astype(np.float32)
    gris = (colores @ PESOS_LUMINOSIDAD)[:, :, None]

    mezcla = colores * (1 - factor) + gris * factor
    resultado_chico = pygame.surfarray.make_surface(mezcla.astype(np.uint8))
    return pygame.transform.scale(resultado_chico, (ancho, alto))


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
    entidades = generar_entidades(nivel, plataformas, POS_SPAWN)
    return plataformas, hue_fondo, hue_jugador, entidades


# --------------------------------------------------------------------------
# Juego
# --------------------------------------------------------------------------
def main():
    """Inicializa Pygame y ejecuta el bucle de eventos, física y renderizado."""
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    lienzo = pygame.Surface((WIDTH, HEIGHT))
    pygame.display.set_caption(texto("en", "window_title"))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 36)
    boton_reintentar = pygame.Rect(WIDTH // 2 - 110, HEIGHT // 2 + 45, 220, 52)
    texto_boton = texto("en", "retry")
    tamano_fuente = 36
    while tamano_fuente > 16 and pygame.font.SysFont(None, tamano_fuente, bold=True).size(texto_boton)[0] > boton_reintentar.width - 28:
        tamano_fuente -= 1
    fuente_boton = pygame.font.SysFont(None, tamano_fuente, bold=True)
    superficie_texto_boton = fuente_boton.render(texto_boton, True, (255, 245, 255))
    escena = pygame.Surface((WIDTH, HEIGHT))
    fondo_cache = pygame.Surface((WIDTH, HEIGHT))
    capa_opacidad = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    panel_texto = pygame.Surface((110, 36), pygame.SRCALPHA)
    panel_texto.fill((0, 0, 0, 90))
    nivel_mostrado = None
    idioma_mostrado = None
    texto_nivel = None
    opacidad_mostrada = None
    nivel_fondo = None
    contador_frames = 0
    intensidad_shake = 0.0  # sacudida de cámara: da sensación de impacto/velocidad
    gifs_game_over = []
    for nombre_gif in ("image1.gif", "image2.gif", "image3.gif", "image4.gif"):
        fotogramas, duracion = cargar_gif(
            os.path.join("assets", nombre_gif), (WIDTH, HEIGHT)
        )
        if fotogramas:
            gifs_game_over.append((fotogramas, duracion))

    # Flashbacks: aparecen unos segundos como fondo y nunca cubren al jugador
    # ni la interfaz. image6 se reserva para los niveles iniciales y image5
    # para los niveles avanzados.
    fotogramas_flashback_inicial, duracion_flashback_inicial = cargar_gif(
        os.path.join("assets", "image6.gif"), (WIDTH, HEIGHT)
    )
    fotogramas_flashback_avanzado, duracion_flashback_avanzado = cargar_gif(
        os.path.join("assets", "image5.gif"), (WIDTH, HEIGHT)
    )
    flashback_activo = False
    flashback_inicio = 0.0
    flashback_duracion_total = 0.0
    fotogramas_flashback = []
    duracion_flashback = 0.1
    proximo_flashback = 0.0
    flashbacks_habilitados = False

    nivel = 0
    plataformas, hue_fondo, hue_jugador, entidades = generar_nivel(nivel)
    particulas = [ParticulaAbstracta(WIDTH, HEIGHT) for _ in range(12)]

    jugador = PersonajeHumanoide(*POS_SPAWN, color_desde_hue(hue_jugador))
    jugador.rect.center = POS_SPAWN

    estado = ESTADO_MENU
    transicion = None
    inicio_game_over = pygame.time.get_ticks()
    gif_game_over = []
    duracion_fotograma_gif = 0.1
    menu = MenuInicio(WIDTH, HEIGHT)
    pausa = MenuPausa(WIDTH, HEIGHT)
    configuracion = {
        "resoluciones": MenuOpciones.RESOLUCIONES,
        "resolucion": 0,
    "pantalla_completa": False,
        "idioma": "en",
        "controles": {
            "left": pygame.K_a,
            "right": pygame.K_d,
            "jump": pygame.K_SPACE,
            "down": pygame.K_s,
        },
    }
    opciones = MenuOpciones(WIDTH, HEIGHT, configuracion)
    estado_despues_opciones = ESTADO_MENU
    jugando = True
    while jugando:
        contador_frames += 1
        clock.tick(FPS)
        tiempo = pygame.time.get_ticks() / 1000.0
        intensidad_shake *= 0.82
        if intensidad_shake < 0.05:
            intensidad_shake = 0.0

        if 1 <= nivel <= 5:
            fotogramas_disponibles = fotogramas_flashback_inicial
            duracion_disponible = duracion_flashback_inicial
        elif nivel >= 15:
            fotogramas_disponibles = fotogramas_flashback_avanzado
            duracion_disponible = duracion_flashback_avanzado
        else:
            fotogramas_disponibles = []
            duracion_disponible = 0.1

        if estado != ESTADO_JUGANDO or not fotogramas_disponibles:
            flashback_activo = False
            flashbacks_habilitados = False
        elif not flashbacks_habilitados:
            flashbacks_habilitados = True
            fotogramas_flashback = fotogramas_disponibles
            duracion_flashback = duracion_disponible
            proximo_flashback = tiempo + random.uniform(3.0, 8.0)
        elif not flashback_activo and estado == ESTADO_JUGANDO and tiempo >= proximo_flashback:
            flashback_activo = True
            flashback_inicio = tiempo
            flashback_duracion_total = random.uniform(1.0, 2.0)
        elif flashback_activo and tiempo - flashback_inicio >= flashback_duracion_total:
            flashback_activo = False
            proximo_flashback = tiempo + random.uniform(6.0, 14.0)

        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                jugando = False
            if estado == ESTADO_MENU:
                evento_menu = evento
                if evento.type == pygame.MOUSEBUTTONDOWN:
                    evento_menu = pygame.event.Event(
                        evento.type,
                        {
                            "button": evento.button,
                            "pos": (
                                int(evento.pos[0] * WIDTH / screen.get_width()),
                                int(evento.pos[1] * HEIGHT / screen.get_height()),
                            ),
                        },
                    )
                accion_menu = menu.manejar_evento(evento_menu)
                if accion_menu == "jugar":
                    estado = ESTADO_JUGANDO
                elif accion_menu == "opciones":
                    estado_despues_opciones = ESTADO_MENU
                    estado = ESTADO_OPCIONES
                elif accion_menu == "salir":
                    jugando = False
            elif estado == ESTADO_PAUSA:
                evento_pausa = evento
                if evento.type == pygame.MOUSEBUTTONDOWN:
                    evento_pausa = pygame.event.Event(
                        evento.type,
                        {
                            "button": evento.button,
                            "pos": (
                                int(evento.pos[0] * WIDTH / screen.get_width()),
                                int(evento.pos[1] * HEIGHT / screen.get_height()),
                            ),
                        },
                    )
                accion_pausa = pausa.manejar_evento(evento_pausa)
                if accion_pausa == "continuar":
                    estado = ESTADO_JUGANDO
                elif accion_pausa == "opciones":
                    estado_despues_opciones = ESTADO_PAUSA
                    estado = ESTADO_OPCIONES
                elif accion_pausa == "salir":
                    jugando = False
            elif estado == ESTADO_OPCIONES:
                evento_opciones = evento
                if evento.type == pygame.MOUSEBUTTONDOWN:
                    evento_opciones = pygame.event.Event(
                        evento.type,
                        {
                            "button": evento.button,
                            "pos": (
                                int(evento.pos[0] * WIDTH / screen.get_width()),
                                int(evento.pos[1] * HEIGHT / screen.get_height()),
                            ),
                        },
                    )
                accion_opciones = opciones.manejar_evento(evento_opciones)
                if accion_opciones == "volver":
                    estado = estado_despues_opciones
                elif accion_opciones == "aplicar":
                    ancho_nuevo, alto_nuevo = configuracion["resoluciones"][configuracion["resolucion"]]
                    modo_ventana = pygame.FULLSCREEN if configuracion["pantalla_completa"] else 0
                    screen = pygame.display.set_mode((ancho_nuevo, alto_nuevo), modo_ventana)
                    menu.actualizar_tamano(WIDTH, HEIGHT)
                    menu.establecer_idioma(configuracion["idioma"])
                    pausa.actualizar_tamano(WIDTH, HEIGHT)
                    pausa.establecer_idioma(configuracion["idioma"])
                    opciones.actualizar_tamano(WIDTH, HEIGHT)
                    pygame.display.set_caption(texto(configuracion["idioma"], "window_title"))
                    texto_boton = texto(configuracion["idioma"], "retry")
                    tamano_fuente = 36
                    while tamano_fuente > 16 and pygame.font.SysFont(None, tamano_fuente, bold=True).size(texto_boton)[0] > boton_reintentar.width - 28:
                        tamano_fuente -= 1
                    fuente_boton = pygame.font.SysFont(None, tamano_fuente, bold=True)
                    superficie_texto_boton = fuente_boton.render(texto_boton, True, (255, 245, 255))
                    idioma_mostrado = None
                    estado = estado_despues_opciones
            if estado == ESTADO_JUGANDO and evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    pausa.establecer_idioma(configuracion["idioma"])
                    estado = ESTADO_PAUSA
                elif evento.key == configuracion["controles"]["jump"]:
                    jugador.saltar()
            elif estado == ESTADO_GAME_OVER and evento.type == pygame.KEYDOWN and evento.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                nivel = 0
                plataformas, hue_fondo, hue_jugador, entidades = generar_nivel(nivel)
                jugador = PersonajeHumanoide(*POS_SPAWN, color_desde_hue(hue_jugador))
                jugador.rect.center = POS_SPAWN
                transicion = None
                estado = ESTADO_JUGANDO
            if (
                evento.type == pygame.MOUSEBUTTONDOWN
                and evento.button == pygame.BUTTON_LEFT
                and estado == ESTADO_GAME_OVER
                and boton_reintentar.collidepoint(
                    (
                        int(evento.pos[0] * WIDTH / screen.get_width()),
                        int(evento.pos[1] * HEIGHT / screen.get_height()),
                    )
                )
            ):
                nivel = 0
                plataformas, hue_fondo, hue_jugador, entidades = generar_nivel(nivel)
                jugador = PersonajeHumanoide(*POS_SPAWN, color_desde_hue(hue_jugador))
                jugador.rect.center = POS_SPAWN
                transicion = None
                estado = ESTADO_JUGANDO

        # Durante la transición se bloquean los controles y solo se actualiza
        # la entrada visual del jugador al nuevo nivel.
        if estado == ESTADO_MENU:
            menu.actualizar()
        elif estado == ESTADO_JUGANDO:
            en_aire_antes = not jugador.en_suelo
            jugador.mover(plataformas, configuracion["controles"])
            for entidad in entidades:
                entidad.mover(plataformas, jugador.rect)

            # Pequeña sacudida de cámara al aterrizar: es barato (solo un
            # offset al hacer blit) y ayuda mucho a que los saltos se
            # sientan con más impacto/velocidad.
            if jugador.en_suelo and en_aire_antes:
                intensidad_shake = max(intensidad_shake, 3.5)

            plataforma_pisada = jugador.plataforma_actual
            if jugador.en_suelo and plataforma_pisada is not None and plataforma_pisada.es_trampa:
                plataforma_pisada.activar_trampa()
                jugador.iniciar_engullido(plataforma_pisada)
                inicio_game_over = pygame.time.get_ticks()
                intensidad_shake = 9.0
                if gifs_game_over:
                    gif_game_over, duracion_fotograma_gif = random.choice(gifs_game_over)
                estado = ESTADO_GAME_OVER

            if estado == ESTADO_JUGANDO and any(
                entidad.rect.colliderect(jugador.rect) for entidad in entidades
            ):
                inicio_game_over = pygame.time.get_ticks()
                intensidad_shake = 9.0
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

                plataformas, hue_fondo, hue_jugador, entidades = generar_nivel(nivel)
                color_destino = color_desde_hue(hue_jugador)

                transicion = TransicionCaricaturesca(
                    color_origen,
                    color_destino,
                    pos_origen,
                    POS_SPAWN,
                    nivel=nivel,
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
            posicion_raton = pygame.mouse.get_pos()
            posicion_raton_logica = (
                int(posicion_raton[0] * WIDTH / screen.get_width()),
                int(posicion_raton[1] * HEIGHT / screen.get_height()),
            )
            menu.dibujar(lienzo, posicion_raton_logica)
            screen.blit(pygame.transform.smoothscale(lienzo, screen.get_size()), (0, 0))
        elif estado == ESTADO_PAUSA:
            posicion_raton = pygame.mouse.get_pos()
            posicion_raton_logica = (
                int(posicion_raton[0] * WIDTH / screen.get_width()),
                int(posicion_raton[1] * HEIGHT / screen.get_height()),
            )
            pausa.dibujar(lienzo, posicion_raton_logica)
            screen.blit(pygame.transform.smoothscale(lienzo, screen.get_size()), (0, 0))
        elif estado == ESTADO_OPCIONES:
            opciones.dibujar(lienzo)
            screen.blit(pygame.transform.smoothscale(lienzo, screen.get_size()), (0, 0))
        else:
            # La escena se dibuja aparte para poder desaturarla como un todo
            # antes de mezclarla con el resto de la interfaz.
            hay_gif_game_over = estado == ESTADO_GAME_OVER and bool(gif_game_over)

            if not hay_gif_game_over:
                tiempo_flashback = tiempo - flashback_inicio
                indice_flashback = int(tiempo_flashback / duracion_flashback) % len(fotogramas_flashback) if flashback_activo else 0
                fotograma_flashback = fotogramas_flashback[indice_flashback] if flashback_activo else None

                # El fondo abstracto es lo más pesado de dibujar; con las
                # optimizaciones de fondo.py ya es mucho más barato, pero
                # de todas formas no hace falta recalcularlo en cada
                # fotograma: sus formas se mueven lento y a 20 Hz (cada 3
                # fotogramas a 60 FPS) sigue viéndose fluido.
                if contador_frames % 3 == 0 or nivel != nivel_fondo:
                    dibujar_fondo_segmentado(fondo_cache, tiempo, hue_fondo, WIDTH, HEIGHT, nivel)
                    nivel_fondo = nivel
                if fotograma_flashback is not None:
                    escena.blit(fotograma_flashback, (0, 0))
                else:
                    escena.blit(fondo_cache, (0, 0))

                for particula in particulas:
                    particula.actualizar()
                    particula.dibujar(escena, tiempo)

                for plataforma in plataformas:
                    if estado != ESTADO_GAME_OVER:
                        plataforma.actualizar()
                    plataforma.dibujar(escena, tiempo, nivel)

                for entidad in entidades:
                    entidad.dibujar(escena, tiempo)

                jugador.dibujar(escena)

                if estado == ESTADO_TRANSICION:
                    transicion.dibujar(escena)

                # Los colores se van perdiendo a medida que suben los niveles.
                escena = escala_grises(escena, saturacion_nivel(nivel))
                if intensidad_shake > 0:
                    lienzo.fill((0, 0, 0))
                    offset = (
                        random.uniform(-intensidad_shake, intensidad_shake),
                        random.uniform(-intensidad_shake, intensidad_shake),
                    )
                    lienzo.blit(escena, offset)
                else:
                    lienzo.blit(escena, (0, 0))

            # La escena se vuelve progresivamente más opaca al avanzar.
            alpha_opacidad = opacidad_nivel(nivel)
            if alpha_opacidad > 0:
                if alpha_opacidad != opacidad_mostrada:
                    capa_opacidad.fill((0, 0, 0, alpha_opacidad))
                    opacidad_mostrada = alpha_opacidad
                lienzo.blit(capa_opacidad, (0, 0))

            lienzo.blit(panel_texto, (6, 6))
            if nivel != nivel_mostrado or configuracion["idioma"] != idioma_mostrado:
                texto_nivel = font.render(
                    f"{texto(configuracion['idioma'], 'level')}: {nivel}",
                    True,
                    (255, 255, 255),
                )
                nivel_mostrado = nivel
                idioma_mostrado = configuracion["idioma"]
            lienzo.blit(texto_nivel, (14, 10))

            if estado == ESTADO_GAME_OVER:
                if gif_game_over:
                    indice_gif = int(
                        (pygame.time.get_ticks() - inicio_game_over)
                        / (duracion_fotograma_gif * 1000)
                    ) % len(gif_game_over)
                    fotograma_gif = gif_game_over[indice_gif]
                    lienzo.blit(fotograma_gif, (0, 0))

                ahora_boton = pygame.time.get_ticks() / 1000.0
                posicion_raton = pygame.mouse.get_pos()
                posicion_raton_logica = (
                    int(posicion_raton[0] * WIDTH / screen.get_width()),
                    int(posicion_raton[1] * HEIGHT / screen.get_height()),
                )
                hover_boton = boton_reintentar.collidepoint(posicion_raton_logica)
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
                pygame.draw.polygon(lienzo, (8, 5, 18), [(x + 5, y + 7) for x, y in puntos_boton])
                pygame.draw.polygon(lienzo, color_boton, puntos_boton)
                pygame.draw.polygon(lienzo, color_borde, puntos_boton, 2)
                if hover_boton:
                    pygame.draw.line(
                        lienzo,
                        (255, int(150 + pulso_boton * 80), 235),
                        puntos_boton[0],
                        puntos_boton[1],
                        3,
                    )

                lienzo.blit(
                    superficie_texto_boton,
                    superficie_texto_boton.get_rect(center=boton_reintentar.center),
                )

            screen.blit(pygame.transform.smoothscale(lienzo, screen.get_size()), (0, 0))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()