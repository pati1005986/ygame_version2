"""Animación de entrada del modo infinito (todo en un solo archivo).

- A color (la paleta del pasillo cambia de tono sin parar).
- El pasillo y la carrera continúan hasta que termina la secuencia.
- Protagonista: ``PersonajeLoco``, de frente a la cámara y corriendo como
  loco; el pasillo se aleja detrás de él.
- Efecto grunge de película sucia (``EfectoGrunge``) sobre todo el fotograma.
- Secuencia: apertura en iris, título que rebota, zoom y barras de cine.
- Empalme con el fondo del modo infinito: detrás de la intro corre el
  MISMO fondo que usa el juego (``fondo.dibujar_fondo_infinito_gen``), el
  pasillo se desvanece con la distancia hasta abrirse a ese fondo, y al
  final pasillo, personaje, viñeta y grunge se funden con él, de modo que
  el último fotograma de la intro es el primero del juego (sin corte).

La clase ``IntroInfinito`` dibuja en una superficie existente y no toma
control de la ventana ni del bucle principal. Este archivo reúne lo que
antes estaba en intro.py, personaje_loco.py y grunge.py.

Preview: ``python intro.py`` (R reinicia, G alterna el grunge, Espacio brinca).
"""
import colorsys
import math
import os
import random
from functools import lru_cache

import pygame

# Fondo real del modo infinito. Si no se puede importar (p. ej. al previsualizar
# este archivo solo, sin ``plataformas``), se usa un degradado del mismo color.
try:
    import fondo as _fondo
except Exception:  # noqa: BLE001 - cualquier fallo de import cae al respaldo
    _fondo = None



# ----------------------------------------------------------------------
# Efecto grunge: postproceso de película sucia y castigada
# ----------------------------------------------------------------------

class EfectoGrunge:
    CUADROS_ESTADO = 3

    def __init__(self, ancho=640, alto=480, intensidad=1.0, semilla=None):
        self.ancho, self.alto = ancho, alto
        self.intensidad = max(0.0, intensidad)
        self._rnd = random.Random(semilla)
        self._cuadro = 0
        self._estado = {}
        k = min(1.5, self.intensidad)
        self.grano_claro = [self._textura_grano(38 * k) for _ in range(4)]
        self.grano_oscuro = [self._textura_grano(46 * k) for _ in range(4)]
        self.suciedad = self._crear_suciedad(k)
        self.borde = self._crear_borde(k)
        self._nuevo_estado()

    # ------------------------------------------------------------------
    # Texturas (se generan una sola vez)
    # ------------------------------------------------------------------
    @staticmethod
    def _convertir(superficie):
        return superficie.convert() if pygame.display.get_surface() else superficie

    def _textura_grano(self, tope):
        """Ruido gris a media resolución, ampliado (grano grueso)."""
        w, h = self.ancho // 2, self.alto // 2
        tabla = bytes(int(tope * (v / 255.0) ** 1.5) for v in range(256))
        datos = os.urandom(w * h).translate(tabla)
        buf = bytearray(w * h * 3)
        buf[0::3] = datos
        buf[1::3] = datos
        buf[2::3] = datos
        pequena = pygame.image.frombuffer(bytes(buf), (w, h), "RGB")
        return self._convertir(pygame.transform.scale(pequena, (self.ancho, self.alto)))

    def _crear_suciedad(self, k):
        """Textura que se MULTIPLICA sobre la imagen: manchas, chorreras y
        un tinte cálido-sucio."""
        w, h, rnd = self.ancho, self.alto, self._rnd
        base = pygame.Surface((w, h))
        base.fill((255, 255, 255))
        capa = pygame.Surface((w, h), pygame.SRCALPHA)
        for _ in range(150):
            r = rnd.randint(8, 90)
            x, y = rnd.randint(0, w), rnd.randint(0, h)
            g = rnd.randint(40, 170)
            alfa = rnd.randint(5, 12) * k
            blob = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
            for anillo in range(4):  # centro más opaco: bordes suaves
                radio = max(1, int(r * (1 - anillo * 0.25)))
                pygame.draw.circle(
                    blob, (g, int(g * 0.9), int(g * 0.7), int(alfa * (anillo + 1))),
                    (r, r), radio,
                )
            capa.blit(blob, (x - r, y - r))
        for _ in range(45):  # chorreras de mugre que bajan
            x = rnd.randint(0, w)
            largo = rnd.randint(40, 320)
            pygame.draw.line(
                capa, (60, 45, 30, int(rnd.randint(18, 50) * k)),
                (x, 0), (x + rnd.randint(-6, 6), largo), rnd.randint(1, 3),
            )
        base.blit(capa, (0, 0))
        base.fill((246, 238, 216), special_flags=pygame.BLEND_RGB_MULT)
        return self._convertir(base)

    def _crear_borde(self, k):
        """Marco oscuro con el contorno interior rasgado."""
        w, h, rnd = self.ancho, self.alto, self._rnd
        degradado = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(34):
            pygame.draw.rect(
                degradado, (0, 0, 0, int(120 * (1 - i / 34) ** 2)),
                (i, i, w - 2 * i, h - 2 * i), 1,
            )
        marco = pygame.Surface((w, h), pygame.SRCALPHA)
        marco.fill((18, 12, 14, 240))

        def paseo(largo, inicio):
            prof, pos = inicio, 0
            while pos <= largo:
                prof = max(2, min(22, prof + rnd.randint(-5, 5)))
                yield pos, prof
                pos += rnd.randint(5, 16)

        puntos = []
        puntos += [(x, d) for x, d in paseo(w, 8)]
        puntos += [(w - d, y) for y, d in paseo(h, 8)]
        puntos += [(w - x, h - d) for x, d in paseo(w, 8)]
        puntos += [(d, h - y) for y, d in paseo(h, 8)]
        pygame.draw.polygon(marco, (0, 0, 0, 0), puntos)
        degradado.blit(marco, (0, 0))
        degradado.set_alpha(int(255 * min(1.0, k)))
        return degradado

    # ------------------------------------------------------------------
    # Estado aleatorio que se renueva cada pocos fotogramas
    # ------------------------------------------------------------------
    def _nuevo_estado(self):
        r, w, h = self._rnd, self.ancho, self.alto
        k = min(1.5, self.intensidad)
        sacudida = 7 if r.random() < 0.06 else 2
        glitch = None
        if r.random() < 0.10 * k:
            alto = r.randint(12, 44)
            glitch = (r.randint(0, h - alto), alto, r.choice((-1, 1)) * r.randint(8, 40))
        rayas = [
            (
                r.randint(0, w), r.randint(0, h - 120), r.randint(90, 420),
                r.random() < 0.7, r.randint(1, 2),
            )
            for _ in range(r.choice((0, 0, 1, 1, 2, 3)))
        ]
        polvo = [
            (r.randint(0, w), r.randint(0, h), r.randint(1, 3), r.random() < 0.55)
            for _ in range(int(r.randint(8, 22) * k))
        ]
        pelos = []
        if r.random() < 0.25:
            x, y = r.randint(40, w - 40), r.randint(40, h - 40)
            pts = [(x, y)]
            for _ in range(5):
                x += r.randint(-14, 14)
                y += r.randint(-10, 18)
                pts.append((x, y))
            pelos.append(pts)
        self._estado = {
            "grano": (r.randrange(4), r.randrange(4)),
            "sacudida": (r.randint(-sacudida, sacudida), r.randint(-sacudida, sacudida)),
            "aberracion": max(1, int(round(k * (2 + r.random() * 1.6)))) + (4 if r.random() < 0.10 else 0),
            "glitch": glitch,
            "parpadeo": r.choice((0, 0, 0, 0, 0, 6, 10, 16, -8)),
            "rayas": rayas,
            "polvo": polvo,
            "pelos": pelos,
        }

    # ------------------------------------------------------------------
    # Aplicación
    # ------------------------------------------------------------------
    def aplicar(self, frame, t=0.0):
        """Aplica el efecto sobre ``frame`` (debe medir ancho x alto)."""
        if self.intensidad <= 0 or frame.get_size() != (self.ancho, self.alto):
            return frame
        if self._cuadro % self.CUADROS_ESTADO == 0:
            self._nuevo_estado()
        self._cuadro += 1
        e = self._estado
        k = min(1.5, self.intensidad)
        w, h = self.ancho, self.alto

        # 1. Temblor del proyector y franja desplazada
        frame.scroll(*e["sacudida"])
        if e["glitch"]:
            y0, alto, dx = e["glitch"]
            franja = frame.subsurface((0, y0, w, alto)).copy()
            frame.blit(franja, (dx, y0))

        # 2. Colores medio desteñidos
        if hasattr(pygame.transform, "grayscale"):
            gris = pygame.transform.grayscale(frame)
            gris.set_alpha(int(105 * min(1.0, k)))
            frame.blit(gris, (0, 0))

        # 3. Aberración cromática
        dx = e["aberracion"]
        rojo = frame.copy()
        rojo.fill((255, 0, 0), special_flags=pygame.BLEND_RGB_MULT)
        cian = frame.copy()
        cian.fill((0, 255, 255), special_flags=pygame.BLEND_RGB_MULT)
        frame.fill((0, 0, 0))
        frame.blit(cian, (-dx, 0), special_flags=pygame.BLEND_RGB_ADD)
        frame.blit(rojo, (dx, 0), special_flags=pygame.BLEND_RGB_ADD)

        # 4. Sombras aplastadas (más contraste)
        oscuro = frame.copy()
        oscuro.blit(frame, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        oscuro.set_alpha(int(100 * min(1.0, k)))
        frame.blit(oscuro, (0, 0))

        # 5. Mugre fija sobre la lente
        frame.blit(self.suciedad, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

        # 6. Grano de película
        frame.blit(self.grano_claro[e["grano"][0]], (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        frame.blit(self.grano_oscuro[e["grano"][1]], (0, 0), special_flags=pygame.BLEND_RGB_SUB)

        # 7. Parpadeo de exposición
        v = e["parpadeo"]
        if v > 0:
            frame.fill((v, v, v), special_flags=pygame.BLEND_RGB_ADD)
        elif v < 0:
            frame.fill((-v, -v, -v), special_flags=pygame.BLEND_RGB_SUB)

        # 8. Rayones, polvo y pelos
        rnd = self._rnd
        for x, y0, largo, clara, grosor in e["rayas"]:
            color = (225, 215, 190) if clara else (25, 18, 16)
            puntos = [(x + rnd.randint(-1, 1), y) for y in range(y0, y0 + largo, 40)]
            if len(puntos) > 1:
                pygame.draw.lines(frame, color, False, puntos, grosor)
        for x, y, tam, claro in e["polvo"]:
            color = (235, 230, 215) if claro else (20, 15, 15)
            pygame.draw.rect(frame, color, (x, y, tam, tam))
        for pts in e["pelos"]:
            pygame.draw.lines(frame, (18, 14, 12), False, pts, 1)

        # 9. Borde quemado y rasgado
        frame.blit(self.borde, (0, 0))
        return frame


# ----------------------------------------------------------------------
# Personaje frontal y desquiciado (independiente de personaje.py)
# ----------------------------------------------------------------------

BLANCO_OJO = (245, 245, 245)
ROJO_VENA = (205, 35, 45)
INTERIOR_BOCA = (110, 16, 40)
LENGUA = (236, 86, 120)
SUDOR = (205, 238, 255)


@lru_cache(maxsize=64)
def _tono(color_rgb, factor):
    """Oscurece/aclara un color RGB (cacheado: hay pocos valores)."""
    r, g, b = color_rgb
    return (
        max(0, min(255, int(r * factor))),
        max(0, min(255, int(g * factor))),
        max(0, min(255, int(b * factor))),
    )


class PersonajeLoco:
    ANCHO, ALTO = 220, 260          # lienzo interno
    CENTRO_X, PIE_Y = 110, 230      # ancla de los pies dentro del lienzo
    PIXEL = 4

    CADENCIA_QUIETO = 7.0           # rad/s de la fase de zancada
    CADENCIA_CARRERA = 20.0
    HERVIDO = 1 / 12                # el pelo y las pupilas "hierven" a 12 Hz

    def __init__(self, color):
        self.color = tuple(color[:3])
        self.corre = False
        self.ritmo = 0.0            # 0 quieto -> 1 a toda velocidad
        self.bob_actual = 0.0       # rebote vertical (px), útil para la cámara
        self.t = 0.0
        self.fase = 0.0
        self.espasmo = 0.0          # segundos restantes del ataque de locura
        self._prox_espasmo = 1.0
        self.salto = 0.0            # altura del brinco (px)
        self._v_salto = 0.0
        self.particulas = []
        self._acum_part = 0.0
        self._reloj_hervido = 0.0
        self._semilla = 0
        self._lienzos = [
            pygame.Surface((self.ANCHO, self.ALTO), pygame.SRCALPHA) for _ in range(2)
        ]
        self._turno = 0
        self._cabeza = pygame.Surface((96, 96), pygame.SRCALPHA)

    # ------------------------------------------------------------------
    # Lógica
    # ------------------------------------------------------------------
    def brincar(self):
        """Un brinco de loco (opcional, para pruebas o interacción)."""
        if self.salto <= 0:
            self._v_salto = 520.0
            self.salto = 0.001

    def actualizar(self, dt):
        dt = max(0.0, min(dt, 0.1))
        self.t += dt
        objetivo = 1.0 if self.corre else 0.0
        self.ritmo += (objetivo - self.ritmo) * min(1.0, dt * 6.0)

        cadencia = self.CADENCIA_QUIETO + (
            self.CADENCIA_CARRERA - self.CADENCIA_QUIETO
        ) * self.ritmo
        # Cadencia irregular: se desboca y se atranca.
        cadencia *= 1.0 + 0.18 * self.ritmo * math.sin(self.t * 3.7)
        self.fase += dt * cadencia
        vib = 0.3 + 0.7 * self.ritmo
        self.bob_actual = abs(math.sin(self.fase)) * 4.0 * vib

        if self.salto > 0:
            self._v_salto -= 1900.0 * dt
            self.salto += self._v_salto * dt
            if self.salto <= 0:
                self.salto = 0.0
                self._v_salto = 0.0

        if self.espasmo > 0:
            self.espasmo = max(0.0, self.espasmo - dt)
        elif self.ritmo > 0.6 and self.t >= self._prox_espasmo:
            self.espasmo = random.uniform(0.3, 0.55)
            self._prox_espasmo = self.t + random.uniform(0.7, 1.6)

        self._reloj_hervido += dt
        if self._reloj_hervido >= self.HERVIDO:
            self._reloj_hervido = 0.0
            self._semilla = random.randint(0, 1_000_000)

        # Sudor y saliva disparados desde la cabeza.
        self._acum_part += dt * (6 + 40 * self.ritmo)
        while self._acum_part >= 1.0:
            self._acum_part -= 1.0
            lado = random.choice((-1, 1))
            self.particulas.append(
                {
                    "x": self.CENTRO_X + lado * random.uniform(14, 24),
                    "y": self.PIE_Y - 72 - self.salto + random.uniform(-12, 10),
                    "vx": lado * random.uniform(60, 260),
                    "vy": random.uniform(-240, -20),
                    "vida": 0.55,
                }
            )
        vivas = []
        for q in self.particulas:
            q["x"] += q["vx"] * dt
            q["y"] += q["vy"] * dt
            q["vy"] += 900.0 * dt
            q["vida"] -= dt
            if q["vida"] > 0:
                vivas.append(q)
        self.particulas = vivas

    # ------------------------------------------------------------------
    # Primitivas de dibujo (bloques sobre la grilla, contorno grueso)
    # ------------------------------------------------------------------
    def _bloque(self, s, x, y, w, h, color):
        p = self.PIXEL
        pygame.draw.rect(
            s, color,
            (round(x / p) * p, round(y / p) * p,
             max(p, round(w / p) * p), max(p, round(h / p) * p)),
        )

    def _bloque_c(self, s, x, y, w, h, color, contorno):
        p = self.PIXEL
        rx, ry = round(x / p) * p, round(y / p) * p
        rw, rh = max(p, round(w / p) * p), max(p, round(h / p) * p)
        g = p // 2
        pygame.draw.rect(s, contorno, (rx - g, ry - g, rw + 2 * g, rh + 2 * g))
        pygame.draw.rect(s, color, (rx, ry, rw, rh))

    def _cadena(self, s, origen, segmentos, ancho, color, contorno):
        """Miembro hecho de sellos cuadrados a lo largo de segmentos.
        Cada segmento es (ángulo en grados medido desde "hacia abajo",
        positivo hacia la derecha de la pantalla; largo). Devuelve el
        extremo final."""
        p = self.PIXEL
        x, y = origen
        sellos = []
        for ang, largo in segmentos:
            a = math.radians(ang)
            dx, dy = math.sin(a), math.cos(a)
            pasos = max(1, int(largo / 2))
            for i in range(pasos):
                sellos.append((x + dx * largo * i / pasos, y + dy * largo * i / pasos))
            x += dx * largo
            y += dy * largo
        sellos.append((x, y))
        g = p // 2
        posiciones = [
            (round((sx - ancho / 2) / p) * p, round((sy - ancho / 2) / p) * p)
            for sx, sy in sellos
        ]
        for rx, ry in posiciones:
            pygame.draw.rect(s, contorno, (rx - g, ry - g, ancho + 2 * g, ancho + 2 * g))
        for rx, ry in posiciones:
            pygame.draw.rect(s, color, (rx, ry, ancho, ancho))
        return x, y

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------
    def dibujar(self, superficie, centro_x=None, pie_y=None):
        """Dibuja al personaje con los pies en (centro_x, pie_y)."""
        if centro_x is None:
            centro_x = self.CENTRO_X
        if pie_y is None:
            pie_y = self.PIE_Y
        actual = self._lienzos[self._turno]
        previo = self._lienzos[1 - self._turno]
        actual.set_alpha(255)
        actual.fill((0, 0, 0, 0))
        self._pintar(actual)

        dx, dy = centro_x - self.CENTRO_X, pie_y - self.PIE_Y
        if self.ritmo > 0.05:
            # Fantasma del fotograma anterior: sensación de velocidad.
            previo.set_alpha(int(95 * self.ritmo))
            superficie.blit(previo, (dx, dy))
        superficie.blit(actual, (dx, dy))
        self._turno = 1 - self._turno

    def _pintar(self, l):
        p = self.PIXEL
        t, f = self.t, self.fase
        rnd = random.Random(self._semilla)
        vib = 0.3 + 0.7 * self.ritmo
        espasmo = self.espasmo > 0

        # Paleta monocromática; el color "chisporrotea" en 3 pasos.
        m = 1.10 + 0.05 * (int(t * 11) % 3)
        brillo = _tono(self.color, 1.75 * m)
        claro = _tono(self.color, 1.45 * m)
        base = _tono(self.color, 1.0 * m)
        medio = _tono(self.color, 0.8 * m)
        oscuro = _tono(self.color, 0.62)
        muy_oscuro = _tono(self.color, 0.35)
        contorno = _tono(self.color, 0.16)

        cx = self.CENTRO_X
        base_y = self.PIE_Y - round(self.salto)
        bob = round(self.bob_actual)
        cadera_y = base_y - 26 - bob

        # --- Sombra de contacto (se queda en el suelo al brincar) ---
        ancho_s = max(24, int(72 - self.salto * 0.35 - bob * 2))
        sombra = pygame.Surface((ancho_s, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(sombra, (0, 0, 0, 100), sombra.get_rect())
        l.blit(sombra, sombra.get_rect(center=(cx, self.PIE_Y + 2)))

        # --- Piernas: levantan la rodilla hacia la cámara, una y una ---
        for lado in (-1, 1):
            s = math.sin(f + (0.0 if lado < 0 else math.pi))
            levanta = 1.0 if self.salto > 0 else max(0.0, s)
            a1 = lado * (6 + 55 * levanta + (12 if espasmo else 0))
            a2 = lado * (6 - 65 * levanta)
            ex, ey = self._cadena(
                l, (cx + lado * 9, cadera_y), ((a1, 10), (a2, 10)), 8, oscuro, contorno
            )
            ancho_pie = 12 + 8 * levanta  # más grande cuanto más cerca de la cámara
            self._bloque_c(l, ex - ancho_pie / 2, ey - 2, ancho_pie, 8, muy_oscuro, contorno)

        # --- Torso ---
        tx = cx + round(math.sin(f) * 5 * vib)
        torso_y = cadera_y - 28
        self._bloque_c(l, tx - 18, torso_y, 36, 28, base, contorno)
        self._bloque(l, tx + 10, torso_y, 8, 28, oscuro)
        for i in range(4):  # franja en zigzag, a lo punk
            self._bloque(l, tx - 16 + i * 8, torso_y + 8 + (4 if i % 2 else 0), 8, 4, muy_oscuro)
        self._bloque(l, tx - 18, cadera_y - 4, 36, 4, muy_oscuro)
        self._bloque(l, tx - 4, cadera_y - 4, 8, 4, brillo)

        # --- Brazos: bombean al correr; en el espasmo giran como molino ---
        for lado in (-1, 1):
            desfase = 0.0 if lado < 0 else math.pi
            if espasmo:
                a1 = math.degrees(t * 12 * lado) + (0 if lado < 0 else 180)
                a2 = a1 + lado * 25 * math.sin(t * 30)
            else:
                a1 = lado * (70 + 60 * vib * math.sin(f + desfase)) + rnd.uniform(-8, 8) * vib
                a2 = a1 + lado * (-30 + 60 * vib * math.sin(2 * f + desfase + 1.0))
            hx, hy = self._cadena(
                l, (tx + lado * 19, torso_y + 8), ((a1, 12), (a2, 12)), 8, claro, contorno
            )
            self._bloque_c(l, hx - 6, hy - 6, 12, 12, claro, contorno)

        # --- Cabeza (con cuello fijo al torso y sacudidas propias) ---
        cabeza = self._pintar_cabeza(rnd, claro, brillo, medio, contorno)
        angulo = math.sin(t * 21) * 6 * vib + math.sin(f) * 5 * vib + rnd.uniform(-3, 3) * vib
        if espasmo:
            angulo += math.sin(t * 38) * 16
        rad = math.radians(angulo)
        cuello_x = tx
        cuello_y = torso_y + 4 + round(math.sin(t * 26) * 2 * vib)
        centro = (cuello_x - 24 * math.sin(rad), cuello_y - 24 * math.cos(rad))
        rot = pygame.transform.rotate(cabeza, angulo)
        l.blit(rot, rot.get_rect(center=(round(centro[0]), round(centro[1]))))

        # --- Sudor y saliva ---
        for q in self.particulas:
            self._bloque_c(l, q["x"], q["y"], p, p, SUDOR, contorno)

    def _pintar_cabeza(self, rnd, claro, brillo, medio, contorno):
        p = self.PIXEL
        t = self.t
        h = self._cabeza
        h.fill((0, 0, 0, 0))
        hx, hy, hw, hh = 26, 36, 44, 36
        cxh = hx + hw // 2
        espasmo = self.espasmo > 0

        self._bloque_c(h, hx, hy, hw, hh, claro, contorno)
        self._bloque(h, hx + 4, hy + 4, 8, 4, brillo)

        # Pelo electrizado: 9 mechones que se abren hacia fuera.
        for i in range(9):
            alto = 2 + (4 - abs(i - 4)) // 2 + rnd.randint(0, 3)
            for nivel in range(alto):
                dx = round((i - 4) * nivel * 0.9)
                self._bloque(h, hx + 4 + 4 * i + dx, hy - (nivel + 1) * p, p, p, contorno)

        # Ojos de distinto tamaño, con venas, y la mirada clavada en cámara.
        ojos = ((hx + 4, hy + 8, 12), (hx + hw - 4 - 16, hy + 6, 16))
        for idx, (ex, ey, w) in enumerate(ojos):
            self._bloque_c(h, ex, ey, w, w, BLANCO_OJO, contorno)
            for vx, vy in ((0, 4), (w - 4, w - 8), (4, w - 4)):
                self._bloque(h, ex + vx, ey + vy, 4, 4, ROJO_VENA)
            self._bloque(h, ex, ey + w, w, p, medio)  # ojera
            if espasmo:  # bizco
                dx, dy = (p if idx == 0 else -p), 0
            elif rnd.random() < 0.3:  # tic: la pupila se escapa un instante
                dx, dy = rnd.choice((-p, 0, p)), rnd.choice((-p, 0, p))
            else:
                dx = dy = 0
            self._bloque(h, ex + (w - p) // 2 + dx, ey + (w - p) // 2 + dy, p, p, contorno)

            # Cejas furiosas, inclinadas hacia el centro, que saltan.
            sube = rnd.choice((0, 0, p))
            for k in range(w // 4 + 1):
                bx = ex - 2 + 4 * k if idx == 0 else ex + w + 2 - 4 - 4 * k
                self._bloque(h, bx, ey - 8 - sube + 2 * k, p, p, contorno)

        # Boca: carcajada enorme con dientes, lengua y baba.
        mw = 28
        mx = cxh - mw // 2
        my = hy + hh - 10
        abierta = int(t * 9) % 2 == 0
        mh = 16 if espasmo else (12 if abierta else 8)
        self._bloque_c(h, mx, my, mw, mh, INTERIOR_BOCA, contorno)
        self._bloque(h, mx + 2, my, mw - 4, 4, BLANCO_OJO)
        self._bloque(h, mx + 4, my + 4, 4, 4, BLANCO_OJO)
        self._bloque(h, mx + mw - 8, my + 4, 4, 4, BLANCO_OJO)
        if mh >= 12:
            self._bloque(h, mx + 6, my + mh - 4, mw - 12, 4, BLANCO_OJO)
            lengua_x = mx + 8 + round(math.sin(t * 20) * 4)
            self._bloque_c(h, lengua_x, my + mh - 8, 12, 12, LENGUA, contorno)
        self._bloque(h, mx - 4, my - 4, 4, 4, contorno)        # hoyuelos
        self._bloque(h, mx + mw, my - 4, 4, 4, contorno)
        baba = 4 + 4 * int(2 + 2 * math.sin(t * 5))
        self._bloque_c(h, mx + mw - 6, my + mh, 4, baba, SUDOR, contorno)

        # Rayitas de vibración alrededor de la cabeza.
        cuadro = int(t * 14)
        for i, grados in enumerate((-165, -135, -45, -15, 15, 165, 135, 45)):
            if (cuadro + i) % 3 == 0:
                continue
            a = math.radians(grados)
            r = hw / 2 + 6 + p * ((cuadro + i) % 2)
            x = cxh + math.cos(a) * r
            y = hy + hh / 2 + math.sin(a) * r * 0.9
            if abs(math.cos(a)) > abs(math.sin(a)):
                self._bloque(h, x - p, y, p * 2, p, contorno)
            else:
                self._bloque(h, x, y - p, p, p * 2, contorno)
        return h


# ----------------------------------------------------------------------
# Intro
# ----------------------------------------------------------------------

ANCHO, ALTO = 640, 480
FPS = 60
ESCALA_PERSONAJE = 2.3
# -1: el personaje corre hacia la cámara y el pasillo se aleja;
#  1: la cámara avanza por el pasillo (como antes).
SENTIDO_PASILLO = -1
PIE_Y = 440

N_SEGMENTOS = 24
FILAS = 6
MEDIO_ANCHO = 380
ALTO_TECHO = 260
ALTO_SUELO = 270
JITTER = 1.2
CUADROS_HERVIDO = 5             # las líneas "hierven" a 12 Hz; el movimiento va a 60 fps

COLOR_PERSONAJE = (238, 108, 60)
NIEBLA = (255, 246, 214)
NIEBLA_PASILLO = (226, 160, 255)   # tinte lila de la lejanía (casa con el fondo)
CONTORNO = (22, 10, 36)

# Valores del fondo del modo infinito (se leen de fondo.py para no desincronizarse).
HUE_FONDO = getattr(_fondo, "_HUE_FONDO_INFINITO", 0.83)
VEL_FONDO = getattr(_fondo, "_VELOCIDAD_FONDO_INFINITO", 2.4)
NIVEL_FONDO = getattr(_fondo, "_NIVEL_FONDO_INFINITO", 5)

# Línea de tiempo de la intro (segundos)
T_ARRANQUE = 0.5      # el personaje empieza a correr
T_IRIS = (0.15, 1.5)  # apertura en iris
T_TITULO = (1.0, 4.0)  # el título aparece (pop) y se mantiene
T_SALIDA = 0.8        # duración de la salida del título
T_ZOOM = 4.5          # fin del zoom inicial
T_BARRAS = (3.8, 4.8)  # las barras de cine se retiran
ALTO_BARRA = 58
T_DISOLVER = (3.6, 4.8)  # pasillo, personaje y viñeta se funden con el fondo
T_LIMPIEZA = (3.8, 4.9)  # el grunge se retira (el fondo del juego no lo lleva)


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------
def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def mezclar(c1, c2, f):
    return (
        int(c1[0] + (c2[0] - c1[0]) * f),
        int(c1[1] + (c2[1] - c1[1]) * f),
        int(c1[2] + (c2[2] - c1[2]) * f),
    )


def pixelar_superficie(superficie, factor=2):
    """Baja resolución para reforzar el look de pixel art y la vuelve a escalar."""
    if factor <= 1:
        return superficie
    ancho, alto = superficie.get_size()
    if ancho <= 1 or alto <= 1:
        return superficie
    mini_ancho = max(1, ancho // factor)
    mini_alto = max(1, alto // factor)
    mini = pygame.Surface((mini_ancho, mini_alto), pygame.SRCALPHA)
    pygame.transform.scale(superficie, (mini_ancho, mini_alto), mini)
    return pygame.transform.scale(mini, (ancho, alto))


def suave(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def rebote(x):
    """Ease-out-back: se pasa un poco y vuelve (efecto de dibujo animado)."""
    x = max(0.0, min(1.0, x))
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def _jitter(a, b, semilla):
    h = (a * 73856093) ^ (b * 19349663) ^ (semilla * 83492791)
    dx = ((h & 0xFFFF) / 0xFFFF - 0.5) * 2 * JITTER
    h2 = (a * 19349663) ^ (b * 83492791) ^ (semilla * 73856093)
    dy = ((h2 & 0xFFFF) / 0xFFFF - 0.5) * 2 * JITTER
    return dx, dy


def hue_del_fondo(t):
    """Matiz base del fondo del modo infinito en el instante ``t`` (la misma
    fórmula que usa ``fondo.dibujar_fondo_segmentado_gen``)."""
    tt = t * VEL_FONDO
    p = max(0.0, min(1.0, (NIVEL_FONDO - 1) / 9.0))
    return (HUE_FONDO + math.sin(tt * 0.35) * (0.05 + 0.07 * p) + p * tt * 0.02) % 1.0


def _fondo_respaldo(s, t):
    """Degradado vertical con los colores del cielo del fondo (solo si falta fondo.py)."""
    h = hue_del_fondo(t)
    arriba, abajo = hsv(h - 0.04, 0.40, 0.97), hsv(h + 0.05, 0.30, 0.80)
    franjas = 48
    alto_franja = math.ceil(ALTO / franjas) + 1
    for i in range(franjas):
        f = i / (franjas - 1)
        pygame.draw.rect(s, mezclar(arriba, abajo, f), (0, int(f * ALTO), ANCHO, alto_franja))


def paleta(t):
    """Colores del pasillo, anclados al matiz del fondo del modo infinito: el
    tono oscila con él, así que pasillo y fondo siempre son de la misma familia."""
    h = hue_del_fondo(t)
    return {
        "pared": (hsv(h, 0.55, 0.98), hsv(h, 0.62, 0.64)),
        "techo": (hsv(h + 0.12, 0.50, 0.92), hsv(h + 0.12, 0.58, 0.62)),
        "suelo": (hsv(h + 0.55, 0.65, 0.46), hsv(h + 0.55, 0.72, 0.27)),
    }


# ----------------------------------------------------------------------
# Pasillo infinito en perspectiva
# ----------------------------------------------------------------------
class Pasillo:
    def __init__(self):
        self.avance = 0.0
        self.cuenta = 0

    def avanzar(self, delta):
        self.avance += delta
        while self.avance >= 1.0:
            self.avance -= 1.0
            self.cuenta += 1
        while self.avance < 0.0:
            self.avance += 1.0
            self.cuenta -= 1

    def dibujar(self, s, cx, cy, semilla, pal):
        puntos = []
        for k in range(N_SEGMENTOS + 1):
            z = max(0.3, 0.8 + (k - self.avance) * 0.7)
            gk = k + self.cuenta
            lados = []
            for lado, signo in ((0, -1), (1, 1)):
                x = cx + signo * MEDIO_ANCHO / z
                y_arriba = cy - ALTO_TECHO / z
                y_abajo = cy + ALTO_SUELO / z
                linea = []
                for r in range(FILAS + 1):
                    y = y_arriba + (y_abajo - y_arriba) * r / FILAS
                    dx, dy = _jitter(gk, r + lado * 20, semilla)
                    linea.append((x + dx, y + dy))
                lados.append(linea)
            puntos.append(lados)

        # ``s`` es una superficie con alfa por píxel. Ya no hay muro de fondo ni
        # niebla crema: con la distancia el pasillo se vuelve transparente y se
        # abre al fondo psicodélico del modo infinito. (pygame.draw escribe el
        # RGBA tal cual, sin mezclar, y se pinta de lejos a cerca.)
        for k in range(N_SEGMENTOS - 1, -1, -1):
            gk = k + self.cuenta
            lejania = (k / N_SEGMENTOS) ** 1.15
            niebla = lejania * 0.45
            alfa = int(255 * (1.0 - 0.97 * lejania))
            tinta = (*CONTORNO, alfa)
            a, b = puntos[k], puntos[k + 1]

            c = (*mezclar(pal["techo"][gk % 2], NIEBLA_PASILLO, niebla), alfa)
            quad = [a[0][0], b[0][0], b[1][0], a[1][0]]
            pygame.draw.polygon(s, c, quad)
            pygame.draw.polygon(s, tinta, quad, 2)

            c = (*mezclar(pal["suelo"][gk % 2], NIEBLA_PASILLO, niebla), alfa)
            quad = [a[0][FILAS], b[0][FILAS], b[1][FILAS], a[1][FILAS]]
            pygame.draw.polygon(s, c, quad)
            pygame.draw.polygon(s, tinta, quad, 2)

            for lado in (0, 1):
                for r in range(FILAS):
                    c = (*mezclar(pal["pared"][(gk + r) % 2], NIEBLA_PASILLO, niebla), alfa)
                    quad = [a[lado][r], b[lado][r], b[lado][r + 1], a[lado][r + 1]]
                    pygame.draw.polygon(s, c, quad)
                    pygame.draw.polygon(s, tinta, quad, 2)


def lineas_de_velocidad(s, cx, cy, intensidad):
    for _ in range(int(16 * intensidad)):
        ang = random.uniform(0, math.tau)
        r1 = random.uniform(110, 230)
        r2 = r1 + random.uniform(110, 280)
        p1 = (cx + math.cos(ang) * r1, cy + math.sin(ang) * r1 * 0.9)
        p2 = (cx + math.cos(ang) * r2, cy + math.sin(ang) * r2 * 0.9)
        pygame.draw.line(s, (255, 255, 255), p1, p2, random.randint(1, 3))


# ----------------------------------------------------------------------
# Texto de la intro
# ----------------------------------------------------------------------
def texto_contorneado(fuente, texto, color, grosor=4):
    base = fuente.render(texto, True, color)
    oscuro = fuente.render(texto, True, CONTORNO)
    w, h = base.get_size()
    surf = pygame.Surface((w + grosor * 2, h + grosor * 2), pygame.SRCALPHA)
    for dx in (-grosor, 0, grosor):
        for dy in (-grosor, 0, grosor):
            if dx or dy:
                surf.blit(oscuro, (grosor + dx, grosor + dy))
    surf.blit(base, (grosor, grosor))
    return surf


def iris(s, t):
    """Apertura en iris clásica de dibujo animado."""
    ini, fin = T_IRIS
    if t >= fin:
        return
    q = suave((t - ini) / (fin - ini))
    radio = int(q * 430)
    capa = pygame.Surface((ANCHO, ALTO))
    capa.fill((0, 0, 0))
    capa.set_colorkey((255, 0, 255))
    if radio > 0:
        pygame.draw.circle(capa, (255, 0, 255), (ANCHO // 2, int(ALTO * 0.62)), radio)
    s.blit(capa, (0, 0))


def barras(s, t):
    ini, fin = T_BARRAS
    alto = int(ALTO_BARRA * (1 - suave((t - ini) / (fin - ini))))
    if alto > 0:
        pygame.draw.rect(s, (0, 0, 0), (0, 0, ANCHO, alto))
        pygame.draw.rect(s, (0, 0, 0), (0, ALTO - alto, ANCHO, alto))


def crear_vineta():
    v = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
    v.fill((10, 0, 20, 150))
    pasos = 40
    for i in range(pasos):
        f = 1.45 - 0.75 * i / pasos
        w, h = int(ANCHO * f), int(ALTO * f)
        alfa = int(150 * (1 - i / pasos) ** 1.6)
        pygame.draw.ellipse(
            v, (10, 0, 20, alfa), pygame.Rect((ANCHO - w) // 2, (ALTO - h) // 2, w, h)
        )
    return v


class IntroInfinito:
    """Secuencia visual no bloqueante para el modo infinito."""

    MINI_W, MINI_H = 220, 260
    SUELO_Y = 230
    CENTRO_MINI_X = 110
    DURACION = T_BARRAS[1] + 0.2

    def __init__(self, color=COLOR_PERSONAJE, volumen_efectos=0.8, titulo="INFINITE",
                 grunge=False, intensidad_grunge=0.0, tiempo_fondo=0.0):
        self.color = color
        self.volumen_efectos = volumen_efectos  # se conserva por compatibilidad
        self.titulo = titulo
        self.grunge = EfectoGrunge(ANCHO, ALTO, intensidad_grunge) if grunge else None
        self.superficie_personaje = pygame.Surface(
            (self.MINI_W, self.MINI_H), pygame.SRCALPHA
        )
        self.vineta = crear_vineta()
        # Primer plano (pasillo + personaje) con alfa por píxel, para que se funda
        # con el fondo; ``buffer`` es el fotograma final y ``_sucio`` sirve para
        # retirar el grunge poco a poco.
        self.lienzo = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        self.buffer = pygame.Surface((ANCHO, ALTO))
        self._sucio = pygame.Surface((ANCHO, ALTO))
        # Reloj del fondo: nunca se reinicia (ni con R), así el fondo no se congela
        # ni salta. Si el juego tiene su propio reloj, se puede pasar aquí.
        self._t_fondo = float(tiempo_fondo)
        self.fondo_visible = pygame.Surface((ANCHO, ALTO))
        self.fondo_trasero = pygame.Surface((ANCHO, ALTO))
        self._gen_fondo = None
        self._precalentar_fondo()
        self.fuente_titulo = pygame.font.Font(None, 64)
        self.fuente_titulo.set_bold(True)
        while self.fuente_titulo.size(self.titulo)[0] > ANCHO - 80:
            tamano = self.fuente_titulo.get_height() - 2
            self.fuente_titulo = pygame.font.Font(None, tamano)
            self.fuente_titulo.set_bold(True)
        self.texto_titulo = texto_contorneado(
            self.fuente_titulo, self.titulo, (255, 238, 120), 5
        )
        self.reiniciar()

    @property
    def terminada(self):
        return self.tiempo >= self.DURACION

    @property
    def tiempo_fondo(self):
        """Reloj con el que se dibujó el fondo por última vez. El juego puede
        continuar su propio fondo desde este valor para que el empalme sea exacto."""
        return self._t_fondo

    def _precalentar_fondo(self):
        """Dibuja un primer fondo completo ahora (en el constructor) para que la
        construcción de las caras no cause un tirón durante la animación. Las
        caras que caen quedan en el estado compartido de fondo.py, así que el
        juego las sigue desde donde las dejó la intro."""
        if _fondo is None:
            _fondo_respaldo(self.fondo_visible, self._t_fondo)
        else:
            _fondo.dibujar_fondo_infinito(self.fondo_visible, self._t_fondo, ANCHO, ALTO)
        self.fondo_trasero.blit(self.fondo_visible, (0, 0))

    def _avanzar_fondo(self):
        """Avanza UNA etapa del fondo por fotograma en el buffer trasero y lo
        intercambia al terminar (igual que hace el juego)."""
        if _fondo is None:
            _fondo_respaldo(self.fondo_visible, self._t_fondo)
            return
        if self._gen_fondo is None:
            self._gen_fondo = _fondo.dibujar_fondo_infinito_gen(
                self.fondo_trasero, self._t_fondo, ANCHO, ALTO
            )
        try:
            next(self._gen_fondo)
        except StopIteration:
            self._gen_fondo = None
            self.fondo_visible, self.fondo_trasero = self.fondo_trasero, self.fondo_visible

    def reiniciar(self):
        self.tiempo = 0.0
        self.cuadro = 0
        self.semilla = 0
        self.pasillo = Pasillo()
        self.jugador = PersonajeLoco(self.color)

    def actualizar(self, dt):
        if self.terminada:
            return
        self.tiempo += max(0.0, dt)
        self._t_fondo += max(0.0, dt)
        self.jugador.corre = self.tiempo >= T_ARRANQUE
        self.jugador.actualizar(dt)
        self.pasillo.avanzar(SENTIDO_PASILLO * 0.085 * self.jugador.ritmo)
        if self.cuadro % CUADROS_HERVIDO == 0:
            self.semilla = random.randint(0, 10_000)
        self.cuadro += 1

    def dibujar(self, superficie):
        t = self.tiempo
        jugador = self.jugador
        ritmo = jugador.ritmo
        cx = ANCHO / 2 + math.sin(t * 5.3) * 14 * ritmo
        cy = ALTO * 0.40 - jugador.bob_actual * 2.5 + math.sin(t * 9.0) * 4 * ritmo

        # Fondo real del modo infinito (una etapa por fotograma).
        self._avanzar_fondo()
        # Presencia del primer plano: 1 durante la intro y 0 al final, cuando solo
        # queda el fondo (el mismo que verá el jugador).
        presencia = 1.0 - suave((t - T_DISOLVER[0]) / (T_DISOLVER[1] - T_DISOLVER[0]))

        self.lienzo.fill((0, 0, 0, 0))
        self.pasillo.dibujar(self.lienzo, cx, cy, self.semilla, paleta(self._t_fondo))
        lineas_de_velocidad(self.lienzo, cx, cy, ritmo)

        self.superficie_personaje.fill((0, 0, 0, 0))
        jugador.dibujar(self.superficie_personaje, self.CENTRO_MINI_X, self.SUELO_Y)
        tam = (
            int(self.MINI_W * ESCALA_PERSONAJE),
            int(self.MINI_H * ESCALA_PERSONAJE),
        )
        grande = pygame.transform.scale(self.superficie_personaje, tam)
        self.lienzo.blit(
            grande,
            (
                ANCHO / 2 - self.CENTRO_MINI_X * ESCALA_PERSONAJE,
                PIE_Y - self.SUELO_Y * ESCALA_PERSONAJE,
            ),
        )

        zoom = 1.07 + 0.40 * (1 - suave(t / T_ZOOM))
        pulso = max(0.0, 1 - ((t * 2.0) % 1.0) * 3)
        zoom += 0.025 * pulso * ritmo
        angulo = math.sin(t * 4.1) * 2.4 * ritmo
        girado = pygame.transform.rotozoom(self.lienzo, angulo, zoom)
        cuadro = self.buffer
        cuadro.blit(self.fondo_visible, (0, 0))
        if presencia > 0.0:
            girado.set_alpha(int(255 * presencia))
            cuadro.blit(girado, girado.get_rect(center=(ANCHO // 2, ALTO // 2)))
            self.vineta.set_alpha(int(255 * presencia))
            cuadro.blit(self.vineta, (0, 0))

        dt_titulo = t - T_TITULO[0]
        if 0 <= dt_titulo < T_TITULO[1] - T_TITULO[0]:
            entrada = suave(dt_titulo / T_SALIDA)
            salida = suave(
                (T_TITULO[1] - T_TITULO[0] - dt_titulo) / T_SALIDA
            )
            escala = max(0.05, rebote(min(1.0, dt_titulo / 0.35)) * salida)
            titulo = pygame.transform.rotozoom(self.texto_titulo, 0, escala)
            titulo.set_alpha(int(255 * entrada * salida))
            cuadro.blit(titulo, titulo.get_rect(center=(ANCHO // 2, 110)))

        dt_flash = t - T_TITULO[0]
        if 0 <= dt_flash < 0.25:
            flash = pygame.Surface((ANCHO, ALTO))
            flash.fill((255, 255, 255))
            flash.set_alpha(int(170 * (1 - dt_flash / 0.25)))
            cuadro.blit(flash, (0, 0))

        barras(cuadro, t)
        iris(cuadro, t)
        # El grunge se desactiva por defecto para dejar una intro más limpia y
        # con un look más de pixel art que de película sucia.
        limpieza = suave((t - T_LIMPIEZA[0]) / (T_LIMPIEZA[1] - T_LIMPIEZA[0]))
        if self.grunge is not None and limpieza < 1.0:
            if limpieza <= 0.0:
                self.grunge.aplicar(cuadro, t)
            else:
                sucio = self._sucio
                sucio.set_alpha(255)
                sucio.blit(cuadro, (0, 0))
                self.grunge.aplicar(sucio, t)
                sucio.set_alpha(int(255 * (1.0 - limpieza)))
                cuadro.blit(sucio, (0, 0))
        if not self.grunge:
            cuadro = pixelar_superficie(cuadro, factor=2)
        if superficie.get_size() == (ANCHO, ALTO):
            superficie.blit(cuadro, (0, 0))
        else:
            pygame.transform.scale(cuadro, superficie.get_size(), superficie)


def main():
    """Ejecuta la intro de forma independiente para poder previsualizarla."""
    pygame.init()
    pantalla = pygame.display.set_mode((ANCHO, ALTO))
    pygame.display.set_caption("MODO INFINITO")
    reloj = pygame.time.Clock()
    intro = IntroInfinito()
    ejecutando = True
    while ejecutando:
        dt = min(reloj.tick(FPS) / 1000.0, 0.1)
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT or (
                evento.type == pygame.KEYDOWN and evento.key == pygame.K_ESCAPE
            ):
                ejecutando = False
            elif evento.type == pygame.KEYDOWN and evento.key == pygame.K_r:
                intro.reiniciar()
            elif evento.type == pygame.KEYDOWN and evento.key == pygame.K_SPACE:
                intro.jugador.brincar()
            elif evento.type == pygame.KEYDOWN and evento.key == pygame.K_g:
                # Alterna el grunge para comparar.
                intro.grunge = None if intro.grunge else EfectoGrunge(ANCHO, ALTO)
        intro.actualizar(dt)
        intro.dibujar(pantalla)
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()