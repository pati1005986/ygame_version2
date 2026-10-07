import math
import random

import pygame

from plataformas import color_desde_hue


# Caché de superficies reutilizadas entre frames para el fondo segmentado.
_CACHE_FONDO = {}


def _obtener_superficie(clave, tam):
    """Devuelve una Surface SRCALPHA reutilizada del tamaño pedido."""
    capa = _CACHE_FONDO.get(clave)
    if capa is None or capa.get_size() != tam:
        capa = pygame.Surface(tam, pygame.SRCALPHA)
        _CACHE_FONDO[clave] = capa
    else:
        capa.fill((0, 0, 0, 0))
    return capa


# ---------------------------------------------------------------------------
# Trazo orgánico: contornos ondulados que imitan una pincelada caricaturesca
# en vez de círculos/elipses perfectos. Es la base "psicodélica" del fondo.
# ---------------------------------------------------------------------------

def _punto_organico(centro, radio, angulo, tiempo, fase, amplitud=0.42, asimetria=0.0):
    """Deforma un radio con varias ondas superpuestas, como un trazo a mano.

    `asimetria` rompe la simetría radial (más "dibujado a mano", menos
    geométrico) añadiendo un lóbulo dominante en una dirección, como una
    pincelada caricaturesca que nunca es perfectamente redonda.
    """
    ondulacion = (
        math.sin(angulo * 3 + fase) * amplitud
        + math.sin(angulo * 7 - fase * 1.7 + tiempo * 1.3) * amplitud * 0.45
        + math.sin(angulo * 1.5 + tiempo * 0.6 + fase) * amplitud * 0.55
        + math.sin(angulo * 2 + fase * 0.6) * asimetria
    )
    r = radio * max(0.22, 1 + ondulacion)
    return (
        centro[0] + math.cos(angulo) * r,
        centro[1] + math.sin(angulo) * r,
    )


def _mancha_organica(capa, centro, radio, color, alpha, tiempo, fase, puntos=26, asimetria=0.12):
    """Mancha con contorno ondulado: la unidad básica de 'pincelada' del fondo."""
    pts = [
        _punto_organico(centro, radio, (i / puntos) * math.tau, tiempo, fase, asimetria=asimetria)
        for i in range(puntos)
    ]
    pygame.draw.polygon(capa, (*color, alpha), pts)


def _trazo_contorno(capa, centro, radio, color, alpha, tiempo, fase, grosor=3):
    """Línea de contorno tipo tinta, exagerando el borde de la mancha (caricatura)."""
    pts = [
        _punto_organico(centro, radio * 1.05, (i / 30) * math.tau, tiempo, fase, 0.5, asimetria=0.15)
        for i in range(30)
    ]
    pygame.draw.polygon(capa, (*color, alpha), pts, grosor)


def _trazo_tinta(capa, centro, radio, tiempo, fase, alpha=150, grosor=4):
    """Contorno oscuro tipo 'tinta de cómic': el rasgo caricaturesco más
    reconocible (bordes gruesos casi negros alrededor de formas de color)."""
    pts = [
        _punto_organico(centro, radio * 1.08, (i / 34) * math.tau, tiempo, fase, 0.48, asimetria=0.14)
        for i in range(34)
    ]
    pygame.draw.polygon(capa, (18, 14, 28, alpha), pts, grosor)


def _puntos_halftone(superficie, ancho, alto, tiempo, hue_base, paso=52, alpha=26):
    """Textura de puntos estilo cómic/pop-art (halftone), muy sutil, para que
    el fondo se lea como una lámina impresa en vez de un degradado liso.

    Rendimiento: el paso de la grilla se subió de 34 a 52px (menos de la
    mitad de puntos) y el color solo se recalcula cada pocas columnas en
    vez de en cada punto individual: la conversión HSV->RGB (``color_desde_hue``)
    es lo más caro de este bucle y el matiz apenas cambia entre puntos
    vecinos, así que reutilizarlo es imperceptible mientras ahorra muchas
    llamadas por fotograma.
    """
    capa = _obtener_superficie("halftone", (ancho, alto))
    fila = 0
    for y in range(-paso, alto + paso, paso):
        desfase = (paso // 2) if fila % 2 else 0
        color = None
        for indice_col, x in enumerate(range(-paso, ancho + paso, paso)):
            cx = x + desfase
            cy = y
            onda = math.sin(cx * 0.01 + tiempo * 0.4) + math.cos(cy * 0.013 - tiempo * 0.3)
            radio_punto = max(1.5, 3.2 + onda * 1.6)
            if color is None or indice_col % 3 == 0:
                hue = (hue_base + (cx / ancho) * 0.15 + tiempo * 0.02) % 1.0
                color = color_desde_hue(hue, 0.4, 0.4)
            pygame.draw.circle(capa, (*color, alpha), (cx, cy), int(radio_punto))
        fila += 1
    superficie.blit(capa, (0, 0))


def _fondo_degradado(superficie, ancho, alto, hue_base, tiempo):
    """Cielo de fondo en degradado vertical (en vez de un color plano) para
    dar más profundidad atmosférica al estilo pop/abstracto."""
    color_arriba = color_desde_hue((hue_base - 0.04) % 1.0, 0.4, 0.97)
    color_abajo = color_desde_hue((hue_base + 0.05) % 1.0, 0.3, 0.8)
    franjas = 48
    alto_franja = math.ceil(alto / franjas) + 1
    for i in range(franjas):
        t = i / (franjas - 1)
        color = [
            int(color_arriba[c] + (color_abajo[c] - color_arriba[c]) * t)
            for c in range(3)
        ]
        pygame.draw.rect(superficie, color, (0, int(t * alto), ancho, alto_franja))


class ParticulaAbstracta:
    """Mancha de color translúcida, con contorno orgánico, que flota por el fondo."""

    def __init__(self, ancho, alto):
        self.ancho = ancho
        self.alto = alto
        self.pos = pygame.Vector2(random.uniform(0, ancho), random.uniform(0, alto))
        self.radio = random.uniform(34, 105)
        self.hue = random.random()
        self.vel = pygame.Vector2(random.uniform(-0.25, 0.25), random.uniform(-0.15, 0.15))
        self.fase = random.uniform(0, math.tau)
        self.fase2 = random.uniform(0, math.tau)
        self.secciones = random.randint(8, 15)
        self.giro = random.uniform(0.7, 1.6)

        # Rendimiento: dibujar esta mancha implica crear una Surface nueva
        # y trazar varios polígonos orgánicos con muchos puntos; hacerlo en
        # cada fotograma para las 12 partículas es caro. La forma se
        # recalcula solo cada pocos fotogramas (la animación es lenta, así
        # que no se nota) y mientras tanto se reutiliza la última capa,
        # reposicionada según el movimiento real de la partícula.
        self._capa_cache = None
        self._centro_cache = None
        self._contador_regen = random.randint(0, 4)  # desfasado entre partículas

    def actualizar(self, dt=1 / 60):
        factor_fotograma = dt * 60
        self.pos.x = (self.pos.x + self.vel.x * factor_fotograma) % self.ancho
        self.pos.y = (self.pos.y + self.vel.y * factor_fotograma) % self.alto

    def dibujar(self, superficie, tiempo):
        self._contador_regen += 1
        if self._capa_cache is not None and self._contador_regen % 4 != 0:
            superficie.blit(self._capa_cache, self.pos - self._centro_cache)
            return

        hue_base = (self.hue + tiempo * 0.02) % 1.0
        radio = self.radio + math.sin(tiempo * 2 + self.fase) * 8
        capa = pygame.Surface((radio * 2.6, radio * 2.6), pygame.SRCALPHA)
        centro = (radio * 1.3, radio * 1.3)

        # Mancha principal con borde ondulado (pincelada caricaturesca).
        color_principal = color_desde_hue(hue_base, 0.7, 0.95)
        _mancha_organica(capa, centro, radio, color_principal, 82, tiempo, self.fase, asimetria=0.16)
        _trazo_contorno(capa, centro, radio, color_desde_hue(hue_base, 0.85, 0.55), 100, tiempo, self.fase, grosor=3)
        # Contorno de tinta oscura: el "outline" de cómic que hace que la
        # mancha se lea como un personaje/objeto dibujado, no como una mancha borrosa.
        _trazo_tinta(capa, centro, radio, tiempo, self.fase, alpha=130, grosor=4)

        # Salpicaduras de color complementario para el efecto psicodélico "pop".
        hue_complementario = (hue_base + 0.5) % 1.0
        for i in range(self.secciones):
            angulo = self.fase2 + i * (math.tau / self.secciones) + tiempo * self.giro
            distancia = 5 + i * (radio / self.secciones) * 0.75
            offset = pygame.Vector2(math.cos(angulo), math.sin(angulo)) * distancia
            usa_complementario = i % 3 == 0
            hue_punto = hue_complementario if usa_complementario else (hue_base + i / self.secciones * 0.28) % 1.0
            color = color_desde_hue(hue_punto, 0.8, 0.95)
            radio_punto = max(3, int((radio * 0.2) - i * 0.35))
            centro_punto = (centro[0] + offset.x, centro[1] + offset.y)
            _mancha_organica(
                capa, centro_punto, radio_punto, color, 200, tiempo * 1.4, self.fase + i, puntos=10
            )

        base = color_desde_hue(hue_base, 0.5, 0.85)
        pygame.draw.circle(capa, (*base, 35), centro, int(radio * 0.85), 2)

        # Brillo tipo "cel-shading" de caricatura: un óvalo blanco desplazado
        # que simula luz reflejada, típico del cartoon plano.
        brillo_pos = (
            centro[0] - radio * 0.32,
            centro[1] - radio * 0.38 + math.sin(tiempo * 1.5 + self.fase) * 3,
        )
        brillo = pygame.Surface((int(radio * 0.7), int(radio * 0.42)), pygame.SRCALPHA)
        pygame.draw.ellipse(brillo, (255, 255, 255, 60), brillo.get_rect())
        brillo_rot = pygame.transform.rotate(brillo, math.degrees(self.fase) % 40 - 20)
        capa.blit(brillo_rot, brillo_rot.get_rect(center=brillo_pos))

        self._capa_cache = capa
        self._centro_cache = pygame.Vector2(centro)
        superficie.blit(capa, self.pos - self._centro_cache)


_VUELTAS_REMOLINO = 2.8
_HILOS_REMOLINO = 4


def _dibujar_remolino(superficie, x, y, radio, hue, tiempo, indice):
    """Espiral con grosor pulsante y goteo final, como una pincelada de acrílico.

    Rendimiento: esta era la función más costosa de todo el fondo. Con 4
    hilos y hasta 160 pasos por remolino, cada redibujado del fondo podía
    llegar a llamar ``color_desde_hue`` (conversión HSV->RGB) y
    ``pygame.draw.line`` más de 600 veces solo aquí, multiplicado por los
    3 remolinos del fondo. Se reduce el número de pasos y se recalcula el
    color cada varios segmentos en vez de en cada uno: el degradado de
    color a lo largo del brazo sigue viéndose suave porque el matiz
    cambia poco entre segmentos vecinos.
    """
    tam = (radio * 2, radio * 2)
    capa = _obtener_superficie(("remolino", indice), tam)
    centro = pygame.Vector2(radio, radio)
    pasos = min(70, max(30, int(radio * 0.45)))

    for hilo in range(_HILOS_REMOLINO):
        fase_hilo = hilo * (math.tau / _HILOS_REMOLINO)
        anterior = None
        color = None
        for paso in range(pasos + 1):
            t = paso / pasos
            angulo = (
                t * math.tau * _VUELTAS_REMOLINO
                + fase_hilo
                + tiempo * (1.3 + indice * 0.4)
                + math.sin(t * math.tau * 2 + tiempo) * 0.25  # deformación orgánica del brazo
            )
            distancia = 8 + t * (radio - 16) + math.sin(t * 14 + tiempo * 2) * (radio * 0.03)
            punto = (
                int(centro.x + math.cos(angulo) * distancia),
                int(centro.y + math.sin(angulo) * distancia),
            )
            if anterior is not None:
                if color is None or paso % 4 == 0:
                    color = color_desde_hue(
                        (hue + t * 0.4 + hilo / _HILOS_REMOLINO * 0.18 + tiempo * 0.05) % 1.0, 0.85, 1.0
                    )
                grosor = max(1, int(6 * (1 - t) + 2 * math.sin(tiempo * 3 + hilo)) + 1)
                pygame.draw.line(capa, (*color, 170), anterior, punto, grosor)
            anterior = punto

        # Gota de pintura al final del brazo, con leve caída animada.
        caida = abs(math.sin(tiempo * 0.8 + fase_hilo)) * radio * 0.12
        gota_pos = (anterior[0], anterior[1] + caida)
        color_gota = color_desde_hue((hue + 0.5 + hilo * 0.1) % 1.0, 0.9, 1.0)
        pygame.draw.circle(capa, (*color_gota, 150), (int(gota_pos[0]), int(gota_pos[1])), max(2, int(radio * 0.035)))

    color_nucleo = color_desde_hue(hue, 0.6, 1.0)
    pygame.draw.circle(capa, (*color_nucleo, 170), centro, max(5, int(radio * 0.07)))
    pygame.draw.circle(capa, (*color_desde_hue((hue + 0.5) % 1.0, 0.9, 1.0), 90), centro, max(9, int(radio * 0.12)), 2)
    superficie.blit(capa, (x, y))


def _dibujar_goteo(superficie, x, y, longitud, hue, tiempo, fase, grosor=6):
    """Chorro de pintura cayendo, con ancho decreciente y gota final."""
    avance = (math.sin(tiempo * 0.5 + fase) * 0.5 + 0.5)  # 0..1, oscila
    largo_actual = longitud * (0.3 + avance * 0.7)
    color = color_desde_hue(hue, 0.75, 0.9)
    tamano = (grosor * 4, int(longitud * 1.3) + 20)
    clave = ("goteo", grosor, int(longitud), tamano[0], tamano[1])
    capa = _obtener_superficie(clave, tamano)

    segmentos = 18
    for i in range(segmentos):
        t = i / segmentos
        if t * longitud > largo_actual:
            break
        alpha = int(150 * (1 - t * 0.6))
        ancho = max(1, int(grosor * (1 - t * 0.7)))
        py = int(t * longitud)
        pygame.draw.line(capa, (*color, alpha), (grosor * 2, py), (grosor * 2, py + 6), ancho)

    pygame.draw.circle(
        capa, (*color, 190), (grosor * 2, int(min(largo_actual, longitud))), max(3, grosor - 1)
    )
    superficie.blit(capa, (x - grosor * 2, y))


def _dibujar_caleidoscopio(superficie, centro, radio, hue_base, tiempo, ancho, alto, brazos=6):
    """Mandala giratorio de cuñas translúcidas: el 'motor' psicodélico del fondo."""
    capa = _obtener_superficie("caleidoscopio", (ancho, alto))
    cx, cy = centro
    rotacion = tiempo * 0.12

    for brazo in range(brazos):
        angulo_ini = rotacion + brazo * (math.tau / brazos)
        angulo_fin = angulo_ini + (math.tau / brazos) * 0.72
        hue = (hue_base + brazo / brazos * 0.6 + tiempo * 0.03) % 1.0
        color = color_desde_hue(hue, 0.7, 0.9)
        pulso = radio * (0.75 + math.sin(tiempo * 1.5 + brazo) * 0.2)

        puntos = [(cx, cy)]
        pasos_arco = 10
        for i in range(pasos_arco + 1):
            a = angulo_ini + (angulo_fin - angulo_ini) * (i / pasos_arco)
            puntos.append((cx + math.cos(a) * pulso, cy + math.sin(a) * pulso))
        pygame.draw.polygon(capa, (*color, 26), puntos)
        # Filo de cada cuña ligeramente marcado, como viñetas de cómic recortadas.
        pygame.draw.polygon(capa, (*color_desde_hue(hue, 0.9, 0.6), 22), puntos, 2)

    superficie.blit(capa, (0, 0))


_CACHE_CIUDAD = {}

# Opacidad máxima de la ciudad sobre el fondo abstracto (0-255).
_ALPHA_CIUDAD = 235
# Altura de la calle en la parte inferior de la pantalla.
_ALTO_SUELO = 22
# Color de "tinta de cómic" para los contornos, igual que en el resto del fondo.
_TINTA = (18, 14, 28)
# Cuántas ciudades distintas se guardan (una por matiz cuantizado).
_MAX_CIUDADES_CACHE = 6


# ---------------------------------------------------------------------------
# Utilidades de color y de dibujo
# ---------------------------------------------------------------------------

def _c(hue, sat, val):
    """Color RGB (tupla de enteros) a partir de matiz/saturación/valor."""
    return tuple(int(v) for v in color_desde_hue(hue % 1.0, sat, val)[:3])


def _mezclar(a, b, t):
    """Interpolación lineal entre dos colores RGB."""
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _degradado_vertical(capa, ancho, y0, y1, paradas):
    """Degradado vertical con varias paradas [(t, color), ...] con t en 0..1."""
    total = max(1, y1 - y0)
    for y in range(y0, y1):
        t = (y - y0) / total
        color = paradas[-1][1]
        for k in range(len(paradas) - 1):
            t0, c0 = paradas[k]
            t1, c1 = paradas[k + 1]
            if t <= t1:
                u = 0.0 if t1 == t0 else max(0.0, min(1.0, (t - t0) / (t1 - t0)))
                color = _mezclar(c0, c1, u)
                break
        pygame.draw.line(capa, color, (0, y), (ancho, y))


def _crear_resplandor(radio, color, alpha_max, pasos=24):
    """Sprite con un resplandor radial suave (círculos concéntricos)."""
    radio = max(2, int(radio))
    sprite = pygame.Surface((radio * 2, radio * 2), pygame.SRCALPHA)
    for i in range(pasos, 0, -1):
        f = i / pasos
        alpha = int(alpha_max * (1 - f) ** 2)
        pygame.draw.circle(sprite, (*color, alpha), (radio, radio), max(1, int(radio * f)))
    return sprite


def _niebla(capa, ancho, y0, y1, color, alpha_max):
    """Velo de bruma que sube desde el suelo: separa las capas del skyline
    y da sensación de profundidad atmosférica."""
    alto_velo = max(1, y1 - y0)
    velo = pygame.Surface((ancho, alto_velo), pygame.SRCALPHA)
    for y in range(alto_velo):
        t = y / alto_velo
        pygame.draw.line(velo, (*color, int(alpha_max * t ** 1.3)), (0, y), (ancho, y))
    capa.blit(velo, (0, y0))


# ---------------------------------------------------------------------------
# Cielo: degradado crepuscular, estrellas, luna con cráteres y nubes planas
# ---------------------------------------------------------------------------

def _dibujar_nube(capa, cx, cy, escala, color, color_sombra):
    """Nube estilo cartoon: base plana, cúmulos redondos y una sombra inferior."""
    w = int(230 * escala)
    h = int(86 * escala)
    nube = pygame.Surface((w, h + 8), pygame.SRCALPHA)
    burbujas = ((0.20, 0.62, 0.30), (0.40, 0.46, 0.42), (0.62, 0.52, 0.36), (0.80, 0.66, 0.26))
    for dy, col in ((5, color_sombra), (0, color)):
        for bx, by, br in burbujas:
            pygame.draw.circle(nube, col, (int(bx * w), int(by * h) + dy), int(br * h))
        pygame.draw.rect(nube, col, (int(0.14 * w), int(0.60 * h) + dy, int(0.72 * w), int(0.32 * h)))
        r_borde = max(2, int(0.16 * h))
        pygame.draw.circle(nube, col, (int(0.14 * w), int(0.76 * h) + dy), r_borde)
        pygame.draw.circle(nube, col, (int(0.86 * w), int(0.76 * h) + dy), r_borde)
    capa.blit(nube, (int(cx - w / 2), int(cy)))


def _dibujar_cielo(capa, ancho, alto, hue_base, rng):
    """Devuelve (color_horizonte, color_medio, centro_luna, radio_luna)."""
    cima = _c(hue_base, 0.10, 0.34)
    medio = _c(hue_base, 0.08, 0.56)
    horizonte = _c(hue_base + 0.05, 0.10, 0.74)
    _degradado_vertical(capa, ancho, 0, alto, [(0.0, cima), (0.55, medio), (1.0, horizonte)])

    luna = (int(ancho * 0.78), int(alto * 0.25))
    r_luna = max(18, int(min(ancho, alto) * 0.055))

    # Estrellas: más densas arriba, se desvanecen hacia el horizonte.
    estrellas = pygame.Surface((ancho, alto), pygame.SRCALPHA)
    tope = alto * 0.5
    for _ in range(max(10, (ancho * alto) // 30000)):
        x = rng.randrange(max(1, ancho))
        y = int((rng.random() ** 1.4) * tope)
        if math.hypot(x - luna[0], y - luna[1]) < r_luna * 2.2:
            continue
        alpha = min(255, int(90 * (1 - y / tope) ** 1.1) + 15)
        col = (255, 255, 245, alpha)
        sorteo = rng.random()
        if sorteo < 0.07:  # destello en cruz
            pygame.draw.line(estrellas, col, (x - 4, y), (x + 4, y), 1)
            pygame.draw.line(estrellas, col, (x, y - 4), (x, y + 4), 1)
        elif sorteo < 0.25:
            pygame.draw.circle(estrellas, col, (x, y), 2)
        else:
            pygame.draw.circle(estrellas, col, (x, y), 1)
    capa.blit(estrellas, (0, 0))

    # Halo grande y suave alrededor de la luna.
    halo = _crear_resplandor(int(min(ancho, alto) * 0.34), _c(hue_base, 0.08, 0.85), 70)
    capa.blit(halo, (luna[0] - halo.get_width() // 2, luna[1] - halo.get_height() // 2))

    # Luna con contorno de tinta y cráteres, como un dibujo de cómic.
    disco = _c(hue_base, 0.05, 0.80)
    sombra_disco = _mezclar(disco, medio, 0.35)
    pygame.draw.circle(capa, disco, luna, r_luna)
    for dx, dy, k in ((-0.35, -0.20, 0.22), (0.30, 0.25, 0.16), (0.10, -0.45, 0.12)):
        pygame.draw.circle(
            capa, sombra_disco,
            (int(luna[0] + dx * r_luna), int(luna[1] + dy * r_luna)),
            max(2, int(r_luna * k)),
        )
    pygame.draw.circle(capa, _TINTA, luna, r_luna, 3)

    # Nubes planas repartidas por el cielo (esquivando la luna).
    color_nube = _mezclar(medio, (150, 150, 155), 0.35)
    sombra_nube = _mezclar(medio, cima, 0.45)
    for i in range(7):
        x = ancho * (0.04 + i * 0.15) + rng.uniform(-40, 40)
        y = alto * rng.uniform(0.10, 0.40)
        escala = rng.uniform(0.7, 1.4)
        if math.hypot(x - luna[0], y - luna[1]) < r_luna * 3.5:
            x -= r_luna * 7
        _dibujar_nube(capa, x, y, escala, (*color_nube, 210), (*sombra_nube, 140))

    return horizonte, medio, luna, r_luna


# ---------------------------------------------------------------------------
# Edificios
# ---------------------------------------------------------------------------

def _generar_skyline(rng, ancho, ancho_min, ancho_max, h_min, h_max, hueco):
    """Lista de (x, ancho, alto). La altura sigue una onda suave (zonas de
    rascacielos y zonas bajas) mezclada con azar, para que no sea una peineta."""
    edificios = []
    fase = rng.uniform(0, math.tau)
    x = -rng.randint(0, ancho_min)
    while x < ancho:
        w = rng.randint(ancho_min, ancho_max)
        onda = 0.5 + 0.5 * math.sin(x / max(1, ancho) * math.tau * 1.6 + fase)
        factor = 0.55 * onda + 0.45 * rng.random()
        edificios.append((x, w, int(h_min + (h_max - h_min) * factor)))
        x += w + hueco
    return edificios


def _dibujar_remate(capa, brillo, tipo, x, y, w, color, sombra, hue_base, rng, balizas):
    """Remate del techo. ``balizas`` recoge luces que parpadean en vivo."""
    if tipo == 0:
        # Escalonado (ziggurat): dos bloques cada vez más angostos.
        inset = max(3, w // 5)
        inset2 = inset + max(2, w // 8)
        for ix, alto_r, y_r in ((inset, 12, y - 12), (inset2, 8, y - 20)):
            rect = (x + ix, y_r, max(3, w - ix * 2), alto_r)
            pygame.draw.rect(capa, color, rect)
            pygame.draw.rect(capa, _TINTA, rect, 2)
    elif tipo == 1:
        # Tejado a dos aguas con una mitad en sombra.
        cima = (x + w / 2, y - max(14, w // 2))
        pygame.draw.polygon(capa, color, [cima, (x, y), (x + w, y)])
        pygame.draw.polygon(capa, sombra, [cima, (x, y), (x + w / 2, y)])
        pygame.draw.polygon(capa, _TINTA, [cima, (x, y), (x + w, y)], 2)
    elif tipo == 2:
        # Antena con travesaño y baliza roja parpadeante.
        bx = x + w // 2
        pygame.draw.line(capa, _TINTA, (bx, y), (bx, y - 30), 2)
        pygame.draw.line(capa, _TINTA, (bx - 5, y - 21), (bx + 5, y - 21), 2)
        rojo = (255, 70, 70)
        pygame.draw.circle(capa, rojo, (bx, y - 31), 3)
        balizas.append((bx, y - 31, rojo))
    elif tipo == 3:
        # Tanque de agua sobre patas.
        r = max(5, w // 4)
        centro = (int(x + w * 0.5), int(y - r - 5))
        for dx in (-r * 0.6, r * 0.6):
            pygame.draw.line(capa, _TINTA, (centro[0] + dx, centro[1] + r), (centro[0] + dx * 1.4, y), 2)
        pygame.draw.circle(capa, color, centro, r)
        pygame.draw.circle(capa, sombra, (centro[0] - r // 3, centro[1]), max(2, r - r // 3))
        pygame.draw.circle(capa, color, (centro[0] + r // 4, centro[1]), max(2, r - r // 3))
        pygame.draw.circle(capa, _TINTA, centro, r, 2)
    elif tipo == 4:
        # Cúpula (semicírculo calculado a mano).
        r = max(6, w // 2 - 2)
        cx = x + w // 2
        arco = [
            (cx + math.cos(math.pi + math.pi * i / 12) * r, y + math.sin(math.pi + math.pi * i / 12) * r)
            for i in range(13)
        ]
        pygame.draw.polygon(capa, color, arco)
        pygame.draw.polygon(capa, _TINTA, arco, 2)
        pygame.draw.line(capa, _TINTA, (cx, y - r), (cx, y - r - 8), 2)
    else:
        # Letrero luminoso con patas.
        neon = _c(hue_base + 0.35 + rng.random() * 0.4, 0.40, 0.80)
        rect = (x + 3, y - 16, max(6, w - 6), 10)
        for px in (x + 6, x + w - 7):
            pygame.draw.line(capa, _TINTA, (px, y), (px, y - 6), 2)
        pygame.draw.rect(capa, neon, rect)
        pygame.draw.rect(capa, _TINTA, rect, 2)
        pygame.draw.rect(brillo, (*neon, 70), (rect[0] - 4, rect[1] - 4, rect[2] + 8, rect[3] + 8))


def _dibujar_capa_lejana(capa, edificios, y_suelo, color, rng):
    """Silueta plana, sin detalle: la niebla la desdibuja después."""
    borde = _mezclar(color, _TINTA, 0.25)
    for x, w, h in edificios:
        y = y_suelo - h
        pygame.draw.rect(capa, color, (x, y, w, h + _ALTO_SUELO))
        pygame.draw.rect(capa, borde, (x, y, w, h), 1)
        if rng.random() < 0.25:  # alguna antena o aguja
            pygame.draw.line(capa, borde, (x + w // 2, y), (x + w // 2, y - rng.randint(8, 18)), 2)


def _dibujar_capa_media(capa, edificios, y_suelo, color, sombra, ventana, rng):
    """Edificios intermedios: volumen sencillo y ventanitas escasas."""
    borde = _mezclar(color, _TINTA, 0.55)
    for x, w, h in edificios:
        y = y_suelo - h
        rect = (x, y, w, h + _ALTO_SUELO)
        pygame.draw.rect(capa, color, rect)
        pygame.draw.rect(capa, sombra, (x, y, max(3, w // 4), h + _ALTO_SUELO))
        pygame.draw.rect(capa, borde, rect, 2)
        for wy in range(y + 8, y_suelo - 6, 10):
            for wx in range(x + 5, x + w - 5, 8):
                if rng.random() < 0.16:
                    pygame.draw.rect(capa, ventana, (wx, wy, 2, 3))


def _dibujar_capa_cercana(capa, brillo, edificios, y_suelo, hue_base, nivel, colores, rng, balizas):
    """Capa frontal: volumen cel-shaded, luz de borde, ventanas con brillo,
    remates variados y tiendas con toldo en la planta baja."""
    color, sombra, luz, calido, frio, apagada = colores
    for indice, (x, w, h) in enumerate(edificios):
        y = y_suelo - h
        rect = (x, y, w, h + _ALTO_SUELO)
        lado = max(4, w // 4)

        pygame.draw.rect(capa, color, rect)
        pygame.draw.rect(capa, sombra, (x, y, lado, h + _ALTO_SUELO))          # cara en sombra
        pygame.draw.rect(capa, luz, (x + w - 4, y + 2, 2, h + _ALTO_SUELO))   # luz de borde
        pygame.draw.rect(capa, _TINTA, rect, 2)

        _dibujar_remate(capa, brillo, (indice + nivel) % 6, x, y, w, color, sombra, hue_base, rng, balizas)

        # Baliza en los edificios más altos.
        if h > (y_suelo * 0.42) and (indice + nivel) % 6 != 2:
            rojo = (255, 70, 70)
            pygame.draw.circle(capa, rojo, (x + w - 6, y - 3), 2)
            balizas.append((x + w - 6, y - 3, rojo))

        # Ventanas: hay pisos enteros encendidos y otros casi apagados.
        for wy in range(y + 10, y_suelo - 26, 13):
            piso_activo = rng.random() < 0.30
            for wx in range(x + 5, x + w - 9, 9):
                if rng.random() < (0.55 if piso_activo else 0.06):
                    col = calido if rng.random() < 0.7 else frio
                    pygame.draw.rect(capa, col, (wx, wy, 5, 7))
                    pygame.draw.rect(brillo, (*col, 55), (wx - 3, wy - 3, 11, 13))
                else:
                    pygame.draw.rect(capa, apagada, (wx, wy, 5, 7))

        # Tienda en la planta baja: vitrina iluminada y toldo de color.
        if w >= 30 and rng.random() < 0.7:
            ty = y_suelo - 12
            toldo = _c(hue_base + 0.30 + rng.random() * 0.5, 0.30, 0.62)
            pygame.draw.rect(capa, calido, (x + 4, ty + 4, w - 8, 8))
            pygame.draw.rect(capa, toldo, (x + 3, ty, w - 6, 5))
            pygame.draw.rect(capa, _TINTA, (x + 3, ty, w - 6, 5), 1)
            pygame.draw.rect(brillo, (*calido, 70), (x + 2, ty + 2, w - 4, 12))


# ---------------------------------------------------------------------------
# Calle y farolas
# ---------------------------------------------------------------------------

def _dibujar_calle(capa, ancho, alto, y_suelo, color_cerca, horizonte):
    asfalto = _mezclar(color_cerca, _TINTA, 0.5)
    pygame.draw.rect(capa, asfalto, (0, y_suelo, ancho, _ALTO_SUELO))
    pygame.draw.line(capa, _TINTA, (0, y_suelo), (ancho, y_suelo), 3)
    pygame.draw.line(capa, _mezclar(asfalto, horizonte, 0.3), (0, y_suelo + 3), (ancho, y_suelo + 3), 1)
    marca = _mezclar(asfalto, (255, 240, 170), 0.55)
    for x in range(8, ancho, 44):
        pygame.draw.rect(capa, marca, (x, alto - 8, 22, 2))


def _dibujar_farolas(capa, ancho, y_suelo, hue_base):
    """Farolas con poste, brazo, cono de luz y halo: anclan la ciudad al suelo."""
    luz = _c(hue_base + 0.12, 0.35, 0.90)
    halo = _crear_resplandor(46, luz, 105)
    alto_cono = 62
    cono = pygame.Surface((70, alto_cono + 1), pygame.SRCALPHA)
    pygame.draw.polygon(cono, (*luz, 38), [(35, 0), (1, alto_cono), (69, alto_cono)])

    for i, x in enumerate(range(70, ancho, 190)):
        signo = 1 if i % 2 == 0 else -1
        lx = x + signo * 14
        ly = y_suelo - 62
        capa.blit(cono, (lx - 35, ly))
        pygame.draw.line(capa, _TINTA, (x, y_suelo + 2), (x, y_suelo - 58), 3)
        pygame.draw.line(capa, _TINTA, (x, y_suelo - 58), (lx, ly), 3)
        pygame.draw.rect(capa, _TINTA, (lx - 5, ly, 10, 4))
        capa.blit(halo, (lx - 46, ly + 2 - 46))
        pygame.draw.circle(capa, luz, (lx, ly + 4), 3)


# ---------------------------------------------------------------------------
# Construcción y dibujo de la ciudad
# ---------------------------------------------------------------------------

def _construir_ciudad(ancho, alto, hue_fondo, nivel):
    """Renderiza la ciudad completa en una Surface opaca. Devuelve
    ``(capa, balizas)``: ``balizas`` son las luces que parpadean cada frame."""
    hue_base = (hue_fondo + 0.08) % 1.0
    rng = random.Random(nivel * 7919 + 13)  # misma ciudad para el mismo nivel
    y_suelo = alto - _ALTO_SUELO

    capa = pygame.Surface((ancho, alto))
    horizonte, medio, _luna, _r_luna = _dibujar_cielo(capa, ancho, alto, hue_base, rng)

    calido = _c(hue_base + 0.13, 0.35, 0.82)
    frio = _c(hue_base + 0.55, 0.12, 0.72)

    # --- Capa lejana + niebla ---
    color_lejos = _c(hue_base + 0.08, 0.07, 0.48)
    lejos = _generar_skyline(rng, ancho, 24, 44, int(alto * 0.14), int(alto * 0.36), 0)
    _dibujar_capa_lejana(capa, lejos, y_suelo, color_lejos, rng)
    _niebla(capa, ancho, int(alto * 0.30), y_suelo, horizonte, 200)

    # --- Capa media + niebla más ligera ---
    color_medio = _c(hue_base + 0.10, 0.07, 0.33)
    sombra_medio = _mezclar(color_medio, _TINTA, 0.35)
    ventana_media = _mezclar(calido, color_medio, 0.45)
    medios = _generar_skyline(rng, ancho, 28, 50, int(alto * 0.18), int(alto * 0.46), -2)
    _dibujar_capa_media(capa, medios, y_suelo, color_medio, sombra_medio, ventana_media, rng)
    _niebla(capa, ancho, int(alto * 0.40), y_suelo, horizonte, 130)

    # --- Capa cercana con detalle ---
    color_cerca = _c(hue_base + 0.12, 0.06, 0.18)
    colores = (
        color_cerca,
        _mezclar(color_cerca, _TINTA, 0.40),     # sombra
        _mezclar(color_cerca, horizonte, 0.30),  # luz de borde (atardecer)
        calido,
        frio,
        _mezclar(color_cerca, (10, 8, 20), 0.45),  # ventana apagada
    )
    balizas_pos = []
    brillo = pygame.Surface((ancho, alto), pygame.SRCALPHA)
    cercanos = _generar_skyline(rng, ancho, 34, 58, int(alto * 0.14), int(alto * 0.50), rng.choice((0, 2, 3)))
    _dibujar_capa_cercana(capa, brillo, cercanos, y_suelo, hue_base, nivel, colores, rng, balizas_pos)
    capa.blit(brillo, (0, 0))  # resplandor de ventanas, tiendas y letreros

    _dibujar_calle(capa, ancho, alto, y_suelo, color_cerca, horizonte)
    _dibujar_farolas(capa, ancho, y_suelo, hue_base)

    # Llovizna fina y estática sobre toda la escena (ambiente triste).
    lluvia = pygame.Surface((ancho, alto), pygame.SRCALPHA)
    for _ in range(max(80, (ancho * alto) // 2200)):
        x = rng.randrange(max(1, ancho))
        y = rng.randrange(max(1, alto))
        largo = rng.randint(7, 16)
        pygame.draw.line(lluvia, (200, 205, 215, rng.randint(25, 55)), (x, y), (x - largo // 4, y + largo), 1)
    capa.blit(lluvia, (0, 0))

    # Sprites de resplandor para las balizas, en varios niveles de intensidad
    # (se elige uno por frame según el pulso; así no hay que cambiar alphas).
    sprites_por_color = {}
    balizas = []
    for bx, by, color in balizas_pos:
        if color not in sprites_por_color:
            sprites_por_color[color] = [
                _crear_resplandor(12, color, int(230 * k / 5)) for k in range(1, 6)
            ]
        balizas.append((sprites_por_color[color], bx, by, rng.uniform(0, math.tau)))
    return capa, balizas


def _dibujar_ciudad(superficie, ancho, alto, hue_fondo, nivel, transicion, tiempo=0.0):
    """Superpone un skyline urbano al atardecer con tres capas de parallax,
    niebla atmosférica, ventanas con brillo, calle y farolas.

    Rendimiento: la ciudad entera se renderiza una sola vez por nivel en una
    Surface opaca y se cachea; en cada frame solo se hace un blit con alpha
    global (la transición) y se animan unas pocas luces de baliza. El matiz
    se cuantiza en pasos de 0.04 para que el pequeño vaivén de color del
    fondo no obligue a reconstruir la ciudad continuamente.
    """
    if transicion <= 0:
        return

    hue_q = round(hue_fondo * 25) / 25
    clave = (nivel, hue_q, ancho, alto)
    entrada = _CACHE_CIUDAD.get(clave)
    if entrada is None:
        while len(_CACHE_CIUDAD) >= _MAX_CIUDADES_CACHE:
            _CACHE_CIUDAD.pop(next(iter(_CACHE_CIUDAD)))
        entrada = _construir_ciudad(ancho, alto, hue_q, nivel)
        _CACHE_CIUDAD[clave] = entrada

    capa, balizas = entrada
    capa.set_alpha(int(_ALPHA_CIUDAD * transicion))
    superficie.blit(capa, (0, 0))

    # Balizas que parpadean (antenas y azoteas altas).
    for sprites, bx, by, fase in balizas:
        luz = (0.5 + 0.5 * math.sin(tiempo * 2.4 + fase)) * transicion
        if luz < 0.1:
            continue
        sprite = sprites[min(len(sprites) - 1, int(luz * len(sprites)))]
        superficie.blit(sprite, (bx - sprite.get_width() // 2, by - sprite.get_height() // 2))


def dibujar_fondo_segmentado(superficie, tiempo, hue_fondo, ancho, alto, nivel=0):
    """Transición progresiva desde el fondo abstracto hacia un skyline urbano más coherente."""
    hue_base = (hue_fondo + math.sin(tiempo * 0.35) * 0.05) % 1.0
    transicion = max(0.0, min(1.0, (nivel - 2) / 8.0))

    _fondo_degradado(superficie, ancho, alto, hue_base, tiempo)

    capa_abstracta = pygame.Surface((ancho, alto), pygame.SRCALPHA)
    _dibujar_caleidoscopio(
        capa_abstracta,
        (ancho * 0.5, alto * 0.5),
        max(ancho, alto) * 0.65,
        hue_base,
        tiempo,
        ancho,
        alto,
    )
    _puntos_halftone(capa_abstracta, ancho, alto, tiempo, hue_base)

    for i in range(6):
        hue = (hue_base + i / 6 + tiempo * 0.025) % 1.0
        color = color_desde_hue(hue, 0.75, 0.85)
        color_pop = color_desde_hue((hue + 0.5) % 1.0, 0.85, 0.95)
        radio = 150 + i * 42
        centro_x = ancho * (0.18 + (i % 3) * 0.24)
        centro_y = alto * (0.22 + (i % 2) * 0.28)

        margen = 26
        tam = (radio * 2 + margen * 2, radio * 2 + margen * 2)
        capa = _obtener_superficie(("bloque", i), tam)
        centro_local = (radio + margen, radio + margen)

        _mancha_organica(capa, centro_local, radio, color, int(58 * (1.0 - transicion)), tiempo, i * 1.7, puntos=24, asimetria=0.18)
        _trazo_contorno(capa, centro_local, radio, color_pop, int(80 * (1.0 - transicion)), tiempo, i * 1.7, grosor=3)
        _trazo_tinta(capa, centro_local, radio, tiempo, i * 1.7, alpha=int(110 * (1.0 - transicion)), grosor=5)

        rect_local = pygame.Rect(margen, margen, radio * 2, radio * 2)
        pygame.draw.arc(
            capa,
            (*color_pop, int(130 * (1.0 - transicion))),
            rect_local.inflate(18, 18),
            math.radians(20 + i * 18 + tiempo * 14),
            math.radians(190 + i * 18 + tiempo * 14),
            12,
        )
        capa_abstracta.blit(capa, (centro_x - radio - margen, centro_y - radio - margen))

        if i % 2 == 0:
            _dibujar_goteo(
                capa_abstracta,
                centro_x + radio * 0.3,
                centro_y + radio * 0.6,
                90 + i * 10,
                (hue + 0.5) % 1.0,
                tiempo,
                fase=i * 2.1,
            )

    for i in range(3):
        hue = (hue_base + 0.18 + i * 0.16 + tiempo * 0.035) % 1.0
        x = (ancho // 3) * (i + 1) - 80
        y = alto // 2 - 100
        radio = 160 + i * 40
        _dibujar_remolino(capa_abstracta, x, y, radio, hue, tiempo, i)

    superficie.blit(capa_abstracta, (0, 0))
    # Se pasa hue_fondo (sin el vaivén de hue_base) para que la ciudad cacheada sea estable.
    _dibujar_ciudad(superficie, ancho, alto, hue_fondo, nivel, transicion, tiempo)