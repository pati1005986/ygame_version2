"""Escena final: el personaje cruza un vacío negro, se desintegra y despierta.

Estilo pixel art: toda la escena se dibuja en una resolución baja (cada
"píxel" mide PIXEL píxeles reales), con paleta reducida, bordes duros y
animaciones a pocos cuadros por segundo, y luego se amplía sin suavizado.

Línea de tiempo:
  1. El personaje camina cansado hacia la derecha entre espirales (parallax).
  2. Poco a poco el mundo se frena y el personaje se desintegra píxel a píxel
     en motas de polvo que flotan hacia arriba.
  3. El polvo se reúne y forma la silueta de un hombre tumbado.
  4. La silueta despierta: respira, intenta incorporarse, se deja caer, y al
     final se sienta, se frota la cara y abre los ojos. Sale un resplandor
     de amanecer a su espalda.
"""

import math

import pygame

try:
    import numpy as np
except ImportError:  # sin numpy no hay paleta reducida ni polvo (solo fundido)
    np = None


DURACION_ANIMACION = 14.5

# --- Línea de tiempo (segundos) ------------------------------------------
INICIO_DESINTEGRA = 3.2     # empieza a desintegrarse el personaje
DURACION_DESINTEGRA = 3.4   # tiempo en que se pierden todos sus píxeles
INICIO_SILUETA = 6.4        # el polvo empieza a formar la silueta
DURACION_SILUETA = 2.4      # tiempo en que se completa la silueta
INICIO_DESPERTAR = 8.8      # empieza a moverse
DURACION_DESPERTAR = 5.0    # hasta quedar sentado con los ojos abiertos
FRENADO_INICIO = 3.0        # el mundo empieza a frenarse
FRENADO_DURACION = 3.2
FRENADO_FUERZA = 0.85       # 0 = no frena, 1 = se detiene del todo
VIDA_PARTICULA = 1.2        # segundos que vive cada mota de polvo

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
POSICION_SILUETA = 0.50    # posición horizontal de la cadera de la silueta
VELOCIDAD_FONDO = 70       # píxeles reales por segundo de la capa del personaje

# --- Integración con el entorno -----------------------------------------
LUZ_BASE = 105             # brillo del personaje sin ninguna espiral cerca
LUZ_MAXIMA = 115           # brillo extra cuando pasa junto a una espiral
INTENSIDAD_REFLEJO = 70    # opacidad del reflejo en el suelo (0 = sin reflejo)

# --- Silueta ---------------------------------------------------------------
ANGULO_SENTADO = 1.35      # inclinación del torso al sentarse (rad, 1.57 = recto)

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


def _suave(x):
    """Suavizado 0..1 (smoothstep) con recorte."""
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _tiempo_fondo(t):
    """Tiempo "del mundo": avanza normal y se frena mientras el personaje se apaga."""
    a, b, k = FRENADO_INICIO, FRENADO_DURACION, FRENADO_FUERZA
    if t <= a:
        return t
    x = min(1.0, (t - a) / b)
    integral = b * (x ** 3 - x ** 4 / 2) + max(0.0, t - a - b)
    return t - k * integral


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
    """Espirales enormes y apagadas que pasan por delante de la escena."""
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
# Desintegración / materialización píxel a píxel
# ----------------------------------------------------------------------
def _campos(ancho, alto, semilla):
    """Umbral de desintegración y velocidad de cada píxel (fijos por figura).

    Los píxeles de la izquierda y de arriba se sueltan antes, con algo de azar,
    como ceniza arrastrada por el viento.
    """

    def crear():
        rng = np.random.RandomState(semilla)
        ruido = rng.random_sample((ancho, alto))
        xs = np.linspace(0.0, 1.0, ancho)[:, None]
        ys = np.linspace(0.0, 1.0, alto)[None, :]
        umbral = 0.5 * ruido + 0.5 * (0.7 * xs + 0.3 * ys)
        umbral = (umbral - umbral.min()) / max(1e-6, umbral.max() - umbral.min())
        vx = 5 + 14 * rng.random_sample((ancho, alto))
        vy = -(3 + 12 * rng.random_sample((ancho, alto)))
        return umbral, vx, vy

    return _cacheado(("campos", ancho, alto, semilla), crear)


def _disolver(figura, tiempo_rel, duracion, aparecer, semilla):
    """Quita (o devuelve) píxeles de `figura`, modificando su alfa en sitio.

    Devuelve las motas de polvo (px, py, color) relativas a la figura, o None.
    - aparecer=False: los píxeles se sueltan y flotan hacia arriba/derecha.
    - aparecer=True: las motas caen desde arriba/izquierda y se posan.
    """
    if np is None:
        k = _suave(tiempo_rel / duracion)
        figura.set_alpha(int(255 * (k if aparecer else 1 - k)))
        return None

    ancho, alto = figura.get_size()
    umbral, vx, vy = _campos(ancho, alto, semilla)
    if aparecer:
        vy = -vy
    colores = pygame.surfarray.array3d(figura)
    alfa = pygame.surfarray.pixels_alpha(figura)
    original = alfa > 0
    d = tiempo_rel - umbral * duracion  # >= 0: el píxel ya se soltó (o llegó)
    if aparecer:
        solido = d >= 0
        flota = (d < 0) & (d > -VIDA_PARTICULA)
    else:
        solido = d < 0
        flota = (d >= 0) & (d < VIDA_PARTICULA)
    nuevo = alfa * solido
    alfa[:] = nuevo
    del alfa  # libera el bloqueo de la superficie

    xs, ys = np.nonzero(flota & original)
    if xs.size == 0:
        return None
    dd = d[xs, ys]
    px = xs + (vx[xs, ys] * dd).astype(np.int32)
    py = ys + (vy[xs, ys] * dd).astype(np.int32)
    brillo = 1.0 - np.abs(dd) / VIDA_PARTICULA
    color = (colores[xs, ys].astype(np.float32) * 0.5 + 120.0) * brillo[:, None]
    return px, py, np.clip(color, 0, 255).astype(np.uint8)


def _dibujar_particulas(pantalla, particulas, origen):
    """Pinta las motas de polvo (1 píxel cada una, con luz máxima)."""
    if particulas is None or np is None:
        return
    px, py, color = particulas
    px = px + origen[0]
    py = py + origen[1]
    ancho, alto = pantalla.get_size()
    ok = (px >= 0) & (px < ancho) & (py >= 0) & (py < alto)
    if not ok.any():
        return
    px, py, color = px[ok], py[ok], color[ok]
    datos = pygame.surfarray.pixels3d(pantalla)
    datos[px, py] = np.maximum(datos[px, py], color)
    del datos


# ----------------------------------------------------------------------
# Personaje
# ----------------------------------------------------------------------
def _preparar_personaje(personaje, tiempo, fatiga):
    # Ritmo irregular: arrastra los pies y casi se detiene a ratos
    fase = tiempo * VELOCIDAD_PASO + 0.9 * math.sin(tiempo * 1.1)

    personaje.rect.height = personaje.altura_normal
    personaje._plataformas = ()
    personaje.particulas = []
    personaje.rastro = []
    personaje.tiempo_animacion = fase
    personaje.amplitud_paso = AMPLITUD_PASO * (1 - 0.45 * fatiga)
    personaje.balanceo_actual = math.sin(fase) * 2.5
    personaje.bob_actual = abs(math.sin(fase)) * 1.2
    # Cabeza caída, con un cabeceo lento
    personaje.bob_cabeza_actual = 0.8 + 0.2 * math.sin(fase * 0.5)
    personaje.inclinacion_actual = (
        INCLINACION + 3 * fatiga + 1.5 * math.sin(fase * 0.5)
    )
    personaje.pose_aire = 0.0
    personaje.en_suelo = True
    personaje.vel_y = 0
    personaje.vel_x = personaje.velocidad * 0.4
    personaje.direccion = 1
    personaje.agachado = False
    personaje.agachado_animacion = 0.0
    personaje.escala_y = 0.96 - 0.04 * fatiga  # cada vez más encorvado
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


def _charco_de_luz(superficie, centro_x, pie_y, escala, luz, intensidad=1.0):
    """Resplandor bajo los pies: da peso a lo que pisa el suelo invisible."""
    ancho_luz, alto_luz = max(4, int(300 * escala)), max(2, int(46 * escala))
    charco = pygame.transform.scale(
        _resplandor(30, (255, 255, 255)), (ancho_luz, alto_luz)
    )
    charco.set_alpha(int((70 + 150 * luz) * max(0.0, intensidad)))
    superficie.blit(charco, charco.get_rect(center=(centro_x, pie_y)))


def _dibujar_suelo_invisible(
    superficie, figura, rect, centro_x, pie_y, escala, luz, intensidad=1.0
):
    """Resplandor bajo los pies y reflejo del personaje en el suelo."""
    _charco_de_luz(superficie, centro_x, pie_y, escala, luz, intensidad)

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


def _escena_personaje(pantalla, personaje, tiempo, t_personaje, tiempo_mundo, pie_y):
    """El personaje camina cansado y luego se desintegra."""
    rel = tiempo - INICIO_DESINTEGRA
    if rel > DURACION_DESINTEGRA + VIDA_PARTICULA:
        return  # ya no queda nada de él

    ancho, alto = pantalla.get_size()
    centro_x = int(ancho * POSICION_X)
    luz = _luz_en(centro_x, tiempo_mundo, ancho, alto)
    fatiga = min(1.0, tiempo / INICIO_DESINTEGRA)

    lienzo = pygame.Surface((140, 180), pygame.SRCALPHA)
    _preparar_personaje(personaje, t_personaje, fatiga)
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

    rect = figura.get_rect()
    rect.centerx = centro_x
    rect.top = pie_y - int(150 * escala)  # los pies están en y=150 del lienzo

    # Desintegración: la figura pierde píxeles y estos se convierten en polvo
    particulas = None
    if rel >= 0:
        particulas = _disolver(figura, rel, DURACION_DESINTEGRA, False, 11)
    vivo = 1.0 - _suave(rel / (DURACION_DESINTEGRA + 0.5))

    _dibujar_suelo_invisible(
        pantalla, figura, rect, centro_x, pie_y, escala, luz, vivo
    )

    # Sombra de contacto bajo los pies
    sombra = pygame.Surface(
        (max(4, int(90 * escala)), max(2, int(14 * escala))), pygame.SRCALPHA
    )
    pygame.draw.ellipse(sombra, (0, 0, 0, int(170 * vivo)), sombra.get_rect())
    pantalla.blit(sombra, sombra.get_rect(center=(centro_x, pie_y)))

    pantalla.blit(figura, rect)
    _dibujar_particulas(pantalla, particulas, rect.topleft)

    # Detalles de cansancio (cabeza aprox. en el tercio superior del lienzo)
    if tiempo < INICIO_DESINTEGRA:
        cabeza = (centro_x, rect.top + int(32 * escala))
        _dibujar_sudor(pantalla, t_personaje, cabeza, escala)
        _dibujar_aliento(
            pantalla, t_personaje,
            (centro_x + int(14 * escala), cabeza[1] + int(10 * escala)), escala,
        )


# ----------------------------------------------------------------------
# Silueta de un hombre despertando
# ----------------------------------------------------------------------
def _elevacion(t):
    """Cuánto se ha incorporado (0 tumbado, 1 sentado) según el progreso t."""
    t = max(0.0, min(1.0, t))
    if t < 0.16:                       # respira dormido
        return 0.0
    if t < 0.34:                       # primer intento: se alza un poco...
        return 0.20 * math.sin((t - 0.16) / 0.18 * math.pi)
    if t < 0.46:                       # ...y se deja caer
        return 0.0
    x = (t - 0.46) / 0.54              # se incorpora de verdad
    return _suave(x) + 0.05 * math.sin(x * math.pi)


def _punto(origen, angulo, largo):
    """Punto a `largo` de `origen` en la dirección `angulo` (y hacia arriba)."""
    return origen[0] + math.cos(angulo) * largo, origen[1] - math.sin(angulo) * largo


def _r(p):
    return int(round(p[0])), int(round(p[1]))


def _linea(superficie, color, a, b, grosor):
    pygame.draw.line(superficie, color, _r(a), _r(b), grosor)


def _silueta(alto, t, tiempo, luz, alba):
    """Hombre visto de lado: t=0 tumbado boca arriba, t=1 sentado.

    Devuelve (superficie, (x_cadera, y_suelo)) en coordenadas de la superficie.
    Se ve oscuro con un contorno claro (luz de borde), como una silueta.
    """
    ancho_s, alto_s = int(alto * 0.95), int(alto * 0.52)
    s = pygame.Surface((ancho_s, alto_s), pygame.SRCALPHA)
    suelo = alto_s - 2

    grosor_torso = max(3, int(alto * 0.05))
    grosor_miembro = max(2, int(alto * 0.028))
    radio_cabeza = max(3, int(alto * 0.036))
    largo_torso, largo_muslo, largo_pierna = alto * 0.15, alto * 0.10, alto * 0.10
    largo_brazo, largo_antebrazo = alto * 0.07, alto * 0.07

    cadera = (int(ancho_s * 0.40), suelo - grosor_torso // 2 - 1)
    e = _elevacion(t)
    ec = max(0.0, min(1.0, e))
    respiracion = 0.03 * math.sin(tiempo * 2.4) * (1 - ec)
    a = math.pi - (math.pi - ANGULO_SENTADO) * e + respiracion
    hombro = _punto(cadera, a, largo_torso)

    v = int(70 + 50 * luz + 25 * alba)
    claro = (v, v + 3, v + 14, 255)
    oscuro = (max(0, v - 28), max(0, v - 25), max(0, v - 12), 255)
    limite_pie = suelo - grosor_miembro // 2 - 1

    # Piernas extendidas hacia la derecha; las rodillas se flexionan al incorporarse
    flex = math.sin(ec * math.pi)
    muslo_a = 0.06 + 0.32 * flex + 0.12 * ec
    pierna_a = -(0.05 + 0.18 * flex + 0.12 * ec)

    def pierna(extra, color):
        rodilla = _punto(cadera, muslo_a + extra, largo_muslo)
        pie = _punto(rodilla, pierna_a + extra, largo_pierna)
        pie = (pie[0], min(pie[1], limite_pie))
        _linea(s, color, cadera, rodilla, grosor_miembro)
        _linea(s, color, rodilla, pie, grosor_miembro)

    # Brazo de apoyo: tumbado junto al cuerpo, luego se apoya hacia atrás
    u1 = -2.3 * ec
    f1 = -0.12 - 1.5 * ec
    codo = _punto(hombro, u1, largo_brazo)
    mano = _punto(codo, f1, largo_antebrazo)

    # Brazo que se frota la cara al final
    g = _suave((t - 0.72) / 0.2)
    u2 = u1 * (1 - g) + 0.55 * g
    f2 = f1 * (1 - g) + (1.75 + 0.18 * math.sin(tiempo * 14)) * g
    codo2 = _punto(hombro, u2, largo_brazo)
    mano2 = _punto(codo2, f2, largo_antebrazo)

    pierna(0.07, oscuro)
    _linea(s, oscuro, hombro, codo, grosor_miembro)
    _linea(s, oscuro, codo, mano, grosor_miembro)
    _linea(s, claro, cadera, hombro, grosor_torso)
    pygame.draw.circle(s, claro, _r(cadera), grosor_torso // 2 + 1)
    pierna(0.0, claro)

    # Cabeza: algo caída hacia delante al sentarse, apoyada en el suelo al tumbarse
    ah = a - 0.22 * ec
    centro = _punto(hombro, ah, radio_cabeza + 1)
    centro = (centro[0], centro[1] - max(0, radio_cabeza - grosor_torso // 2 - 1) * (1 - ec))
    pygame.draw.circle(s, claro, _r(centro), radio_cabeza)

    _linea(s, claro, hombro, codo2, grosor_miembro)
    _linea(s, claro, codo2, mano2, grosor_miembro)

    # Contorno claro de 1 píxel: lo que lo separa del vacío negro
    mascara = pygame.mask.from_surface(s, 40)
    borde = min(255, int(150 + 70 * max(luz, alba)))
    for punto in mascara.outline():
        s.set_at(punto, (borde, borde, min(255, borde + 10), 255))

    # Abre los ojos: un destello al final
    if _suave((t - 0.86) / 0.1) > 0.5:
        ex = int(centro[0] + radio_cabeza * 0.45)
        ey = int(centro[1] - radio_cabeza * 0.2)
        pygame.draw.rect(s, (240, 240, 250, 255), (ex, ey, 2, 1))

    return s, (cadera[0], suelo)


def _reflejo_silueta(superficie, sil, pos, suelo, alto):
    """Reflejo de la silueta en el suelo invisible."""
    if INTENSIDAD_REFLEJO <= 0:
        return
    n = min(suelo, int(alto * 0.25))
    if n <= 0:
        return
    zona = sil.subsurface(pygame.Rect(0, suelo - n, sil.get_width(), n)).copy()
    reflejo = pygame.transform.flip(zona, False, True)
    reflejo.blit(
        _degradado_alfa(sil.get_width(), n, INTENSIDAD_REFLEJO),
        (0, 0),
        special_flags=pygame.BLEND_RGBA_MULT,
    )
    superficie.blit(reflejo, (pos[0], pos[1] + suelo))


def _escena_silueta(pantalla, tiempo, t_cuadro, tiempo_mundo, pie_y):
    """El polvo se reúne y forma un hombre que va despertando."""
    rel = tiempo - INICIO_SILUETA
    if rel < -VIDA_PARTICULA:
        return

    ancho, alto = pantalla.get_size()
    centro_x = int(ancho * POSICION_SILUETA)
    luz = _luz_en(centro_x, tiempo_mundo, ancho, alto)
    escala_ref = alto * ESCALA_ALTURA / 180
    t_despertar = (t_cuadro - INICIO_DESPERTAR) / DURACION_DESPERTAR
    alba = _suave((t_despertar - 0.30) / 0.70)

    # Amanecer: un resplandor cálido que crece detrás de él
    if alba > 0:
        radio = int(alto * 0.55) // 2 * 2
        glow = _resplandor(radio, (255, 240, 215)).copy()
        glow.set_alpha(int(255 * alba))
        origen = (centro_x - radio, pie_y - int(alto * 0.12) - radio)
        for _ in range(2):
            pantalla.blit(glow, origen)

    _charco_de_luz(
        pantalla, centro_x, pie_y, escala_ref, luz, _suave(rel / DURACION_SILUETA)
    )

    sil, (hx, suelo) = _silueta(alto, t_despertar, t_cuadro, luz, alba)
    particulas = None
    if rel < DURACION_SILUETA:
        particulas = _disolver(sil, rel, DURACION_SILUETA, True, 23)

    pos = (centro_x - hx, pie_y - suelo)
    _reflejo_silueta(pantalla, sil, pos, suelo, alto)
    pantalla.blit(sil, pos)
    _dibujar_particulas(pantalla, particulas, pos)


# ----------------------------------------------------------------------
# Escena completa
# ----------------------------------------------------------------------
def dibujar(superficie, personaje, tiempo):
    """Dibuja la escena: camina, se desintegra y despierta como silueta."""
    ancho_real, alto_real = superficie.get_size()
    ancho = -(-ancho_real // PIXEL)   # resolución baja (redondeo hacia arriba)
    alto = -(-alto_real // PIXEL)
    pantalla = pygame.Surface((ancho, alto))

    # El mundo se frena mientras el personaje se apaga (y con él sus pasos)
    tiempo_mundo = _tiempo_fondo(tiempo)

    # Animaciones a pocos cuadros por segundo: sensación de sprite animado
    t_personaje = math.floor(tiempo_mundo * FPS_PERSONAJE) / FPS_PERSONAJE
    t_cuadro = math.floor(tiempo * FPS_PERSONAJE) / FPS_PERSONAJE
    t_giro = math.floor(tiempo * FPS_GIRO) / FPS_GIRO

    suelo_y = int(alto * 0.74)
    pie_y = suelo_y + int(alto * 0.07)
    _dibujar_fondo(pantalla, tiempo_mundo, t_giro)

    _escena_personaje(pantalla, personaje, tiempo, t_personaje, tiempo_mundo, pie_y)
    _escena_silueta(pantalla, tiempo, t_cuadro, tiempo_mundo, pie_y)

    _dibujar_primer_plano(pantalla, tiempo_mundo, t_giro)

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