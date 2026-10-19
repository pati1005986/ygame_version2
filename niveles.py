"""Generación de niveles y utilidades relacionadas con el jugador."""

import random

from constantes import (
    HEIGHT,
    MARGEN_SALTO_SEGURO,
    NIVEL_DESPERTAR,
    NIVEL_SALTOS_LARGOS,
    NIVEL_TRAMPAS,
    POS_SPAWN,
    WIDTH,
)
from dificultad import parametros_dificultad, parametros_dificultad_infinito
from enemigo import generar_entidades
from personaje import PersonajeHumanoide
from plataformas import Plataforma, color_desde_hue

Y_MINIMA = 70
Y_MAXIMA = HEIGHT - 50


def _parametros(nivel, modo_infinito):
    if modo_infinito:
        return parametros_dificultad_infinito(nivel)
    return parametros_dificultad(nivel)


def _hay_peligros(nivel, modo_infinito):
    """Enemigos y trampas existen hasta el nivel 30 (siempre en modo infinito)."""
    return modo_infinito or nivel < NIVEL_DESPERTAR


def _limitar_y(y):
    return max(Y_MINIMA, min(Y_MAXIMA, y))


def _diseno_por_nivel(nivel):
    """Devuelve (cantidad de plataformas, rango de distancia X, rango de desnivel Y)."""
    if nivel >= NIVEL_SALTOS_LARGOS:
        return random.randint(5, 7), (95, 165), (-150, 150)
    if nivel >= NIVEL_TRAMPAS:
        return random.randint(8, 12), (35, 90), (-125, 110)
    return random.randint(7, 10), (25, 70), (-85, 75)


def _siguiente_y(top_guia, desnivel, altura_alcanzable):
    """Elige una altura que el jugador pueda alcanzar desde la plataforma guía."""
    while True:
        y = _limitar_y(top_guia + random.randint(*desnivel))
        if top_guia - y <= altura_alcanzable:
            return y


def _crear_plataforma_opcional(x, y, nivel, modo_infinito, prob_movil):
    """Ruta lateral opcional; en niveles medios puede ser un camino falso."""
    x_opcional = x + random.randint(-35, 35)
    y_opcional = _limitar_y(y + random.randint(-145, 145))
    ancho = random.randint(45, 95)
    falso = nivel < NIVEL_SALTOS_LARGOS and random.random() < 0.30
    hue = random.random()
    es_trampa = _hay_peligros(nivel, modo_infinito) and (
        falso or random.random() < 0.20
    )
    return Plataforma(
        x_opcional, y_opcional, ancho, 20, hue, es_trampa,
        probabilidad_movimiento=prob_movil,
    )


def _crear_plataformas(nivel, modo_infinito, parametros):
    prob_movil = parametros["probabilidad_plataforma_movil"]
    plataformas = [
        Plataforma(50, 300, 150, 20, random.random(), probabilidad_movimiento=prob_movil)
    ]
    guia = plataformas[0].rect

    cantidad, distancia_x, desnivel = _diseno_por_nivel(nivel)
    altura_alcanzable = max(
        0,
        PersonajeHumanoide.altura_maxima_salto(parametros["gravedad_jugador"])
        - MARGEN_SALTO_SEGURO,
    )

    for indice in range(cantidad):
        ancho = random.randint(50, 115) if nivel >= NIVEL_TRAMPAS else random.randint(65, 135)
        x = guia.right + random.randint(*distancia_x)
        y = _siguiente_y(guia.top, desnivel, altura_alcanzable)
        es_trampa = (
            nivel >= NIVEL_TRAMPAS
            and _hay_peligros(nivel, modo_infinito)
            and random.random() < 0.28
        )
        nueva = Plataforma(
            x, y, ancho, 20, random.random(), es_trampa,
            probabilidad_movimiento=prob_movil,
        )
        plataformas.append(nueva)
        guia = nueva.rect

        # Las rutas opcionales no reemplazan la ruta principal.
        if nivel >= NIVEL_TRAMPAS and indice % 2 == 1 and random.random() < 0.65:
            plataformas.append(
                _crear_plataforma_opcional(x, y, nivel, modo_infinito, prob_movil)
            )
    return plataformas


def generar_nivel(nivel, modo_infinito=False):
    """Crea un nivel y devuelve sus plataformas y colores base.

    Args:
        nivel: Número del nivel actual.
        modo_infinito: Activa la curva infinita y conserva enemigos/trampas
            después del nivel 30, sin cambiar la curva de historia.

    Returns:
        Una tupla ``(plataformas, hue_fondo, hue_jugador, entidades)``.
    """
    parametros = _parametros(nivel, modo_infinito)
    plataformas = _crear_plataformas(nivel, modo_infinito, parametros)

    hue_fondo = random.random()
    hue_jugador = random.random()
    entidades = (
        generar_entidades(
            nivel,
            plataformas,
            POS_SPAWN,
            velocidad_patrulla=parametros["velocidad_enemigo_patrulla"],
            velocidad_persecucion=parametros["velocidad_enemigo_persecucion"],
            rango_deteccion=parametros["rango_deteccion_enemigo"],
            ancho_pantalla=WIDTH,
            alto_pantalla=HEIGHT,
            cantidad_maxima=6 if modo_infinito else 4,
        )
        if _hay_peligros(nivel, modo_infinito)
        else []
    )
    return plataformas, hue_fondo, hue_jugador, entidades


def crear_jugador(hue_jugador, volumen_efectos):
    """Crea al personaje en el punto de aparición."""
    jugador = PersonajeHumanoide(
        *POS_SPAWN,
        color_desde_hue(hue_jugador),
        volumen_efectos,
        dash_habilitado=True,
    )
    jugador.rect.center = POS_SPAWN
    return jugador


def ajustar_dificultad_jugador(jugador, nivel, modo_infinito=False):
    """Aumenta el ritmo sin hacer que los primeros niveles sean bruscos."""
    parametros = _parametros(nivel, modo_infinito)
    jugador.velocidad = parametros["velocidad_jugador"]
    jugador.gravedad = parametros["gravedad_jugador"]
    jugador.aplicar_agarre(parametros)  # sin claves de agarre = valores por defecto
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