"""Caída al vacío psicodélico (pixel art): alternativa a la pantalla de Game Over.

El personaje (en su versión eufórica del modo infinito) es succionado por un
túnel de espirales de colores que cambia de paleta al ritmo de un latido cada
vez más rápido, mientras la pantalla tiembla, se rompe en tiras (glitch) y el
mundo del juego se desvanece en un iris que se abre desde el personaje. Al
final: onda de choque y cierre de iris en negro. Cuando termina,
``terminada`` pasa a ``True``.

Uso mínimo (igual que antes)::

    from vacio import AnimacionVacio

    AnimacionVacio.precalentar(pantalla)          # opcional, al cargar el juego
    anim = AnimacionVacio(pantalla, jugador)      # al perder
    anim.actualizar(dt); anim.dibujar(pantalla)   # en el bucle
    if anim.terminada: ...

Cómo consigue el look pixel art (y sigue siendo barato):
    * TODO se dibuja en una superficie diminuta (~256 px de ancho) y se
      amplía con vecino más cercano por un factor entero: píxeles gordos y
      uniformes. Sin suavizados en ningún sitio.
    * El túnel es un mapa de índices con tramado ordenado (dither de Bayer)
      pintado con una paleta de bandas planas, con línea oscura entre bandas
      y dos tonos por banda (estilo cel-shading de 16 bits). Se anima rotando
      la paleta (palette cycling): por fotograma solo cambian 256 colores.
    * Cada 2 latidos se cambia de paleta (arcoíris, ácido, CGA, fuego,
      vaporwave) y cada 4 se alterna entre dos túneles de giro opuesto.
    * El personaje se dibuja con su propio pixel art (sin suavizar), con
      rotación en pasos de 15°, escala en pasos y posición ajustada a la
      rejilla del fondo, contorno negro y estela de siluetas de colores.
    * Las transiciones (iris de entrada y de salida) son circulares y
      "escalonadas", como en las consolas clásicas, en vez de fundidos.

Ajustes: todo está en las constantes de abajo. Si quieres una versión sin
destellos (fotosensibilidad), pon ``REDUCIR_PARPADEO = True``.
"""

import colorsys
import math
import random
from collections import deque

import pygame

from personaje import PersonajeHumanoide

# ----------------------------------------------------------------------
# Ajustes (todo afinable desde aquí)
# ----------------------------------------------------------------------
DURACION_CAIDA = 2.8      # s que tarda en tragárselo el vacío
DURACION_FINAL = 0.7      # s de onda de choque + cierre de iris
DURACION_ENTRADA = 0.5    # s que tarda el iris en abrirse y revelar el vórtice
ANCHO_BAJO = 256          # resolución interna (más bajo = píxeles más gordos)
MARGEN = 4                # px extra por lado en la superficie interna (sacudida)
BRAZOS = 6                # brazos de la espiral principal
TORSION = 1.5             # cuánto se enrosca la espiral
NUM_CHISPAS = 64          # chispas que se precipitan al centro
NUM_RAYAS = 12            # rayas de velocidad oscuras que giran
NUM_ANILLOS = 6           # anillos poligonales del túnel
HISTORIAL_ESTELA = 7      # siluetas de la estela del personaje
LATIDO_INICIAL = 0.46     # s entre latidos al empezar...
LATIDO_FINAL = 0.26       # ...y al final de la caída (más rápido = más frenético)
REDUCIR_PARPADEO = False  # True: sin flashes blancos y paleta más pausada

_DOS_PI = 2 * math.pi
_P_ACERCAR = 0.22         # fracción de la caída en que el personaje viaja al centro
_ANCHO_SPRITE, _ALTO_SPRITE = 220, 260
_CK = (255, 0, 254)       # color transparente de las capas auxiliares
_BAYER = tuple(
    tuple((v + 0.5) / 16 for v in fila)
    for fila in ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
)
_COLORES_VINETA = ((70, 0, 110), (26, 0, 58), (0, 0, 0))

_CACHE_MAPAS = {}
_CACHE_VINETAS = {}


# ----------------------------------------------------------------------
# Paletas: bandas planas, línea oscura entre bandas y dos tonos por banda
# ----------------------------------------------------------------------
_TEMAS = (
    # arcoíris
    (((255, 40, 70), (255, 150, 0), (255, 235, 0), (70, 235, 70),
      (0, 225, 255), (50, 90, 255), (160, 60, 255), (255, 50, 200)), (24, 0, 48)),
    # ácido
    (((190, 255, 0), (255, 0, 140), (0, 255, 200), (255, 120, 0),
      (120, 0, 255), (255, 255, 120)), (0, 18, 30)),
    # CGA
    (((85, 255, 255), (255, 85, 255), (255, 255, 255)), (0, 0, 0)),
    # fuego
    (((255, 0, 60), (255, 110, 0), (255, 200, 0), (255, 255, 160),
      (200, 0, 120), (110, 0, 160)), (30, 0, 20)),
    # vaporwave
    (((255, 113, 206), (1, 205, 254), (5, 255, 161), (185, 103, 255),
      (255, 251, 150)), (20, 0, 60)),
)


def _crear_paleta(colores, separador, repeticiones=2):
    """256 colores: ``repeticiones`` vueltas por la lista de colores; cada
    banda lleva una línea oscura al principio y su mitad final sombreada."""
    n = len(colores) * repeticiones
    ancho = 256.0 / n
    paleta = []
    for i in range(256):
        banda = min(n - 1, int(i / ancho))
        pos = (i - banda * ancho) / ancho
        base = colores[banda % len(colores)]
        if pos < 0.12:
            color = separador
        elif pos < 0.62:
            color = base
        else:
            color = tuple(int(c * 0.72) for c in base)
        paleta.append(color)
    return paleta


_PALETAS = tuple(_crear_paleta(c, s) for c, s in _TEMAS)


def _hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


# Colores vivos para chispas, anillos y estela.
_NEON = tuple(_hsv(i / 12, 0.9, 1.0) for i in range(12)) + ((255, 255, 255),) * 2


# ----------------------------------------------------------------------
# Datos precalculados (una sola vez por tamaño)
# ----------------------------------------------------------------------
def _geometria(tam):
    """Factor de ampliación entero y tamaño de la superficie interna."""
    ancho, alto = tam
    f = max(1, int(round(ancho / ANCHO_BAJO)))
    return f, -(-ancho // f), -(-alto // f)


def _obtener_mapa(w, h, variante):
    """Índices de paleta (0-255) de un túnel en espiral con tramado de Bayer.

    variante 0: espiral de ``BRAZOS`` brazos, giro a la derecha.
    variante 1: 4 brazos, giro contrario y más alabeada.
    """
    clave = (w, h, variante)
    mapa = _CACHE_MAPAS.get(clave)
    if mapa is not None:
        return mapa
    if variante == 0:
        brazos, torsion, alabeo, lobulos = BRAZOS, TORSION, 0.10, 3
    else:
        brazos, torsion, alabeo, lobulos = 4, -1.2, 0.17, 5
    cx, cy = (w - 1) / 2, (h - 1) / 2
    k_ang = brazos / _DOS_PI
    atan2, log, hypot, sin = math.atan2, math.log, math.hypot, math.sin
    datos = bytearray(w * h)
    i = 0
    for y in range(h):
        dy = y - cy
        bayer = _BAYER[y & 3]
        for x in range(w):
            dx = x - cx
            ang = atan2(dy, dx)
            lr = log(hypot(dx, dy) + 1.0)
            u = k_ang * ang + torsion * lr + alabeo * sin(lobulos * ang + 3.0 * lr)
            u += (bayer[x & 3] - 0.5) * 0.03  # tramado: bordes de banda "a cuadros"
            datos[i] = int((u % 1.0) * 256)
            i += 1
    mapa = _CACHE_MAPAS[clave] = bytes(datos)
    return mapa


def _superficie_indexada(mapa, w, h):
    """Superficie de 8 bits con los índices de ``mapa`` (con alternativas por
    si la versión de pygame no admite alguna vía)."""
    for crear in (pygame.image.frombuffer, pygame.image.fromstring):
        try:
            return crear(mapa, (w, h), "P")
        except (ValueError, TypeError, pygame.error):
            pass
    superficie = pygame.Surface((w, h), 0, 8)
    superficie.set_palette([(i, i, i) for i in range(256)])
    i = 0
    for y in range(h):
        for x in range(w):
            v = mapa[i]
            superficie.set_at((x, y), (v, v, v))
            i += 1
    return superficie


def _obtener_vineta(w, h):
    """Pozo oscuro en el centro y bordes sombreados, con tramado de Bayer y
    solo 3 tonos (púrpura, oscuro, negro): nada de degradados suaves."""
    clave = (w, h)
    vineta = _CACHE_VINETAS.get(clave)
    if vineta is not None:
        return vineta
    vineta = pygame.Surface((w, h))
    vineta.fill(_CK)
    cx, cy = (w - 1) / 2, (h - 1) / 2
    rmax = math.hypot(cx, cy)
    hypot = math.hypot
    for y in range(h):
        dy = y - cy
        bayer = _BAYER[y & 3]
        for x in range(w):
            d = hypot(x - cx, dy) / rmax
            pozo = max(0.0, 1.0 - d / 0.15)
            borde = min(1.0, max(0.0, (d - 0.6) / 0.4))
            borde = borde * borde * (3 - 2 * borde)
            densidad = min(1.0, pozo + 0.30 * borde)
            nivel = min(3, int(densidad * 3 + bayer[x & 3]))
            if nivel:
                vineta.set_at((x, y), _COLORES_VINETA[nivel - 1])
    vineta.set_colorkey(_CK)
    _CACHE_VINETAS[clave] = vineta
    return vineta


def _convertir(superficie, colorkey=None):
    if pygame.display.get_surface() is not None:
        superficie = superficie.convert()
    if colorkey is not None:
        superficie.set_colorkey(colorkey)
    return superficie


# ----------------------------------------------------------------------
# Animación
# ----------------------------------------------------------------------
class AnimacionVacio:
    """Animación de caída al vacío (pixel art).

    Args:
        superficie: pantalla (o superficie) donde se dibujará. Se usa para
            conocer el tamaño y, si ``captura`` es True, para convertir el
            último fotograma del juego en el "mundo" que el iris va abriendo.
        personaje: el jugador (opcional). Se toma su color, dirección,
            volumen y, si no das ``posicion``, su ``rect.center``.
        posicion: centro del personaje EN COORDENADAS DE PANTALLA. Si tu
            juego usa cámara, pásala ya convertida (rect.center - cámara).
            Si se sale de la pantalla (p. ej. cayó por un hueco) se acerca
            al borde más cercano.
        color: color del personaje si no pasas ``personaje``.
        euforico: ``True`` = cara del modo infinito (ojos locos, sonrisa).
        sonido: reproduce un silbido descendente (síntesis en memoria).
        captura: copia la pantalla al empezar y la deshace con un iris.
        duracion: segundos de caída (la animación completa dura
            ``duracion + DURACION_FINAL``).
    """

    def __init__(
        self,
        superficie,
        personaje=None,
        posicion=None,
        color=None,
        euforico=True,
        sonido=True,
        captura=True,
        duracion=DURACION_CAIDA,
    ):
        self._tam = superficie.get_size()
        ancho, alto = self._tam
        self._duracion_caida = max(0.5, float(duracion))
        self.duracion_total = self._duracion_caida + DURACION_FINAL
        self.t = 0.0
        self._ultimo_tick = None
        self._cuadro = 0
        self._fase = random.uniform(0, 256)        # fase de la paleta
        self._giro = random.uniform(0, _DOS_PI)    # giro de rayas y anillos
        self._anillos = random.random()            # avance de los anillos
        self._ang_orbita = random.uniform(0, _DOS_PI)
        self._signo = random.choice((-1, 1))       # sentido de giro del personaje
        self._tema = random.randrange(len(_PALETAS))
        self._mapa = 0                             # túnel activo (0 o 1)
        self._cuenta_latido = 0.0                  # el primer latido es inmediato
        self._latidos = 0
        self._pulso = 0.0                          # 1 en cada latido, decae rápido
        self._glitch = 0.0
        self._tiras = []
        self._destello_sprite = 0
        self._sacudida = (0, 0)

        # --- Personaje: una copia propia, el jugador real no se toca ---
        color = color or (personaje.color if personaje is not None else (90, 170, 255))
        volumen = personaje.volumen_efectos if personaje is not None else 1.0
        self._actor = PersonajeHumanoide(0, 0, color, volumen)
        self._actor.euforico = euforico
        self._actor.direccion = personaje.direccion if personaje is not None else 1
        self._actor.rect.midbottom = (_ANCHO_SPRITE // 2, _ALTO_SPRITE // 2 + 60)
        self._sprite = pygame.Surface((_ANCHO_SPRITE, _ALTO_SPRITE), pygame.SRCALPHA)
        self._con_mascara = hasattr(pygame, "mask") and hasattr(
            pygame.mask.Mask, "to_surface"
        )

        if posicion is None and personaje is not None:
            posicion = personaje.rect.center
        if posicion is None:
            posicion = (ancho / 2, alto / 2)
        self._inicio = (
            min(max(posicion[0], ancho * 0.1), ancho * 0.9),
            min(max(posicion[1], alto * 0.1), alto * 0.9),
        )
        self._x, self._y = self._inicio
        self._escala = 1.0
        self._angulo = 0.0
        self._visible = True
        self._historial = deque(maxlen=HISTORIAL_ESTELA * 2)

        self._cap = None
        self._preparar(self._tam)
        if captura:
            self._crear_captura(superficie)

        self._chispas = [
            [
                random.uniform(0, _DOS_PI),
                self._rmax * random.uniform(0.08, 1.2),
                random.randrange(len(_NEON)),
            ]
            for _ in range(NUM_CHISPAS)
        ]

        self._sonido = None
        if sonido:
            self._sonido = PersonajeHumanoide._crear_sonido(820, 1.3, 1.0, 45, ruido=0.12)
            if self._sonido is not None:
                self._sonido.set_volume(self._actor.volumen_efectos * 0.10)
                self._sonido.play()

        self._mover_personaje(0.0)

    # ------------------------------------------------------------------
    @classmethod
    def precalentar(cls, superficie):
        """Opcional: construye de antemano los datos pesados (mapas del
        túnel, viñeta y sonido) para que la primera animación arranque sin
        tirón. Llamar una vez al cargar el juego."""
        _, w, h = _geometria(superficie.get_size())
        W, H = w + 2 * MARGEN, h + 2 * MARGEN
        _obtener_mapa(W, H, 0)
        _obtener_mapa(W, H, 1)
        _obtener_vineta(W, H)
        PersonajeHumanoide._crear_sonido(820, 1.3, 1.0, 45, ruido=0.12)

    def _preparar(self, tam):
        """(Re)crea las superficies internas para un tamaño de pantalla."""
        self._tam = tam
        f, w, h = _geometria(tam)
        W, H = w + 2 * MARGEN, h + 2 * MARGEN
        self._f, self._w, self._h = f, w, h
        self._dim = (W, H)
        self._centro = (W // 2, H // 2)
        self._rmax = math.hypot(W / 2, H / 2)
        self._unidad = max(0.75, tam[1] / 720)
        self._bases = tuple(
            _superficie_indexada(_obtener_mapa(W, H, v), W, H) for v in (0, 1)
        )
        self._buf = _convertir(pygame.Surface((W, H)))
        self._tmp = _convertir(pygame.Surface((W, H)))
        self._ampliada = _convertir(pygame.Surface((W * f, H * f)))
        self._vineta = _convertir(_obtener_vineta(W, H), _CK)
        self._cap = None  # al cambiar de tamaño se pierde la captura

    def _crear_captura(self, superficie):
        """El último fotograma del juego, pixelado, tapando el vórtice."""
        f, w, h = self._f, self._w, self._h
        W, H = self._dim
        pequena = pygame.transform.scale(superficie, (w, h))
        cap = pygame.Surface((W, H))
        cap.fill(_CK)
        cap.blit(pequena, (MARGEN, MARGEN))
        self._cap = _convertir(cap, _CK)
        cx = int(self._inicio[0] / f) + MARGEN
        cy = int(self._inicio[1] / f) + MARGEN
        self._iris_c = (cx, cy)
        self._iris_max = max(
            math.hypot(cx - ex, cy - ey)
            for ex in (MARGEN, MARGEN + w)
            for ey in (MARGEN, MARGEN + h)
        ) + 4

    # ------------------------------------------------------------------
    @property
    def terminada(self):
        return self.t >= self.duracion_total

    @property
    def progreso(self):
        """0.0 al empezar, 1.0 al terminar."""
        return min(1.0, self.t / self.duracion_total)

    def omitir(self):
        """Salta al final (por ejemplo, si el jugador pulsa una tecla)."""
        self.t = self.duracion_total

    # ------------------------------------------------------------------
    # Lógica
    # ------------------------------------------------------------------
    def actualizar(self, dt=None):
        """Avanza la animación. ``dt`` en segundos; si es None se mide solo."""
        if dt is None:
            ahora = pygame.time.get_ticks()
            dt = 1 / 60 if self._ultimo_tick is None else (ahora - self._ultimo_tick) / 1000.0
            self._ultimo_tick = ahora
        dt = max(0.0, min(float(dt), 0.05))
        if self.terminada:
            return
        self.t = min(self.t + dt, self.duracion_total)
        self._cuadro += 1

        p = min(1.0, self.t / self._duracion_caida)
        qf = self._progreso_final()

        # Latido: cada vez más rápido. En cada uno, golpe, glitch y cambios.
        self._cuenta_latido -= dt
        if self._cuenta_latido <= 0:
            self._latido(p)
            avance = min(1.0, p + qf)
            self._cuenta_latido += LATIDO_INICIAL + (LATIDO_FINAL - LATIDO_INICIAL) * avance
        self._pulso = max(0.0, self._pulso - dt * 4.5)
        self._glitch = max(0.0, self._glitch - dt)
        if self._destello_sprite > 0:
            self._destello_sprite -= 1

        # El vórtice se acelera durante la caída y se desboca en el final.
        self._fase += (70 + 330 * p ** 1.4 + 700 * qf + 500 * self._pulso) * dt
        self._giro += (1.2 + 2.4 * p + 3.0 * qf) * dt
        self._anillos += (0.35 + 1.1 * p + 1.5 * qf) * dt

        # Chispas: convergen al centro girando.
        k = math.exp(-(1.4 + 1.0 * p) * dt)
        giro_chispa = (0.9 + 1.0 * p) * dt
        for c in self._chispas:
            c[0] += giro_chispa
            c[1] *= k
            if c[1] < self._rmax * 0.07:
                c[0] = random.uniform(0, _DOS_PI)
                c[1] = self._rmax * random.uniform(0.9, 1.2)
                c[2] = random.randrange(len(_NEON))

        # Sacudida de cámara (en píxeles de la superficie interna).
        amp = min(MARGEN - 1, 3.0 * self._pulso + 0.8 * p + 1.2 * qf)
        self._sacudida = (
            int(round(random.uniform(-amp, amp))),
            int(round(random.uniform(-amp, amp))),
        )

        self._mover_personaje(dt)
        self._animar_actor(dt)

    def _latido(self, p):
        """Cada latido: golpe, y de vez en cuando nueva paleta / otro túnel."""
        self._latidos += 1
        n = self._latidos
        self._pulso = 1.0
        if n % (4 if REDUCIR_PARPADEO else 2) == 0:
            self._tema = (self._tema + 1) % len(_PALETAS)
        if n % 4 == 2:
            self._mapa = 1 - self._mapa
        if n > 1:
            W, H = self._dim
            self._glitch = 0.12
            self._tiras = [
                (
                    random.randrange(H),
                    random.randint(2, 7),
                    random.choice((-1, 1)) * random.randint(3, 14),
                )
                for _ in range(random.randint(2, 5))
            ]
            if not REDUCIR_PARPADEO:
                self._destello_sprite = 2

    def _progreso_final(self):
        return max(0.0, (self.t - self._duracion_caida) / DURACION_FINAL)

    def _mover_personaje(self, dt):
        """Trayectoria: viaja al centro (crece) y luego orbita en espiral,
        temblando, mientras se encoge y gira como loco hasta desaparecer."""
        ancho, alto = self._tam
        cx, cy = ancho / 2, alto / 2
        p = min(1.0, self.t / self._duracion_caida)
        giro = 0.0
        if p >= 1.0:
            self._visible = False
            if self._historial:
                self._historial.popleft()
            return
        if p < _P_ACERCAR:
            q = p / _P_ACERCAR
            e = q * q * (3 - 2 * q)
            x = self._inicio[0] + (cx - self._inicio[0]) * e
            y = self._inicio[1] + (cy - self._inicio[1]) * e
            escala = 1.0 + 0.9 * e
            visible = True
        else:
            q = (p - _P_ACERCAR) / (1 - _P_ACERCAR)
            self._ang_orbita += (3.0 + 4.0 * q) * dt
            radio = 0.2 * min(ancho, alto) * math.sin(math.pi * q) ** 0.8
            radio *= 1.0 + 0.12 * math.sin(self.t * 23.0)
            x = cx + math.cos(self._ang_orbita) * radio
            y = cy + math.sin(self._ang_orbita) * radio * 0.75
            escala = 1.9 * max(0.0, 1.0 - q ** 1.3) ** 1.2
            giro = (q ** 1.3) * 1440 * self._signo
            # Al final parpadea hasta desaparecer.
            visible = not (q > 0.8 and self._cuadro % 3 == 0)
        escala *= 1.0 + 0.16 * self._pulso
        self._x, self._y = x, y
        self._escala = max(0.02, escala) * self._unidad
        self._angulo = 25 * math.sin(self.t * 9.0) + giro
        self._visible = visible and escala > 0.05
        self._historial.append((x, y))

    def _animar_actor(self, dt):
        """Pose de caída libre: brazos y piernas pedaleando, pelo al viento."""
        a = self._actor
        t = self.t
        a.en_suelo = False
        a.muriendo = False
        a.girando = False
        a.pose_aire = 1.0
        # Alternar "subiendo/bajando" cambia piernas, brazos y pelo: pedaleo.
        a.vel_y = -6.0 if int(t / 0.10) % 2 else 14.0
        a.vel_x = math.sin(t * 7.0) * 3.0
        a.balanceo_actual = math.sin(t * 15.0) * 9.0
        a.inclinacion_actual = math.sin(t * 8.0) * 4.0
        a.escala_y = 1.0 + 0.09 * math.sin(t * 12.0)
        a.tiempo_animacion += dt * 10.0  # solo hace respirar el halo

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------
    def dibujar(self, superficie):
        """Dibuja el fotograma actual sobre ``superficie``."""
        if superficie.get_size() != self._tam:
            self._preparar(superficie.get_size())
        self._pintar_fondo(superficie)
        self._pintar_personaje(superficie)

    def _pintar_fondo(self, destino):
        buf = self._buf
        W, H = self._dim
        cx, cy = self._centro
        rmax = self._rmax
        f = self._f
        draw = pygame.draw
        cos, sin = math.cos, math.sin
        paleta = _PALETAS[self._tema]
        oscuro = _TEMAS[self._tema][1]
        n_neon = len(_NEON)

        # 1) Túnel: solo se rota la paleta (palette cycling).
        corte = int(self._fase) % 256
        base = self._bases[self._mapa]
        base.set_palette(paleta[corte:] + paleta[:corte])
        buf.blit(base, (0, 0))

        # 2) Rayas de velocidad oscuras, girando al revés.
        r0, r1 = rmax * 0.08, rmax * 1.1
        for k in range(NUM_RAYAS):
            a = -self._giro * 0.5 + k * _DOS_PI / NUM_RAYAS
            ca, sa = cos(a), sin(a)
            draw.line(
                buf, oscuro,
                (int(cx + ca * r0), int(cy + sa * r0)),
                (int(cx + ca * r1), int(cy + sa * r1)),
                2 if k % 3 == 0 else 1,
            )

        # 3) Anillos poligonales (cuadrados, hexágonos, octógonos) que se
        #    cierran hacia el centro girando a distinta velocidad.
        for k in range(NUM_ANILLOS):
            fase = (self._anillos + k / NUM_ANILLOS) % 1.0
            r = rmax * 1.1 * (1.0 - fase) ** 2.2
            if r < 3:
                continue
            lados = (4, 6, 8, 4, 6, 8)[k % 6]
            a0 = self._giro * (1.0 + 0.15 * k) * (1 if k % 2 else -1)
            pts = [
                (int(cx + cos(a0 + _DOS_PI * i / lados) * r),
                 int(cy + sin(a0 + _DOS_PI * i / lados) * r))
                for i in range(lados)
            ]
            color = _NEON[(k * 3 + self._cuadro // 3) % n_neon]
            draw.polygon(buf, color, pts, 2 if r > rmax * 0.3 else 1)

        # 4) Chispas que se precipitan al centro (estela + cabeza cuadrada
        #    o cruz de 5 píxeles cuando están cerca del borde).
        lejos, medio = rmax * 0.55, rmax * 0.28
        for ang, r, ci in self._chispas:
            color = _NEON[(ci + self._cuadro // 2) % n_neon]
            x, y = int(cx + cos(ang) * r), int(cy + sin(ang) * r)
            r_cola = r * 1.22
            draw.line(
                buf, color,
                (int(cx + cos(ang - 0.10) * r_cola), int(cy + sin(ang - 0.10) * r_cola)),
                (x, y),
            )
            if r > lejos:
                buf.fill((255, 255, 255), (x - 1, y, 3, 1))
                buf.fill((255, 255, 255), (x, y - 1, 1, 3))
            elif r > medio:
                buf.fill(color, (x, y, 2, 2))
            else:
                buf.set_at((x, y), (255, 255, 255))  # fuera de la superficie se ignora

        # 5) Glitch: tiras horizontales desplazadas en cada latido.
        if self._glitch > 0 and self._tiras:
            self._tmp.blit(buf, (0, 0))
            for y0, alto, dx in self._tiras:
                buf.blit(self._tmp, (dx, y0), pygame.Rect(0, y0, W, alto))

        # 6) Viñeta con tramado: el centro se hunde en negro.
        buf.blit(self._vineta, (0, 0))

        # 7) Pozo: núcleo negro con anillos que laten.
        rp = max(2, int(rmax * 0.07 * (1.0 + 0.3 * self._pulso)))
        draw.circle(buf, (0, 0, 0), (cx, cy), rp)
        draw.circle(buf, _NEON[(self._cuadro // 2) % n_neon], (cx, cy), rp + 1, 1)
        draw.circle(buf, _NEON[(self._cuadro // 2 + 5) % n_neon], (cx, cy), rp + 4, 1)

        # 8) El mundo del juego (pixelado) se deshace con un iris que se
        #    abre desde el personaje.
        if self._cap is not None:
            e = min(1.0, self.t / DURACION_ENTRADA)
            if e >= 1.0:
                self._cap = None
            else:
                rad = int(self._iris_max * e ** 0.85)
                if rad > 0:
                    draw.circle(self._cap, _CK, self._iris_c, rad)
                buf.blit(self._cap, (0, 0))
                draw.circle(
                    buf, _NEON[(self._cuadro * 2) % n_neon],
                    self._iris_c, rad + 1, 2,
                )

        # 9) Final: onda de choque, destello y cierre de iris en negro.
        qf = self._progreso_final()
        if qf > 0:
            for k in range(3):
                rad = int(qf * rmax * (1.25 - 0.22 * k))
                if rad > 1:
                    color = (255, 255, 255) if k % 2 == 0 else _NEON[(self._cuadro + k * 4) % n_neon]
                    draw.circle(buf, color, (cx, cy), rad, 3 if k == 0 else 2)
            if qf < 0.3 and not REDUCIR_PARPADEO:
                r_flash = int(rmax * 0.25 * (1 - qf / 0.3))
                if r_flash > 0:
                    draw.circle(buf, (255, 255, 255), (cx, cy), r_flash)
            if qf > 0.4:
                e = min(1.0, (qf - 0.4) / 0.6)
                e = e * e * (3 - 2 * e)
                self._cerrar_iris(int(rmax * 1.15 * (1.0 - e)))

        # 10) Ampliar todo de golpe (vecino más cercano) con la sacudida.
        ampliada = self._ampliada
        try:
            pygame.transform.scale(buf, (W * f, H * f), ampliada)
        except (ValueError, TypeError, pygame.error):
            ampliada = pygame.transform.scale(buf, (W * f, H * f))
        sx, sy = self._sacudida
        destino.blit(ampliada, ((sx - MARGEN) * f, (sy - MARGEN) * f))

    def _cerrar_iris(self, rad):
        """Todo lo que queda fuera de ``rad`` píxeles del centro, en negro."""
        buf = self._buf
        if rad <= 0:
            buf.fill((0, 0, 0))
            return
        grande = int(self._rmax * 1.3) + 2
        ancho = grande - rad - 2
        if ancho > 0:
            pygame.draw.circle(buf, (0, 0, 0), self._centro, grande, ancho)
        pygame.draw.circle(
            buf, _NEON[(self._cuadro * 2) % len(_NEON)], self._centro, rad + 2, 2
        )

    def _pintar_personaje(self, destino):
        f = self._f
        sx, sy = self._sacudida
        dx, dy = sx * f, sy * f

        def ajustar(x, y):
            """Pega la posición a la rejilla de píxeles gordos del fondo."""
            return int(round(x / f)) * f + dx, int(round(y / f)) * f + dy

        if not self._visible:
            # Quedan las cuentas de la estela encogiéndose.
            n = len(self._historial)
            for i, (hx, hy) in enumerate(list(self._historial)[::2]):
                lado = max(f, int(18 * self._unidad * (i + 1) / (n + 1)) // f * f)
                color = _NEON[(self._cuadro * 2 + i * 3) % len(_NEON)]
                px, py = ajustar(hx, hy)
                destino.fill(color, (px - lado // 2, py - lado // 2, lado, lado))
            return

        sprite = self._sprite
        sprite.fill((0, 0, 0, 0))
        self._actor.dibujar(sprite)

        # Rotar en pasos de 15° y escalar en pasos: movimiento "de pixel art".
        angulo = int(round(self._angulo / 15.0)) * 15
        girado = pygame.transform.rotate(sprite, angulo)
        s = max(1 / 12, round(self._escala * 12) / 12)
        nuevo = (max(1, int(girado.get_width() * s)), max(1, int(girado.get_height() * s)))
        imagen = pygame.transform.scale(girado, nuevo)  # nunca smoothscale
        px, py = ajustar(self._x, self._y)
        rect = imagen.get_rect(center=(px, py))

        blanca = None
        if self._con_mascara:
            try:
                mascara = pygame.mask.from_surface(imagen, 40)
                blanca = mascara.to_surface(
                    setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0)
                )
            except (AttributeError, TypeError, ValueError, pygame.error):
                self._con_mascara = False
                blanca = None

        if blanca is not None:
            # Estela de siluetas de colores que se encogen hacia atrás.
            historial = list(self._historial)[::2]
            n = len(historial)
            for i, (hx, hy) in enumerate(historial):
                k = 0.45 + 0.5 * (i + 1) / (n + 1)
                tam = (max(1, int(blanca.get_width() * k)), max(1, int(blanca.get_height() * k)))
                cuenta = pygame.transform.scale(blanca, tam)
                color = _NEON[(self._cuadro * 2 + i * 3) % len(_NEON)]
                cuenta.fill(color + (255,), special_flags=pygame.BLEND_RGBA_MULT)
                bx, by = ajustar(hx, hy)
                destino.blit(cuenta, cuenta.get_rect(center=(bx, by)))

            # Contorno negro grueso (un píxel gordo del fondo, o casi).
            grosor = max(2, f // 2 + 1)
            negra = blanca.copy()
            negra.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
            for ox, oy in (
                (-grosor, 0), (grosor, 0), (0, -grosor), (0, grosor),
                (-grosor, -grosor), (grosor, -grosor), (-grosor, grosor), (grosor, grosor),
            ):
                destino.blit(negra, rect.move(ox, oy))

        if blanca is not None and self._destello_sprite > 0:
            destino.blit(blanca, rect)  # destello blanco del golpe
        else:
            destino.blit(imagen, rect)