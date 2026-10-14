"""Escena final: el personaje cruza un vacío negro antes del menú.

Estilo pixel art: toda la escena se dibuja en una resolución baja (cada
"píxel" mide PIXEL píxeles reales), con paleta reducida, bordes duros y
animaciones a pocos cuadros por segundo, y luego se amplía sin suavizado.

Vista lateral 2D: el personaje camina cansado hacia la derecha mientras
espirales blancas pasan en capas de parallax sobre un fondo totalmente negro.
Las espirales son la única fuente de luz del personaje.
"""

import math

import pygame

try:
    import numpy as np
except ImportError:  # sin numpy no se reduce la paleta, el resto funciona igual
    np = None


DURACION_ANIMACION = 8.0

# --- Estilo pixel art ----------------------------------------------------
PIXEL = 4                  # tamaño de cada píxel (más alto = más grueso)
NIVELES_COLOR = 6          # niveles por canal (menos = paleta más pobre)
FPS_PERSONAJE = 12         # cuadros por segundo de la animación del personaje
FPS_GIRO = 10              # cuadros por segundo del giro de las espirales

# --- Ajustes del personaje cansado -------------------------------------
VELOCIDAD_PASO = 4.2       # ritmo de pasos (más bajo = más lento)
AMPLITUD_PASO = 0.45       # zancada corta
INCLINACION = 5            # cuerpo encorvado hacia delante
OPACIDAD_GRIS = 120        # cuánto se "apaga" el color (0-255)
ESCALA_ALTURA = 0.46       # alto del personaje respecto al alto de la pantalla
POSICION_X = 0.36          # posición horizontal del personaje (fracción)
VELOCIDAD_FONDO = 70       # píxeles reales por segundo de la capa del personaje

# --- Integración con el entorno -----------------------------------------
LUZ_BASE = 105             # brillo del personaje sin ninguna espiral cerca
LUZ_MAXIMA = 115           # brillo extra cuando pasa junto a una espiral
INTENSIDAD_REFLEJO = 70    # opacidad del reflejo en el suelo (0 = sin reflejo)

# Capas de espirales (periodo y radio en píxeles reales, grosor en píxeles
# pixel-art): (parallax, periodo, radio, brillo, grosor, giro,
#              y_minimo, y_rango, con_resplandor)
CAPA_LEJANA = (0.25, 260, 38, 70, 1, 0.20, 0.18, 0.55, False)
CAPA_MEDIA = (0.50, 380, 70, 135, 1, -0.30, 0.15, 0.55, True)
CAPA_CERCANA = (1.00, 640, 105, 215, 1, 0.45, 0.20, 0.45, True)
CAPA_PRIMER_PLANO = (1.60, 1000, 200, 38, 3, -0.25, 0.10, 0.65, False)

_cache = {}


def _cacheado(clave, crear):
    if clave not in _cache:
        if len(_cache) > 40:
            _cache.clear()
        _cache[clave] = crear()
    return _cache[clave]


# ----------------------------------------------------------------------
# Utilidades de dibujo (todo ocurre en la superficie de baja resolución)
# ----------------------------------------------------------------------
def _resplandor(radio, color):
    """Círculo de luz en anillos escalonados (alfa decreciente)."""

    def crear():
        superficie = pygame.Surface((radio * 2, radio * 2), pygame.SRCALPHA)
        for r in range(radio, 0, -2):
            alfa = int(70 * (1 - r / radio) ** 2)
            pygame.draw.circle(superficie, (*color, alfa), (radio, radio), r)
        return superficie

    return _cacheado(("glow", radio, color), crear)


def _viñeta(ancho, alto):
    def crear():
        superficie = pygame.Surface((ancho, alto), pygame.SRCALPHA)
        pasos = 14
        grosor = max(1, ancho // (pasos * 2))
        for i in range(pasos):
            alfa = int(150 * (1 - i / pasos) ** 2)
            rect = pygame.Rect(0, 0, ancho, alto).inflate(
                -i * ancho // (pasos * 2), -i * alto // (pasos * 2)
            )
            pygame.draw.rect(superficie, (0, 0, 0, alfa), rect, grosor)
        return superficie

    return _cacheado(("vig", ancho, alto), crear)


def _degradado_alfa(ancho, alto, alfa_arriba):
    """Máscara que va de alfa_arriba a 0 de arriba abajo (para el reflejo)."""

    def crear():
        superficie = pygame.Surface((ancho, max(1, alto)), pygame.SRCALPHA)
        for y in range(max(1, alto)):
            t = y / max(1, alto - 1)
            alfa = int(alfa_arriba * (1 - t) ** 1.6)
            pygame.draw.line(superficie, (255, 255, 255, alfa), (0, y), (ancho, y))
        return superficie

    return _cacheado(("grad", ancho, alto, alfa_arriba), crear)


def _dibujar_espiral(superficie, centro, radio, brillo, grosor, angulo0):
    vueltas = 3
    pasos = 60
    puntos = []
    for indice in range(pasos + 1):
        angulo = angulo0 + indice * math.tau * vueltas / pasos
        distancia = radio * indice / pasos
        puntos.append(
            (
                int(centro[0] + math.cos(angulo) * distancia),
                int(centro[1] + math.sin(angulo) * distancia),
            )
        )
    brillo = max(0, min(255, int(brillo)))
    pygame.draw.lines(
        superficie, (brillo, brillo, brillo), False, puntos, max(1, grosor)
    )


def _posterizar(superficie, niveles):
    """Reduce la paleta a unos pocos niveles por canal (look pixel art)."""
    if np is None or niveles < 2:
        return
    datos = pygame.surfarray.pixels3d(superficie)
    cuantizado = (datos.astype(np.uint16) * (niveles - 1) + 127) // 255
    datos[:] = (cuantizado * 255 // (niveles - 1)).astype(np.uint8)
    del datos  # libera el bloqueo de la superficie


# ----------------------------------------------------------------------
# Espirales con parallax
# ----------------------------------------------------------------------
def _espirales(capa, tiempo, ancho, alto):
    """Genera (cx, cy, radio, numero) de las espirales visibles de una capa."""
    paralaje = capa[0]
    periodo = capa[1] / PIXEL
    radio_base = capa[2] / PIXEL
    y_min, y_rango = capa[6], capa[7]
    desplazamiento = tiempo * VELOCIDAD_FONDO / PIXEL * paralaje
    primero = int(desplazamiento // periodo)
    x = -(desplazamiento % periodo) - periodo
    indice = 0
    while x < ancho + periodo:
        numero = primero + indice - 1
        cx = x + periodo * 0.5
        cy = alto * (y_min + y_rango * ((numero * 0.618033) % 1.0))
        radio = radio_base * (0.75 + 0.5 * ((numero * 0.37) % 1.0))
        yield cx, cy, radio, numero
        x += periodo
        indice += 1


def _dibujar_capa(superficie, capa, tiempo, tiempo_giro, progreso):
    ancho, alto = superficie.get_size()
    brillo_base, grosor, giro, con_glow = capa[3], capa[4], capa[5], capa[8]
    for cx, cy, radio, numero in _espirales(capa, tiempo, ancho, alto):
        pulso = 0.8 + 0.2 * math.sin(tiempo * 1.6 + numero)
        brillo = brillo_base * pulso * (0.85 + 0.15 * progreso)
        sentido = 1 if numero % 2 == 0 else -1
        angulo0 = tiempo_giro * giro * sentido + numero
        if con_glow:
            r_glow = max(8, int(radio * 1.8) // 4 * 4)
            glow = _resplandor(r_glow, (255, 255, 255)).copy()
            glow.set_alpha(int(255 * pulso * brillo_base / 215))
            superficie.blit(glow, (int(cx) - r_glow, int(cy) - r_glow))
        _dibujar_espiral(superficie, (cx, cy), radio, brillo, grosor, angulo0)


def _dibujar_fondo(superficie, tiempo, tiempo_giro):
    """Vacío negro con espirales blancas (lejanas, medias y cercanas)."""
    superficie.fill((0, 0, 0))
    progreso = min(1.0, max(0.0, tiempo / DURACION_ANIMACION))
    for capa in (CAPA_LEJANA, CAPA_MEDIA, CAPA_CERCANA):
        _dibujar_capa(superficie, capa, tiempo, tiempo_giro, progreso)


def _dibujar_primer_plano(superficie, tiempo, tiempo_giro):
    """Espirales enormes y apagadas que pasan por delante del personaje."""
    progreso = min(1.0, max(0.0, tiempo / DURACION_ANIMACION))
    _dibujar_capa(superficie, CAPA_PRIMER_PLANO, tiempo, tiempo_giro, progreso)


def _luz_en(x, tiempo, ancho, alto):
    """Cuánta luz de espirales llega a la posición x (0..1)."""
    luz = 0.0
    for capa in (CAPA_MEDIA, CAPA_CERCANA):
        for cx, _cy, radio, numero in _espirales(capa, tiempo, ancho, alto):
            pulso = 0.8 + 0.2 * math.sin(tiempo * 1.6 + numero)
            cercania = max(0.0, 1 - abs(cx - x) / (radio * 3.2))
            luz += cercania ** 2 * (capa[3] / 215) * pulso
    return min(1.0, luz)


# ----------------------------------------------------------------------
# Personaje
# ----------------------------------------------------------------------
def _preparar_personaje(personaje, tiempo):
    # Ritmo irregular: arrastra los pies y casi se detiene a ratos
    fase = tiempo * VELOCIDAD_PASO + 0.9 * math.sin(tiempo * 1.1)

    personaje.rect.height = personaje.altura_normal
    personaje._plataformas = ()
    personaje.particulas = []
    personaje.rastro = []
    personaje.tiempo_animacion = fase
    personaje.amplitud_paso = AMPLITUD_PASO
    personaje.balanceo_actual = math.sin(fase) * 2.5
    personaje.bob_actual = abs(math.sin(fase)) * 1.2
    # Cabeza caída, con un cabeceo lento
    personaje.bob_cabeza_actual = 0.8 + 0.2 * math.sin(fase * 0.5)
    personaje.inclinacion_actual = INCLINACION + 1.5 * math.sin(fase * 0.5)
    personaje.pose_aire = 0.0
    personaje.en_suelo = True
    personaje.vel_y = 0
    personaje.vel_x = personaje.velocidad * 0.4
    personaje.direccion = 1
    personaje.agachado = False
    personaje.agachado_animacion = 0.0
    personaje.escala_y = 0.96  # ligeramente encorvado
    personaje.muriendo = False
    personaje.girando = False
    personaje.dash_restante = 0


def _apagar_color(lienzo, luz):
    """Desatura el personaje y lo ilumina según la luz de las espirales."""
    mascara = pygame.mask.from_surface(lienzo)
    gris = mascara.to_surface(
        setcolor=(95, 95, 105, OPACIDAD_GRIS), unsetcolor=(0, 0, 0, 0)
    )
    lienzo.blit(gris, (0, 0))
    v = int(LUZ_BASE + LUZ_MAXIMA * luz)
    lienzo.fill((v, v, min(255, v + 10), 255), special_flags=pygame.BLEND_RGBA_MULT)


def _endurecer_bordes(figura):
    """Quita el suavizado: cada píxel es opaco o transparente."""
    mascara = pygame.mask.from_surface(figura, 110)
    duro = mascara.to_surface(setsurface=figura, unsetcolor=(0, 0, 0, 0))
    return duro, mascara


def _luz_de_borde(figura, mascara, luz):
    """Contorno de 1 píxel que se enciende cerca de una espiral."""
    if luz < 0.15:
        return
    nivel = int(110 + 145 * luz)
    for punto in mascara.outline():
        figura.set_at(punto, (nivel, nivel, nivel, 255))


def _dibujar_sudor(superficie, tiempo, cabeza, escala):
    for i in range(3):
        ciclo = (tiempo * 0.9 + i * 0.33) % 1.0
        x = int(cabeza[0] + (10 + i * 4) * escala + math.sin(i * 2.0) * 2)
        y = int(cabeza[1] + ciclo * 38 * escala)
        tono = 1 - ciclo
        color = (int(150 * tono), int(170 * tono), int(190 * tono))
        pygame.draw.rect(superficie, color, (x, y, 1, 2))


def _dibujar_aliento(superficie, tiempo, boca, escala):
    """Pequeñas nubes de vaho cuadradas por el jadeo."""
    ciclo = (tiempo * 0.7) % 1.0
    for i in range(3):
        t = (ciclo + i * 0.25) % 1.0
        lado = 2 + int(t * 4)
        puff = pygame.Surface((lado, lado), pygame.SRCALPHA)
        puff.fill((170, 170, 185, int(90 * (1 - t))))
        superficie.blit(
            puff, (int(boca[0] + t * 34 * escala), int(boca[1] - t * 12 * escala))
        )


def _dibujar_suelo_invisible(superficie, figura, rect, centro_x, pie_y, escala, luz):
    """Da peso al personaje: resplandor bajo los pies y reflejo en el suelo."""
    ancho_luz, alto_luz = max(4, int(300 * escala)), max(2, int(46 * escala))
    charco = pygame.transform.scale(
        _resplandor(30, (255, 255, 255)), (ancho_luz, alto_luz)
    )
    charco.set_alpha(int(70 + 150 * luz))
    superficie.blit(charco, charco.get_rect(center=(centro_x, pie_y)))

    if INTENSIDAD_REFLEJO <= 0:
        return

    alto_fig = figura.get_height()
    y0 = alto_fig - int(150 * escala)  # fila del espejo en la figura volteada
    zona = pygame.Rect(0, y0, figura.get_width(), alto_fig - y0)
    if zona.height <= 0:
        return
    reflejo = pygame.transform.flip(figura, False, True)
    recorte = reflejo.subsurface(zona).copy()
    recorte.blit(
        _degradado_alfa(zona.width, zona.height, INTENSIDAD_REFLEJO),
        (0, 0),
        special_flags=pygame.BLEND_RGBA_MULT,
    )
    superficie.blit(recorte, (rect.left, pie_y))


def dibujar(superficie, personaje, tiempo):
    """Dibuja al personaje cansado caminando de lado por el vacío negro."""
    ancho_real, alto_real = superficie.get_size()
    ancho = -(-ancho_real // PIXEL)   # resolución baja (redondeo hacia arriba)
    alto = -(-alto_real // PIXEL)
    pantalla = pygame.Surface((ancho, alto))

    # Animaciones a pocos cuadros por segundo: sensación de sprite animado
    t_personaje = math.floor(tiempo * FPS_PERSONAJE) / FPS_PERSONAJE
    t_giro = math.floor(tiempo * FPS_GIRO) / FPS_GIRO

    suelo_y = int(alto * 0.74)
    _dibujar_fondo(pantalla, tiempo, t_giro)

    centro_x = int(ancho * POSICION_X)
    luz = _luz_en(centro_x, tiempo, ancho, alto)

    lienzo = pygame.Surface((140, 180), pygame.SRCALPHA)
    _preparar_personaje(personaje, t_personaje)
    personaje.rect.centerx = lienzo.get_width() // 2
    personaje.rect.bottom = 150
    personaje.dibujar(lienzo)
    _apagar_color(lienzo, luz)

    escala = alto * ESCALA_ALTURA / lienzo.get_height()
    figura = pygame.transform.smoothscale(
        lienzo,
        (
            max(1, int(lienzo.get_width() * escala)),
            max(1, int(lienzo.get_height() * escala)),
        ),
    )
    figura, mascara = _endurecer_bordes(figura)
    _luz_de_borde(figura, mascara, luz)

    pie_y = suelo_y + int(alto * 0.07)
    rect = figura.get_rect()
    rect.centerx = centro_x
    rect.top = pie_y - int(150 * escala)  # los pies están en y=150 del lienzo

    _dibujar_suelo_invisible(pantalla, figura, rect, centro_x, pie_y, escala, luz)

    # Sombra de contacto bajo los pies
    sombra = pygame.Surface((max(4, int(90 * escala)), max(2, int(14 * escala))), pygame.SRCALPHA)
    pygame.draw.ellipse(sombra, (0, 0, 0, 170), sombra.get_rect())
    pantalla.blit(sombra, sombra.get_rect(center=(centro_x, pie_y)))

    pantalla.blit(figura, rect)

    # Detalles de cansancio (cabeza aprox. en el tercio superior del lienzo)
    cabeza = (centro_x, rect.top + int(32 * escala))
    _dibujar_sudor(pantalla, t_personaje, cabeza, escala)
    _dibujar_aliento(
        pantalla, t_personaje,
        (centro_x + int(14 * escala), cabeza[1] + int(10 * escala)), escala,
    )

    _dibujar_primer_plano(pantalla, tiempo, t_giro)

    # Viñeta y fundido de entrada
    pantalla.blit(_viñeta(ancho, alto), (0, 0))
    if tiempo < 0.8:
        velo = pygame.Surface((ancho, alto))
        velo.set_alpha(int(255 * (1 - tiempo / 0.8)))
        pantalla.blit(velo, (0, 0))

    # Paleta reducida y ampliación sin suavizado: píxeles grandes y nítidos
    _posterizar(pantalla, NIVELES_COLOR)
    ampliada = pygame.transform.scale(pantalla, (ancho * PIXEL, alto * PIXEL))
    superficie.blit(ampliada, (0, 0))