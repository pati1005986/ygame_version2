"""Punto de entrada del juego de plataformas procedural.

El módulo coordina la ventana de Pygame, la generación de niveles, el
personaje y la transición visual. La lógica especializada vive en
``eventos.py``, ``personaje.py`` y ``transicion.py`` para mantener este
archivo centrado en el bucle principal.
"""

import math
import random
import sys

import numpy as np
import pygame

from dificultad import parametros_dificultad
from catarsis import play_catarsis_animation
from eventos import (
    ESTADO_ADVERTENCIA,
    ESTADO_GAME_OVER,
    ESTADO_JUGANDO,
    ESTADO_MENU,
    ESTADO_OPCIONES,
    ESTADO_PAUSA,
    ESTADO_TRANSICION,
    DependenciasEventos,
    EventosVisuales,
    EstadoEventos,
    escala_grises,
    opacidad_nivel,
    procesar_eventos,
    saturacion_nivel,
)
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

POS_SPAWN = pygame.Vector2(120, 235)  # centro del punto de aparición del jugador


def crear_vineta_peligro(ancho, alto):
    """Prepara UNA VEZ (no en cada fotograma) una superficie con una viñeta
    roja radial: transparente en el centro, más opaca hacia los bordes.

    Se usa como aviso de que un enemigo está muy cerca: cada fotograma solo
    hace falta ajustar su transparencia global (``set_alpha``) según
    ``alerta_enemigos`` y pegarla (un solo ``blit``), así que es barata de
    mantener en el bucle principal aunque el cálculo con numpy que arma el
    degradado -relativamente caro- se hace solo aquí, al iniciar el juego.
    """
    y, x = np.mgrid[0:alto, 0:ancho]
    centro_x, centro_y = ancho / 2, alto / 2
    distancia = np.sqrt(((x - centro_x) / centro_x) ** 2 + ((y - centro_y) / centro_y) ** 2)
    alpha = np.clip((distancia - 0.55) / (1.3 - 0.55), 0.0, 1.0) ** 1.6

    rgba = np.zeros((alto, ancho, 4), dtype=np.uint8)
    rgba[:, :, 0] = 175  # tinte rojo de advertencia
    rgba[:, :, 1] = 15
    rgba[:, :, 2] = 15
    rgba[:, :, 3] = (alpha * 235).astype(np.uint8)
    superficie = pygame.image.frombuffer(rgba.tobytes(), (ancho, alto), "RGBA")
    return superficie.convert_alpha()


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
        ancho_pantalla=WIDTH,
        alto_pantalla=HEIGHT,
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
    font = pygame.font.Font(None, 36)
    font_advertencia_titulo = pygame.font.Font(None, 46)
    font_advertencia_titulo.set_bold(True)
    font_advertencia = pygame.font.Font(None, 26)
    font_advertencia_prompt = pygame.font.Font(None, 22)
    boton_reintentar = pygame.Rect(WIDTH // 2 - 110, HEIGHT // 2 + 45, 220, 52)
    texto_boton = texto(idioma_inicial, "retry")
    tamano_fuente = 36
    fuente_boton = pygame.font.Font(None, tamano_fuente)
    fuente_boton.set_bold(True)
    while tamano_fuente > 16 and fuente_boton.size(texto_boton)[0] > boton_reintentar.width - 28:
        tamano_fuente -= 1
        fuente_boton = pygame.font.Font(None, tamano_fuente)
        fuente_boton.set_bold(True)
    superficie_texto_boton = fuente_boton.render(texto_boton, True, (255, 245, 255))
    idioma_advertencia_mostrado = None
    textos_advertencia = None
    escena = pygame.Surface((WIDTH, HEIGHT))
    capa_nivel_anterior = pygame.Surface((WIDTH, HEIGHT))  # foto fija del nivel que se deja atrás
    capa_nivel_nuevo = pygame.Surface((WIDTH, HEIGHT))
    fondo_cache = pygame.Surface((WIDTH, HEIGHT))
    capa_opacidad = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    vineta_peligro = crear_vineta_peligro(WIDTH, HEIGHT)
    panel_texto = pygame.Surface((110, 36), pygame.SRCALPHA)
    panel_texto.fill((0, 0, 0, 90))
    nivel_mostrado = None
    idioma_mostrado = None
    texto_nivel = None
    opacidad_mostrada = None
    nivel_fondo = None
    intensidad_shake = 0.0  # sacudida de cámara: da sensación de impacto/velocidad
    alerta_enemigos = 0.0  # 0-1: qué tan cerca está el enemigo más próximo
    tiempo_ultimo_fondo = -1.0
    combo_actual = 0
    combo_mejor_nivel = 0
    combo_expira = 0
    resumen_combo = 0
    resumen_expira = 0
    combo_hud_clave = None
    combo_hud_superficie = None
    resumen_clave = None
    resumen_superficies = None
    fuente_combo = pygame.font.Font(None, 26)
    fuente_combo.set_bold(True)
    fuente_resumen = pygame.font.Font(None, 32)
    fuente_resumen.set_bold(True)
    eventos_visuales = EventosVisuales(WIDTH, HEIGHT)

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
    configuracion["escala_ui"] = float(configuracion.get("escala_ui", 1.0))
    if configuracion["escala_ui"] not in MenuOpciones.ESCALAS_UI:
        configuracion["escala_ui"] = 1.0
    configuracion["controles"] = MenuOpciones.DEFAULTS["controles"].copy()
    configuracion["controles"].update(configuracion_guardada.get("controles", {}))

    jugador = PersonajeHumanoide(
        *POS_SPAWN,
        color_desde_hue(hue_jugador),
        configuracion["volumen_efectos"],
        dash_habilitado=True,
    )
    jugador.rect.center = POS_SPAWN
    ajustar_dificultad_jugador(jugador, nivel)
    aplicar_volumen_audio(configuracion, jugador)

    estado = ESTADO_ADVERTENCIA
    transicion = None
    despertar_mostrado = False
    menu = MenuInicio(WIDTH, HEIGHT, idioma=configuracion["idioma"], escala_ui=configuracion["escala_ui"])
    pausa = MenuPausa(WIDTH, HEIGHT, idioma=configuracion["idioma"], escala_ui=configuracion["escala_ui"])
    opciones = MenuOpciones(WIDTH, HEIGHT, configuracion)
    estado_despues_opciones = ESTADO_MENU
    jugando = True

    dependencias_eventos = DependenciasEventos(
        width=WIDTH,
        height=HEIGHT,
        pos_spawn=POS_SPAWN,
        menu=menu,
        pausa=pausa,
        opciones=opciones,
        configuracion=configuracion,
        generar_nivel=generar_nivel,
        color_desde_hue=color_desde_hue,
        crear_jugador=PersonajeHumanoide,
        ajustar_dificultad_jugador=ajustar_dificultad_jugador,
        aplicar_volumen_audio=aplicar_volumen_audio,
        guardar_configuracion=guardar_configuracion,
        texto=texto,
    )

    # Conserva la física histórica por fotograma, desacoplándola del render.
    paso_fisica = 1 / FPS
    acumulador_fisica = paso_fisica

    def actualizar_mundo(dt):
        nonlocal intensidad_shake, alerta_enemigos
        nonlocal jugador, estado, nivel, plataformas
        nonlocal hue_fondo, hue_jugador, entidades, transicion
        nonlocal combo_actual, combo_mejor_nivel, combo_expira
        nonlocal resumen_combo, resumen_expira

        tiempo_mundo = pygame.time.get_ticks() / 1000.0
        intensidad_shake *= 0.82
        if intensidad_shake < 0.05:
            intensidad_shake = 0.0
        alerta_enemigos *= 0.9
        if alerta_enemigos < 0.02:
            alerta_enemigos = 0.0

        hay_gif_game_over = (
            estado == ESTADO_GAME_OVER
            and (
                bool(eventos_visuales.gif_game_over)
                or eventos_visuales.game_over_nivel_alto_activo
            )
        )
        if estado == ESTADO_JUGANDO:
            en_aire_antes = not jugador.en_suelo
            dash_activo = jugador.dash_restante > 0
            jugador.mover(plataformas, configuracion["controles"])
            ahora_combo = pygame.time.get_ticks()
            if jugador._salto_ejecutado_este_frame and en_aire_antes:
                registrar_truco(ahora_combo)
            if jugador.dash_ejecutado_este_frame:
                registrar_truco(ahora_combo)
                jugador.dash_ejecutado_este_frame = False
            if not eventos_visuales.evento_flashback_especial_activo:
                for entidad in entidades:
                    entidad.mover(plataformas, jugador.rect)
                alerta_enemigos = max(
                    alerta_enemigos,
                    max(
                        (entidad.nivel_alerta() for entidad in entidades),
                        default=0.0,
                    ),
                )
                if alerta_enemigos > 0:
                    intensidad_shake = max(
                        intensidad_shake, alerta_enemigos * 2.2
                    )

            if jugador.en_suelo and en_aire_antes:
                intensidad_shake = max(intensidad_shake, 3.5)

            plataforma_pisada = jugador.plataforma_actual
            if (
                jugador.en_suelo
                and plataforma_pisada is not None
                and plataforma_pisada.es_trampa
            ):
                plataforma_pisada.activar_trampa()
                jugador.iniciar_engullido(plataforma_pisada)
                intensidad_shake = 9.0
                eventos_visuales.iniciar_game_over(
                    nivel, pygame.time.get_ticks()
                )
                estado = ESTADO_GAME_OVER

            if estado == ESTADO_JUGANDO and not dash_activo and any(
                entidad.rect.colliderect(jugador.rect) for entidad in entidades
            ):
                intensidad_shake = 9.0
                eventos_visuales.iniciar_game_over(
                    nivel, pygame.time.get_ticks()
                )
                estado = ESTADO_GAME_OVER
                combo_actual = 0
                combo_mejor_nivel = 0
                combo_expira = 0

            salio_por_la_derecha = jugador.rect.centerx >= WIDTH
            salio_por_otro_borde = (
                jugador.rect.top > HEIGHT or jugador.rect.right < 0
            )
            if salio_por_la_derecha:
                resumen_combo = combo_mejor_nivel
                resumen_expira = pygame.time.get_ticks() + 1800
                combo_actual = 0
                combo_mejor_nivel = 0
                combo_expira = 0
                dibujar_nivel(
                    capa_nivel_anterior,
                    fondo_cache,
                    plataformas,
                    entidades,
                    tiempo_mundo,
                    nivel,
                )
                nivel += 1
                eventos_visuales.entrar_nivel(nivel, tiempo_mundo)
                color_origen = jugador.color
                pos_origen = pygame.Vector2(jugador.rect.center)

                plataformas, hue_fondo, hue_jugador, entidades = generar_nivel(
                    nivel
                )
                color_destino = color_desde_hue(hue_jugador)
                transicion = TransicionCaricaturesca(
                    color_origen,
                    color_destino,
                    pos_origen,
                    POS_SPAWN,
                    nivel=nivel,
                    volumen_efectos=configuracion["volumen_efectos"],
                    suelo_spawn=plataformas[0].rect.top,
                    ancho_pantalla=WIDTH,
                )
                jugador.vel_y = 0
                ajustar_dificultad_jugador(jugador, nivel)
                estado = ESTADO_TRANSICION
            elif salio_por_otro_borde:
                intensidad_shake = 9.0
                eventos_visuales.iniciar_game_over(
                    nivel,
                    pygame.time.get_ticks(),
                    seleccionar_por_nivel=False,
                )
                estado = ESTADO_GAME_OVER
                combo_actual = 0
                combo_mejor_nivel = 0
                combo_expira = 0

        elif estado == ESTADO_GAME_OVER:
            combo_actual = 0
            combo_mejor_nivel = 0
            combo_expira = 0
            resumen_expira = 0
            for plataforma in plataformas:
                plataforma.actualizar(dt)
            if jugador.muriendo:
                jugador.actualizar_engullido()
            elif any(plataforma.trampa_activada for plataforma in plataformas):
                jugador.rect.y += 3

        elif estado == ESTADO_TRANSICION:
            transicion_terminada = transicion.actualizar(jugador)
            for fuerza_impacto in transicion.recoger_impactos():
                intensidad_shake = max(intensidad_shake, fuerza_impacto)
            if transicion_terminada:
                aplicar_volumen_audio(configuracion, jugador)
                estado = ESTADO_JUGANDO

        if estado == ESTADO_JUGANDO:
            for plataforma in plataformas:
                plataforma.actualizar(dt)

        hay_gif_game_over = (
            estado == ESTADO_GAME_OVER
            and (
                bool(eventos_visuales.gif_game_over)
                or eventos_visuales.game_over_nivel_alto_activo
            )
        )
        if estado in (
            ESTADO_JUGANDO,
            ESTADO_TRANSICION,
            ESTADO_GAME_OVER,
        ) and not hay_gif_game_over:
            for particula in particulas:
                particula.actualizar(dt)

        if combo_actual and pygame.time.get_ticks() > combo_expira:
            combo_actual = 0

    def registrar_truco(ahora):
        nonlocal combo_actual, combo_mejor_nivel, combo_expira
        if ahora > combo_expira:
            combo_actual = 0
        combo_actual += 1
        combo_mejor_nivel = max(combo_mejor_nivel, combo_actual)
        combo_expira = ahora + 2000

    while jugando:
        # Limita el avance tras una pausa del sistema; el acumulador hace
        # varios pasos pequeños si el render no alcanza los 60 FPS.
        dt = min(clock.tick(FPS) / 1000.0, 0.25)
        acumulador_fisica += dt
        tiempo = pygame.time.get_ticks() / 1000.0

        eventos_visuales.actualizar_flashback(
            nivel, estado, tiempo, ESTADO_JUGANDO
        )

        contexto_eventos = EstadoEventos(
            screen=screen,
            jugando=jugando,
            estado=estado,
            estado_despues_opciones=estado_despues_opciones,
            jugador=jugador,
            nivel=nivel,
            plataformas=plataformas,
            hue_fondo=hue_fondo,
            hue_jugador=hue_jugador,
            entidades=entidades,
            transicion=transicion,
            boton_reintentar=boton_reintentar,
            texto_boton=texto_boton,
            tamano_fuente=tamano_fuente,
            fuente_boton=fuente_boton,
            superficie_texto_boton=superficie_texto_boton,
            idioma_mostrado=idioma_mostrado,
        )
        procesar_eventos(
            pygame.event.get(), contexto_eventos, dependencias_eventos
        )
        screen = contexto_eventos.screen
        jugando = contexto_eventos.jugando
        estado = contexto_eventos.estado
        estado_despues_opciones = contexto_eventos.estado_despues_opciones
        jugador = contexto_eventos.jugador
        nivel = contexto_eventos.nivel
        plataformas = contexto_eventos.plataformas
        hue_fondo = contexto_eventos.hue_fondo
        hue_jugador = contexto_eventos.hue_jugador
        entidades = contexto_eventos.entidades
        transicion = contexto_eventos.transicion
        texto_boton = contexto_eventos.texto_boton
        tamano_fuente = contexto_eventos.tamano_fuente
        fuente_boton = contexto_eventos.fuente_boton
        superficie_texto_boton = contexto_eventos.superficie_texto_boton
        idioma_mostrado = contexto_eventos.idioma_mostrado

        if estado == ESTADO_MENU:
            menu.actualizar()

        while acumulador_fisica >= paso_fisica:
            actualizar_mundo(paso_fisica)
            acumulador_fisica -= paso_fisica

        if estado == ESTADO_JUGANDO and nivel == 30 and not despertar_mostrado:
            despertar_mostrado = True
            play_catarsis_animation(
                screen,
                clock,
                exit_text=texto(configuracion["idioma"], "exit"),
                button_renderer=menu,
            )

        eventos_visuales.actualizar_flashbacks_especiales(tiempo)

        # --- Renderizado ---
        if estado == ESTADO_ADVERTENCIA:
            lienzo.fill((8, 8, 12))
            if idioma_advertencia_mostrado != configuracion["idioma"]:
                idioma_advertencia_mostrado = configuracion["idioma"]
                textos_advertencia = (
                    (
                        font_advertencia_titulo.render(
                            texto(idioma_advertencia_mostrado, "epilepsy_warning_title"),
                            True,
                            (255, 210, 80),
                        ),
                        (WIDTH // 2, 190),
                    ),
                    (
                        font_advertencia.render(
                            texto(idioma_advertencia_mostrado, "epilepsy_warning_line_1"),
                            True,
                            (245, 245, 245),
                        ),
                        (WIDTH // 2, 275),
                    ),
                    (
                        font_advertencia.render(
                            texto(idioma_advertencia_mostrado, "epilepsy_warning_line_2"),
                            True,
                            (245, 245, 245),
                        ),
                        (WIDTH // 2, 315),
                    ),
                    (
                        font_advertencia_prompt.render(
                            texto(
                                idioma_advertencia_mostrado,
                                "epilepsy_warning_continue",
                            ),
                            True,
                            (180, 180, 190),
                        ),
                        (WIDTH // 2, 430),
                    ),
                )
            for superficie_texto, centro in textos_advertencia:
                lienzo.blit(
                    superficie_texto,
                    superficie_texto.get_rect(center=centro),
                )
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
            pausa.dibujar(lienzo, posicion_raton_logica, dt)
            screen.blit(pygame.transform.smoothscale(lienzo, screen.get_size()), (0, 0))
        elif estado == ESTADO_OPCIONES:
            opciones.dibujar(lienzo, dt=dt)
            screen.blit(pygame.transform.smoothscale(lienzo, screen.get_size()), (0, 0))
        else:
            # La escena se dibuja aparte para poder desaturarla como un todo
            # antes de mezclarla con el resto de la interfaz.
            hay_gif_game_over = (
                estado == ESTADO_GAME_OVER
                and (
                    bool(eventos_visuales.gif_game_over)
                    or eventos_visuales.game_over_nivel_alto_activo
                )
            )

            if not hay_gif_game_over:
                fotograma_flashback = (
                    eventos_visuales.obtener_fotograma_flashback(tiempo)
                )

                # El fondo abstracto es lo más pesado de dibujar; con las
                # optimizaciones de fondo.py ya es mucho más barato, pero
                # de todas formas no hace falta recalcularlo en cada
                # fotograma: sus formas se mueven lento y a 20 Hz (cada 3
                # fotogramas a 60 FPS) sigue viéndose fluido.
                if (
                    tiempo - tiempo_ultimo_fondo >= 1 / 20
                    or nivel != nivel_fondo
                ):
                    dibujar_fondo_segmentado(fondo_cache, tiempo, hue_fondo, WIDTH, HEIGHT, nivel)
                    nivel_fondo = nivel
                    tiempo_ultimo_fondo = tiempo
                if estado == ESTADO_TRANSICION:
                    # Los dos niveles se dibujan uno junto al otro y la cámara
                    # se desliza del viejo al nuevo siguiendo al personaje.
                    camara = int(round(transicion.desplazamiento_camara()))
                    dibujar_nivel(capa_nivel_nuevo, fondo_cache, plataformas, entidades, tiempo, nivel)
                    escena.blit(capa_nivel_anterior, (-camara, 0))
                    escena.blit(capa_nivel_nuevo, (WIDTH - camara, 0))

                    for particula in particulas:
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
                        particula.dibujar(escena, tiempo)

                    for plataforma in plataformas:
                        plataforma.dibujar(escena, tiempo, nivel)

                    for entidad in entidades:
                        entidad.dibujar(escena, tiempo)

                    jugador.dibujar(escena)

                # Los colores se van perdiendo a medida que suben los niveles;
                # durante la transición el cambio es gradual, al ritmo de la cámara.
                nivel_visual = nivel - 1 + transicion.progreso_camara() if estado == ESTADO_TRANSICION else nivel
                escala_grises(escena, saturacion_nivel(nivel_visual))
                if intensidad_shake > 0:
                    lienzo.fill((0, 0, 0))
                    offset = (
                        random.uniform(-intensidad_shake, intensidad_shake),
                        random.uniform(-intensidad_shake, intensidad_shake),
                    )
                    lienzo.blit(escena, offset)
                else:
                    lienzo.blit(escena, (0, 0))

                if alerta_enemigos > 0.02:
                    # Pulso suave para que la viñeta "respire" en vez de
                    # quedarse fija, como un latido que se acelera con el
                    # peligro (el propio halo del enemigo, en enemigo.py,
                    # ya pulsa más rápido cerca; esto lo refuerza en toda
                    # la pantalla).
                    pulso = 0.85 + 0.15 * math.sin(tiempo * (4.0 + 4.0 * alerta_enemigos))
                    vineta_peligro.set_alpha(int(255 * min(1.0, alerta_enemigos) * pulso))
                    lienzo.blit(vineta_peligro, (0, 0))

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

            clave_hud_combo = (
                configuracion["idioma"],
                combo_actual if tiempo * 1000 <= combo_expira else 0,
                jugador.dashes_disponibles > 0
                and jugador.dash_enfriamiento <= 0,
            )
            if clave_hud_combo != combo_hud_clave:
                combo_hud_clave = clave_hud_combo
                idioma_hud, combo_visible, dash_listo = clave_hud_combo
                lineas_hud = []
                if combo_visible > 0:
                    lineas_hud.append(
                        fuente_combo.render(
                            f"{texto(idioma_hud, 'combo')} x{combo_visible}",
                            True,
                            (255, 225, 100),
                        )
                    )
                lineas_hud.append(
                    fuente_combo.render(
                        f"{texto(idioma_hud, 'dash_control')} "
                        f"{texto(idioma_hud, 'ready') if dash_listo else '...'}",
                        True,
                        (130, 255, 190) if dash_listo else (165, 165, 175),
                    )
                )
                combo_hud_superficie = lineas_hud
            for indice, linea_hud in enumerate(combo_hud_superficie):
                rect_hud = linea_hud.get_rect(topright=(WIDTH - 14, 10 + indice * 26))
                lienzo.blit(linea_hud, rect_hud)

            if (
                estado == ESTADO_TRANSICION
                and pygame.time.get_ticks() <= resumen_expira
            ):
                clave_resumen = (
                    configuracion["idioma"],
                    nivel - 1,
                    resumen_combo,
                )
                if clave_resumen != resumen_clave:
                    resumen_clave = clave_resumen
                    idioma_resumen, nivel_resumen, combo_resumen = clave_resumen
                    resumen_superficies = (
                        fuente_resumen.render(
                            f"{texto(idioma_resumen, 'level_clear')} "
                            f"{nivel_resumen}",
                            True,
                            (255, 245, 205),
                        ),
                        fuente_combo.render(
                            f"{texto(idioma_resumen, 'best_combo')} "
                            f"x{combo_resumen}",
                            True,
                            (255, 215, 105),
                        ),
                    )
                for linea, y in zip(resumen_superficies, (58, 92)):
                    lienzo.blit(
                        linea,
                        linea.get_rect(center=(WIDTH // 2, y)),
                    )

            if estado == ESTADO_GAME_OVER:
                eventos_visuales.dibujar_game_over(
                    lienzo,
                    nivel,
                    pygame.time.get_ticks(),
                    tiempo,
                )

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

            eventos_visuales.dibujar_flashback_especial(
                lienzo,
                tiempo,
                configuracion["idioma"],
                font,
                font_advertencia_titulo,
                texto,
            )

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