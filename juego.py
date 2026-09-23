
"""Punto de entrada del juego de plataformas procedural.

El módulo coordina la ventana de Pygame, la generación de niveles, el
personaje y la transición visual. La lógica especializada vive en
``personaje.py`` y ``transicion.py`` para mantener este archivo centrado en
el bucle principal del juego.
"""

import math
import os
import random
import sys

import cv2
import numpy as np
import pygame

from dificultad import parametros_dificultad
from fondo import ParticulaAbstracta, dibujar_fondo_segmentado
from enemigo import generar_entidades
from idioma import texto
from menu import MenuInicio
from opciones import MenuOpciones, cargar_configuracion, guardar_configuracion, normalizar_configuracion
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
ESTADO_ADVERTENCIA = "advertencia"
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


def aplicar_volumen_audio(configuracion, jugador=None):
    """Aplica el volumen general a todas las fuentes de audio del juego."""
    volumen = max(
        0.0,
        min(
            1.0,
            float(
                configuracion.get(
                    "volumen_musica",
                    configuracion.get("volumen_efectos", 0.8),
                )
            ),
        ),
    )
    configuracion["volumen_musica"] = volumen
    configuracion["volumen_efectos"] = volumen
    if pygame.mixer.get_init():
        pygame.mixer.music.set_volume(volumen)
    if jugador is not None:
        jugador.ajustar_volumen_efectos(volumen)


# --------------------------------------------------------------------------
# Generación de niveles
# --------------------------------------------------------------------------
def generar_nivel(nivel):
    """Crea un nivel y devuelve sus plataformas y colores base.

    Args:
        nivel: Número del nivel actual; aumenta gradualmente la cantidad de
            plataformas.

    Returns:
        Una tupla ``(plataformas, hue_fondo, hue_jugador, entidades)``.
    """
    parametros = parametros_dificultad(nivel)
    prob_movil = parametros["probabilidad_plataforma_movil"]

    plataformas = [
        Plataforma(50, 300, 150, 20, random.random(), probabilidad_movimiento=prob_movil)
    ]
    plataforma_guia = plataformas[0].rect
    ultimo_x = plataforma_guia.right

    if nivel >= 17:
        cantidad_plataformas = random.randint(5, 7)
        distancia_x = (95, 165)
        desplazamiento_y = (-150, 150)
    elif nivel >= 10:
        cantidad_plataformas = random.randint(8, 12)
        distancia_x = (35, 90)
        desplazamiento_y = (-125, 110)
    else:
        cantidad_plataformas = random.randint(7, 10)
        distancia_x = (25, 70)
        desplazamiento_y = (-85, 75)

    for indice in range(cantidad_plataformas):
        w = random.randint(50, 115) if nivel >= 10 else random.randint(65, 135)
        x = ultimo_x + random.randint(*distancia_x)
        y = max(70, min(HEIGHT - 50, plataforma_guia.top + random.randint(*desplazamiento_y)))
        es_trampa = nivel >= 10 and random.random() < 0.28
        plataforma_nueva = Plataforma(
            x, y, w, 20, random.random(), es_trampa, probabilidad_movimiento=prob_movil
        )
        plataformas.append(plataforma_nueva)
        plataforma_guia = plataforma_nueva.rect
        ultimo_x = plataforma_guia.right

        # Las rutas opcionales aparecen como decisiones laterales y no
        # reemplazan la ruta principal. En niveles medios también pueden
        # convertirse en caminos falsos.
        if nivel >= 10 and indice % 2 == 1 and random.random() < 0.65:
            x_opcional = x + random.randint(-35, 35)
            y_opcional = max(70, min(HEIGHT - 50, y + random.randint(-145, 145)))
            ancho_opcional = random.randint(45, 95)
            falso = nivel <= 16 and random.random() < 0.30
            plataformas.append(
                Plataforma(
                    x_opcional,
                    y_opcional,
                    ancho_opcional,
                    20,
                    random.random(),
                    falso or random.random() < 0.20,
                    probabilidad_movimiento=prob_movil,
                )
            )

    hue_fondo = random.random()
    hue_jugador = random.random()
    entidades = generar_entidades(
        nivel,
        plataformas,
        POS_SPAWN,
        velocidad_patrulla=parametros["velocidad_enemigo_patrulla"],
        velocidad_persecucion=parametros["velocidad_enemigo_persecucion"],
        rango_deteccion=parametros["rango_deteccion_enemigo"],
    )
    return plataformas, hue_fondo, hue_jugador, entidades


def ajustar_dificultad_jugador(jugador, nivel):
    """Aumenta el ritmo sin hacer que los primeros niveles sean bruscos."""
    parametros = parametros_dificultad(nivel)
    jugador.velocidad = parametros["velocidad_jugador"]
    jugador.gravedad = parametros["gravedad_jugador"]
    jugador.actualizar_nivel(nivel)


def dibujar_nivel(capa, fondo, plataformas, entidades, tiempo, nivel):
    """Pinta un nivel completo (fondo, plataformas y enemigos) en ``capa``.

    Se usa durante la transición: cada nivel se dibuja en su propia capa del
    tamaño de la pantalla y la cámara las desliza una junto a la otra.
    El personaje no se incluye: se dibuja aparte, por encima de todo.
    """
    capa.blit(fondo, (0, 0))
    for plataforma in plataformas:
        plataforma.dibujar(capa, tiempo, nivel)
    for entidad in entidades:
        entidad.dibujar(capa, tiempo)


# --------------------------------------------------------------------------
# Juego
# --------------------------------------------------------------------------
def main(nivel_inicial=1, idioma_inicial="en"):
    """Inicializa Pygame y ejecuta el bucle de eventos, física y renderizado."""
    idiomas_disponibles = {"en", "es", "pt", "ru"}
    if idioma_inicial not in idiomas_disponibles:
        idioma_inicial = "en"

    pygame.init()
    if not pygame.mixer.get_init():
        pygame.mixer.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    lienzo = pygame.Surface((WIDTH, HEIGHT))
    pygame.display.set_caption(texto(idioma_inicial, "window_title"))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 36)
    font_advertencia_titulo = pygame.font.SysFont(None, 46, bold=True)
    font_advertencia = pygame.font.SysFont(None, 26)
    font_advertencia_prompt = pygame.font.SysFont(None, 22)
    boton_reintentar = pygame.Rect(WIDTH // 2 - 110, HEIGHT // 2 + 45, 220, 52)
    texto_boton = texto(idioma_inicial, "retry")
    tamano_fuente = 36
    while tamano_fuente > 16 and pygame.font.SysFont(None, tamano_fuente, bold=True).size(texto_boton)[0] > boton_reintentar.width - 28:
        tamano_fuente -= 1
    fuente_boton = pygame.font.SysFont(None, tamano_fuente, bold=True)
    superficie_texto_boton = fuente_boton.render(texto_boton, True, (255, 245, 255))
    escena = pygame.Surface((WIDTH, HEIGHT))
    capa_nivel_anterior = pygame.Surface((WIDTH, HEIGHT))  # foto fija del nivel que se deja atrás
    capa_nivel_nuevo = pygame.Surface((WIDTH, HEIGHT))
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
    for nombre_gif in (
        "image1.gif",
        "image2.gif",
        "image3.gif",
        "image4.gif",
        "image12.gif",
        "image13.gif",
    ):
        fotogramas, duracion = cargar_gif(
            os.path.join("assets", nombre_gif), (WIDTH, HEIGHT)
        )
        if fotogramas:
            gifs_game_over.append((fotogramas, duracion))

    gif_game_over_nivel_alto = []
    fotogramas_game_over_alto, duracion_game_over_alto = cargar_gif(
        os.path.join("assets", "image14.gif"), (WIDTH, HEIGHT)
    )
    if fotogramas_game_over_alto:
        gif_game_over_nivel_alto = [(fotogramas_game_over_alto, duracion_game_over_alto)]

    secuencia_game_over = []
    for nombre_gif in ("image7.gif", "image8.gif", "image9.gif"):
        fotogramas, duracion = cargar_gif(
            os.path.join("assets", nombre_gif), (WIDTH, HEIGHT)
        )
        if fotogramas:
            secuencia_game_over.append((fotogramas, duracion))
    duracion_imagen_game_over = 3.0

    # Flashbacks: aparecen unos segundos como fondo y nunca cubren al jugador
    # ni la interfaz. image6 se reserva para los niveles iniciales y image5
    # para los niveles avanzados.
    fotogramas_flashback_inicial, duracion_flashback_inicial = cargar_gif(
        os.path.join("assets", "image15.gif"), (WIDTH, HEIGHT)
    )
    fotogramas_flashback_medioinicial, duracion_flashback_medioinicial = cargar_gif(
        os.path.join("assets", "image6.gif"), (WIDTH, HEIGHT)
    )
    fotogramas_flashback_avanzado, duracion_flashback_avanzado = cargar_gif(
        os.path.join("assets", "image5.gif"), (WIDTH, HEIGHT)
    )
    fotogramas_flashback_final, duracion_flashback_final = cargar_gif(
        os.path.join("assets", "image16.gif"), (WIDTH, HEIGHT)
    )
    flashback_activo = False
    flashback_inicio = 0.0
    flashback_duracion_total = 0.0
    fotogramas_flashback = []
    duracion_flashback = 0.1
    proximo_flashback = 0.0
    flashbacks_habilitados = False
    flashback_nivel_10_activo = False
    inicio_flashback_nivel_10 = 0.0
    duracion_flashback_nivel_10 = 3.0
    flashback_nivel_22_activo = False
    inicio_flashback_nivel_22 = 0.0
    duracion_flashback_nivel_22 = 2.5

    nivel = max(1, int(nivel_inicial))
    plataformas, hue_fondo, hue_jugador, entidades = generar_nivel(nivel)
    particulas = [ParticulaAbstracta(WIDTH, HEIGHT) for _ in range(12)]

    configuracion_guardada = cargar_configuracion()
    configuracion = normalizar_configuracion(configuracion_guardada)
    configuracion["resoluciones"] = MenuOpciones.RESOLUCIONES
    configuracion["idioma"] = configuracion.get("idioma", idioma_inicial)
    if configuracion["idioma"] not in {"en", "es", "pt", "ru"}:
        configuracion["idioma"] = idioma_inicial
    configuracion["resolucion"] = max(0, min(configuracion.get("resolucion", 0), len(MenuOpciones.RESOLUCIONES) - 1))
    configuracion["pantalla_completa"] = bool(configuracion.get("pantalla_completa", False))
    configuracion["volumen_musica"] = max(0.0, min(1.0, float(configuracion.get("volumen_musica", 0.8))))
    configuracion["volumen_efectos"] = max(0.0, min(1.0, float(configuracion.get("volumen_efectos", 0.8))))
    configuracion["controles"] = MenuOpciones.DEFAULTS["controles"].copy()
    configuracion["controles"].update(configuracion_guardada.get("controles", {}))

    jugador = PersonajeHumanoide(*POS_SPAWN, color_desde_hue(hue_jugador), configuracion["volumen_efectos"])
    jugador.rect.center = POS_SPAWN
    ajustar_dificultad_jugador(jugador, nivel)
    aplicar_volumen_audio(configuracion, jugador)

    estado = ESTADO_ADVERTENCIA
    transicion = None
    inicio_game_over = pygame.time.get_ticks()
    gif_game_over = []
    duracion_fotograma_gif = 0.1
    indice_imagen_game_over = 0
    menu = MenuInicio(WIDTH, HEIGHT, idioma=configuracion["idioma"])
    pausa = MenuPausa(WIDTH, HEIGHT, idioma=configuracion["idioma"])
    opciones = MenuOpciones(WIDTH, HEIGHT, configuracion)
    estado_despues_opciones = ESTADO_MENU
    jugando = True

    def aplicar_modo_pantalla():
        nonlocal screen
        ancho, alto = configuracion["resoluciones"][configuracion["resolucion"]]
        modo_ventana = pygame.FULLSCREEN if configuracion["pantalla_completa"] else 0
        screen = pygame.display.set_mode((ancho, alto), modo_ventana)

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
        elif nivel >= 22:
            fotogramas_disponibles = fotogramas_flashback_final
            duracion_disponible = duracion_flashback_final
        elif nivel >= 10:
            fotogramas_disponibles = fotogramas_flashback_avanzado
            duracion_disponible = duracion_flashback_avanzado
        elif nivel >= 6:
            fotogramas_disponibles = fotogramas_flashback_medioinicial
            duracion_disponible = duracion_flashback_medioinicial
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
            elif evento.type == pygame.KEYDOWN and evento.key == pygame.K_F11:
                configuracion["pantalla_completa"] = not configuracion["pantalla_completa"]
                aplicar_modo_pantalla()
            if estado == ESTADO_ADVERTENCIA and evento.type in (
                pygame.KEYDOWN,
                pygame.MOUSEBUTTONDOWN,
            ):
                estado = ESTADO_MENU
            elif estado == ESTADO_MENU:
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
                    guardar_configuracion(configuracion)
                    aplicar_volumen_audio(configuracion, jugador)
                    aplicar_modo_pantalla()
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
                    jugador.solicitar_salto()
            elif estado == ESTADO_GAME_OVER and evento.type == pygame.KEYDOWN and evento.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                nivel = 1
                plataformas, hue_fondo, hue_jugador, entidades = generar_nivel(nivel)
                jugador = PersonajeHumanoide(*POS_SPAWN, color_desde_hue(hue_jugador), configuracion["volumen_efectos"])
                jugador.rect.center = POS_SPAWN
                ajustar_dificultad_jugador(jugador, nivel)
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
                nivel = 1
                plataformas, hue_fondo, hue_jugador, entidades = generar_nivel(nivel)
                jugador = PersonajeHumanoide(*POS_SPAWN, color_desde_hue(hue_jugador), configuracion["volumen_efectos"])
                jugador.rect.center = POS_SPAWN
                ajustar_dificultad_jugador(jugador, nivel)
                transicion = None
                estado = ESTADO_JUGANDO

        # Durante la transición se bloquean los controles y solo se actualiza
        # la entrada visual del jugador al nuevo nivel.
        if estado == ESTADO_ADVERTENCIA:
            pass
        elif estado == ESTADO_MENU:
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
                indice_imagen_game_over = 0
                if nivel >= 20 and gif_game_over_nivel_alto:
                    gif_game_over, duracion_fotograma_gif = gif_game_over_nivel_alto[0]
                elif nivel >= 10 and secuencia_game_over:
                    gif_game_over, duracion_fotograma_gif = secuencia_game_over[0]
                elif gifs_game_over:
                    gif_game_over, duracion_fotograma_gif = random.choice(gifs_game_over)
                estado = ESTADO_GAME_OVER

            if estado == ESTADO_JUGANDO and any(
                entidad.rect.colliderect(jugador.rect) for entidad in entidades
            ):
                inicio_game_over = pygame.time.get_ticks()
                intensidad_shake = 9.0
                indice_imagen_game_over = 0
                if nivel >= 20 and gif_game_over_nivel_alto:
                    gif_game_over, duracion_fotograma_gif = gif_game_over_nivel_alto[0]
                elif nivel >= 10 and secuencia_game_over:
                    gif_game_over, duracion_fotograma_gif = secuencia_game_over[0]
                elif gifs_game_over:
                    gif_game_over, duracion_fotograma_gif = random.choice(gifs_game_over)
                estado = ESTADO_GAME_OVER

            # Se cambia de nivel en cuanto la mitad del cuerpo cruza el borde
            # vista y la cámara lo acompaña hacia el nivel siguiente.
            salio_por_la_derecha = jugador.rect.centerx >= WIDTH
            salio_por_otro_borde = (
                jugador.rect.top > HEIGHT
                or jugador.rect.right < 0
            )
            if salio_por_la_derecha:
                # Foto fija del nivel que se deja atrás: la cámara lo mostrará
                # deslizándose mientras sigue al personaje hacia el siguiente.
                dibujar_nivel(capa_nivel_anterior, fondo_cache, plataformas, entidades, tiempo, nivel)
                nivel += 1
                if nivel == 10:
                    flashback_nivel_10_activo = True
                    inicio_flashback_nivel_10 = tiempo
                elif nivel == 22:
                    flashback_nivel_22_activo = True
                    inicio_flashback_nivel_22 = tiempo
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
                    volumen_efectos=configuracion["volumen_efectos"],
                    suelo_spawn=plataformas[0].rect.top,  # los rebotes ocurren sobre la primera plataforma
                    ancho_pantalla=WIDTH,
                )
                jugador.vel_y = 0
                ajustar_dificultad_jugador(jugador, nivel)
                estado = ESTADO_TRANSICION
            elif salio_por_otro_borde:
                inicio_game_over = pygame.time.get_ticks()
                intensidad_shake = 9.0
                indice_imagen_game_over = 0
                if gifs_game_over:
                    gif_game_over, duracion_fotograma_gif = random.choice(gifs_game_over)
                estado = ESTADO_GAME_OVER

        elif estado == ESTADO_GAME_OVER:
            for plataforma in plataformas:
                plataforma.actualizar()
            if jugador.muriendo:
                jugador.actualizar_engullido()
            elif any(plataforma.trampa_activada for plataforma in plataformas):
                jugador.rect.y += 3

        elif estado == ESTADO_TRANSICION:
            transicion_terminada = transicion.actualizar(jugador)
            # Cada rebote del personaje al aterrizar sacude un poco la cámara.
            for fuerza_impacto in transicion.recoger_impactos():
                intensidad_shake = max(intensidad_shake, fuerza_impacto)
            if transicion_terminada:
                aplicar_volumen_audio(configuracion, jugador)
                estado = ESTADO_JUGANDO

        if flashback_nivel_10_activo and tiempo - inicio_flashback_nivel_10 >= duracion_flashback_nivel_10:
            flashback_nivel_10_activo = False
        if flashback_nivel_22_activo and tiempo - inicio_flashback_nivel_22 >= duracion_flashback_nivel_22:
            flashback_nivel_22_activo = False

        # --- Renderizado ---
        if estado == ESTADO_ADVERTENCIA:
            lienzo.fill((8, 8, 12))
            titulo_advertencia = font_advertencia_titulo.render(
                texto(configuracion["idioma"], "epilepsy_warning_title"),
                True,
                (255, 210, 80),
            )
            linea_advertencia_1 = font_advertencia.render(
                texto(configuracion["idioma"], "epilepsy_warning_line_1"),
                True,
                (245, 245, 245),
            )
            linea_advertencia_2 = font_advertencia.render(
                texto(configuracion["idioma"], "epilepsy_warning_line_2"),
                True,
                (245, 245, 245),
            )
            prompt_advertencia = font_advertencia_prompt.render(
                texto(configuracion["idioma"], "epilepsy_warning_continue"),
                True,
                (180, 180, 190),
            )
            lienzo.blit(titulo_advertencia, titulo_advertencia.get_rect(center=(WIDTH // 2, 190)))
            lienzo.blit(linea_advertencia_1, linea_advertencia_1.get_rect(center=(WIDTH // 2, 275)))
            lienzo.blit(linea_advertencia_2, linea_advertencia_2.get_rect(center=(WIDTH // 2, 315)))
            lienzo.blit(prompt_advertencia, prompt_advertencia.get_rect(center=(WIDTH // 2, 430)))
            screen.blit(pygame.transform.smoothscale(lienzo, screen.get_size()), (0, 0))
        elif estado == ESTADO_MENU:
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
                if estado == ESTADO_TRANSICION:
                    # Los dos niveles se dibujan uno junto al otro y la cámara
                    # se desliza del viejo al nuevo siguiendo al personaje.
                    camara = int(round(transicion.desplazamiento_camara()))
                    dibujar_nivel(capa_nivel_nuevo, fondo_cache, plataformas, entidades, tiempo, nivel)
                    escena.blit(capa_nivel_anterior, (-camara, 0))
                    escena.blit(capa_nivel_nuevo, (WIDTH - camara, 0))

                    for particula in particulas:
                        particula.actualizar()
                        particula.dibujar(escena, tiempo)

                    # Foco y cara primero; el personaje va por encima para que
                    # no lo tape la oscuridad.
                    transicion.dibujar(escena)
                    jugador.dibujar(escena)
                else:
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

                # Los colores se van perdiendo a medida que suben los niveles;
                # durante la transición el cambio es gradual, al ritmo de la cámara.
                nivel_visual = nivel - 1 + transicion.progreso_camara() if estado == ESTADO_TRANSICION else nivel
                escena = escala_grises(escena, saturacion_nivel(nivel_visual))
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
            nivel_hud = nivel - 1 if estado == ESTADO_TRANSICION and transicion.progreso_camara() < 0.5 else nivel
            if nivel_hud != nivel_mostrado or configuracion["idioma"] != idioma_mostrado:
                texto_nivel = font.render(
                    f"{texto(configuracion['idioma'], 'level')}: {nivel_hud}",
                    True,
                    (255, 255, 255),
                )
                nivel_mostrado = nivel_hud
                idioma_mostrado = configuracion["idioma"]
            lienzo.blit(texto_nivel, (14, 10))

            if estado == ESTADO_GAME_OVER:
                if nivel >= 20 and gif_game_over_nivel_alto:
                    gif_game_over, duracion_fotograma_gif = gif_game_over_nivel_alto[0]

                elif nivel >= 10 and secuencia_game_over:
                    indice_imagen_game_over = min(
                        int((pygame.time.get_ticks() - inicio_game_over) / 1000 / duracion_imagen_game_over),
                        len(secuencia_game_over) - 1,
                    )
                    gif_game_over, duracion_fotograma_gif = secuencia_game_over[indice_imagen_game_over]

                if gif_game_over:
                    indice_gif = int(
                        (pygame.time.get_ticks() - inicio_game_over)
                        / (duracion_fotograma_gif * 1000)
                    ) % len(gif_game_over)
                    fotograma_gif = gif_game_over[indice_gif]
                    offset_game_over = (
                        int(2 * math.sin(tiempo * 28.0)),
                        int(2 * math.cos(tiempo * 31.0)),
                    )
                    lienzo.blit(fotograma_gif, offset_game_over)

                ahora_boton = pygame.time.get_ticks() / 1000.0
                posicion_raton = pygame.mouse.get_pos()
                posicion_raton_logica = (
                    int(posicion_raton[0] * WIDTH / screen.get_width()),
                    int(posicion_raton[1] * HEIGHT / screen.get_height()),
                )
                hover_boton = boton_reintentar.collidepoint(posicion_raton_logica)

                rect_boton = menu._dibujar_boton_comic(lienzo, boton_reintentar, hover_boton)
                texto_retry = texto(configuracion["idioma"], "retry")
                menu._texto_centrado(
                    lienzo,
                    texto_retry,
                    menu.font_prompt,
                    rect_boton.center,
                    (255, 255, 255),
                )

                if hover_boton:
                    pulso_boton = (math.sin(ahora_boton * 4.0) + 1.0) * 0.5
                    brillo = int(180 + pulso_boton * 75)
                    pygame.draw.line(
                        lienzo,
                        (255, brillo, 255),
                        rect_boton.topleft,
                        (rect_boton.right, rect_boton.top),
                        2,
                    )

            if flashback_nivel_10_activo:
                lienzo.fill((0, 0, 0))
                texto_flashback = font.render(
                    texto(configuracion["idioma"], "level_10_flashback"),
                    True,
                    (255, 255, 255),
                )
                desplazamiento_flash = int(3 * math.sin(tiempo * 40.0))
                rect_flashback = texto_flashback.get_rect(center=(WIDTH // 2, HEIGHT // 2))
                rect_flashback.x += desplazamiento_flash
                lienzo.blit(
                    texto_flashback,
                    rect_flashback,
                )
            elif flashback_nivel_22_activo:
                lienzo.fill((0, 0, 0))
                veladura = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                veladura.fill((0, 0, 0, 185))
                lienzo.blit(veladura, (0, 0))

                edad = max(0.0, tiempo - inicio_flashback_nivel_22)
                intensidad_flash = max(0.0, 1.0 - edad / duracion_flashback_nivel_22)
                flash_alpha = int(210 * intensidad_flash * (0.5 + 0.5 * math.sin(tiempo * 34.0)))
                if flash_alpha > 0:
                    flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                    flash.fill((255, 255, 255, flash_alpha))
                    lienzo.blit(flash, (0, 0))

                for _ in range(22):
                    x = random.randint(0, WIDTH - 1)
                    y = random.randint(0, HEIGHT - 1)
                    w = random.randint(2, 7)
                    h = random.randint(2, 7)
                    pygame.draw.rect(lienzo, (245, 245, 245, 80), pygame.Rect(x, y, w, h))

                frase = texto(configuracion["idioma"], "level_22_flashback").upper()
                texto_flashback = font_advertencia_titulo.render(frase, True, (255, 245, 245))
                sombra_flashback = font_advertencia_titulo.render(frase, True, (18, 18, 18))
                rect_flashback = texto_flashback.get_rect(center=(WIDTH // 2, HEIGHT // 2))
                desplazamiento_x = int(12 * math.sin(tiempo * 45.0))
                desplazamiento_y = int(9 * math.cos(tiempo * 38.0))
                sombra_rect = rect_flashback.copy().move(6 + desplazamiento_x, 7 + desplazamiento_y)
                rect_temblor = rect_flashback.move(desplazamiento_x, desplazamiento_y)
                lienzo.blit(sombra_flashback, sombra_rect)
                lienzo.blit(texto_flashback, rect_temblor)

            screen.blit(pygame.transform.smoothscale(lienzo, screen.get_size()), (0, 0))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    nivel_inicial = 1
    idioma_inicial = "en"
    if "--nivel" in sys.argv:
        indice_nivel = sys.argv.index("--nivel") + 1
        if indice_nivel < len(sys.argv):
            try:
                nivel_inicial = int(sys.argv[indice_nivel])
            except ValueError:
                pass
    if "--idioma" in sys.argv:
        indice_idioma = sys.argv.index("--idioma") + 1
        if indice_idioma < len(sys.argv):
            idioma_inicial = sys.argv[indice_idioma].lower()
    main(nivel_inicial, idioma_inicial)