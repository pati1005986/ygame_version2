"""Estilo pixel art compartido por todas las pantallas del juego.

Se dibuja directamente sobre la superficie de destino, pero SIEMPRE en
bloques de ``px`` x ``px`` pixeles reales. Así botones, paneles, texto y
formas comparten la misma rejilla y se ven como arte de baja resolución
ampliado, sin necesidad de un lienzo intermedio.

Uso típico en una pantalla:

    self.ui = UIPixel()
    self.ui.establecer_px(UIPixel.px_para(self._escala()))
    ...
    self.ui.panel(superficie, rect_panel)
    self.ui.boton(superficie, rect, self.ui.color(0), "JUGAR", hover=hover,
                  tiempo=self._tiempo)
    self.ui.scanlines(superficie)   # opcional, al final
"""

import math
import os
import random

import pygame


class UIPixel:
    PIXEL_BASE = 3
    TAM_MIN = 5
    RUTA_FUENTE = os.path.join("assets", "fonts", "pixel.ttf")
    FUENTES_SISTEMA = "consolas,couriernew,dejavusansmono,monospace"

    # Paleta compartida: colores planos y saturados (estilo 16 bits).
    PALETA = (
        (255, 0, 77),     # rojo arcade
        (0, 200, 70),     # verde fosforito
        (41, 173, 255),   # azul cielo
        (255, 163, 0),    # naranja
        (170, 100, 255),  # violeta
    )
    TINTA = (20, 12, 28)       # contorno
    SOMBRA = (8, 4, 14)        # sombra dura
    ACENTO = (255, 236, 39)
    BLANCO = (255, 255, 255)
    ACTIVO = (90, 230, 200)    # botón "esperando tecla"

    def __init__(self, px=None, antialias=False):
        self.px = 0
        self.antialias = antialias
        self._fuentes = {}
        self._cache = {}
        self._cache_paneles = {}
        self._cache_scan = {}
        self.establecer_px(px or self.PIXEL_BASE)

    # ------------------------------------------------------------------
    # Rejilla
    # ------------------------------------------------------------------
    @classmethod
    def px_para(cls, escala, base=None):
        """Tamaño de pixel de arte para un factor de escala de UI. ``base``
        permite pantallas con botones pequeños (p. ej. opciones usa 2)."""
        base = cls.PIXEL_BASE if base is None else base
        return max(2, min(8, int(round(base * escala))))

    def establecer_px(self, px):
        px = max(1, int(px))
        if px == self.px:
            return
        self.px = px
        self._cache.clear()
        self._cache_paneles.clear()
        self._cache_scan.clear()

    def _snap(self, valor):
        return int(round(valor / self.px)) * self.px

    def color(self, indice):
        return self.PALETA[indice % len(self.PALETA)]

    @staticmethod
    def mezclar(color, objetivo, t):
        return tuple(int(a + (b - a) * t) for a, b in zip(color, objetivo))

    def tam_para_alto(self, alto_real, preferido):
        """Tamaño de fuente (en pixeles de arte) que cabe en un alto real."""
        unidades = max(1, alto_real // self.px)
        return max(self.TAM_MIN, min(preferido, int((unidades - 2) * 0.8)))

    # ------------------------------------------------------------------
    # Texto
    # ------------------------------------------------------------------
    def _fuente(self, tam):
        fuente = self._fuentes.get(tam)
        if fuente is None:
            if os.path.exists(self.RUTA_FUENTE):
                try:
                    fuente = pygame.font.Font(self.RUTA_FUENTE, tam)
                except (pygame.error, OSError):
                    fuente = None
            if fuente is None:
                fuente = pygame.font.SysFont(self.FUENTES_SISTEMA, tam, bold=True)
            self._fuentes[tam] = fuente
        return fuente

    def _imagen(self, contenido, color, tam):
        """Texto sin suavizado, ampliado ``px`` veces (cacheado)."""
        clave = (contenido, tuple(color), tam)
        imagen = self._cache.get(clave)
        if imagen is None:
            if len(self._cache) > 600:
                self._cache.clear()
            base = self._fuente(tam).render(contenido, self.antialias, color)
            if self.px != 1:
                base = pygame.transform.scale(
                    base, (base.get_width() * self.px, base.get_height() * self.px)
                )
            imagen = base
            self._cache[clave] = imagen
        return imagen

    def texto(self, s, contenido, centro, color=None, tam=10, ancho_max=None,
              contorno=True, centrado=True):
        """Texto pixelado con contorno de 1 pixel y sombra dura. Si no cabe en
        ``ancho_max`` reduce el tamaño hasta ``TAM_MIN``."""
        if not contenido:
            return pygame.Rect(int(centro[0]), int(centro[1]), 0, 0)
        color = color or self.BLANCO
        t = tam
        imagen = self._imagen(contenido, color, t)
        while ancho_max is not None and imagen.get_width() > ancho_max and t > self.TAM_MIN:
            t -= 1
            imagen = self._imagen(contenido, color, t)
        if centrado:
            rect = imagen.get_rect(center=(int(centro[0]), int(centro[1])))
        else:
            rect = imagen.get_rect(topleft=(int(centro[0]), int(centro[1])))
        rect.topleft = (self._snap(rect.x), self._snap(rect.y))
        if contorno:
            p = self.px
            borde = self._imagen(contenido, self.TINTA, t)
            for dx, dy in ((-p, 0), (p, 0), (0, -p), (0, p), (p, p)):
                s.blit(borde, rect.move(dx, dy))
        s.blit(imagen, rect)
        return rect

    def titulo(self, s, contenido, centro, color=None, tam=18, tiempo=0.0,
               ancho_max=None):
        """Título con letras que ondulan en pasos de pixel entero."""
        if not contenido:
            return
        color = color or self.ACENTO
        p = self.px
        t = tam
        imagenes = [self._imagen(c, color, t) for c in contenido]
        while (
            ancho_max
            and sum(i.get_width() for i in imagenes) > ancho_max
            and t > self.TAM_MIN
        ):
            t -= 1
            imagenes = [self._imagen(c, color, t) for c in contenido]
        total = sum(i.get_width() for i in imagenes)
        alto = max(i.get_height() for i in imagenes)
        x = centro[0] - total // 2
        y = centro[1] - alto // 2
        for i, (caracter, imagen) in enumerate(zip(contenido, imagenes)):
            if caracter != " ":
                dy = int(round(math.sin(tiempo * 3 + i * 0.55) * 1.5)) * p
                pos = (self._snap(x), self._snap(y) + dy)
                borde = self._imagen(caracter, self.TINTA, t)
                for ox, oy in ((-p, 0), (p, 0), (0, -p), (0, p), (p, p), (0, 2 * p), (p, 2 * p)):
                    s.blit(borde, (pos[0] + ox, pos[1] + oy))
                s.blit(imagen, pos)
            x += imagen.get_width()

    # ------------------------------------------------------------------
    # Formas básicas
    # ------------------------------------------------------------------
    @staticmethod
    def _muescas_real(s, color, x, y, w, h, n):
        """Rectángulo con las esquinas mordidas ``n`` pixeles reales."""
        if w < 3 * n or h < 3 * n:
            s.fill(color, (x, y, w, h))
            return
        s.fill(color, (x + n, y, w - 2 * n, h))
        s.fill(color, (x, y + n, w, h - 2 * n))

    def boton(self, s, rect, color, etiqueta="", hover=False, activo=False,
              tiempo=0.0, tam=10):
        """Botón biselado con sombra dura. ``hover`` lo eleva 1 pixel y pasa
        un brillo diagonal; ``activo`` lo pinta de ``ACTIVO`` y parpadea el
        contorno. Devuelve el rect del cuerpo dibujado (para colocar texto)."""
        p = self.px
        bw = max(5, rect.w // p)
        bh = max(5, rect.h // p)
        ox = self._snap(rect.x + (rect.w - bw * p) / 2)
        oy = self._snap(rect.y + (rect.h - bh * p) / 2)
        elevado = hover or activo

        base = self.ACTIVO if activo else color
        if hover and not activo:
            base = self.mezclar(base, self.BLANCO, 0.18)
        claro = self.mezclar(base, self.BLANCO, 0.45)
        oscuro = self.mezclar(base, (0, 0, 0), 0.4)

        def f(c, x, y, w, h):
            s.fill(c, (ox + x * p, oy + y * p, w * p, h * p))

        def m(c, x, y, w, h):
            if w < 3 or h < 3:
                f(c, x, y, w, h)
                return
            f(c, x + 1, y, w - 2, h)
            f(c, x, y + 1, w, h - 2)

        dy = -1 if elevado else 0
        m(self.SOMBRA, 1, 1, bw, bh)
        borde = self.TINTA
        if activo and int(tiempo * 6) % 2 == 0:
            borde = self.ACENTO
        m(borde, 0, dy, bw, bh)

        ix, iy, iw, ih = 1, 1 + dy, bw - 2, bh - 2
        m(base, ix, iy, iw, ih)
        if iw >= 4 and ih >= 4:
            f(claro, ix + 1, iy, iw - 2, 1)
            f(claro, ix, iy + 1, 1, ih - 2)
            f(oscuro, ix + 1, iy + ih - 1, iw - 2, 1)
            f(oscuro, ix + iw - 1, iy + 1, 1, ih - 2)

        if hover and not activo and iw > 12:
            brillo = self.mezclar(base, self.BLANCO, 0.6)
            ciclo = iw + 16
            x0 = int((tiempo * 18) % ciclo) - 8
            for fila in range(1, ih - 1):
                x = x0 + (ih - fila)
                if 1 <= x <= iw - 3:
                    f(brillo, ix + x, iy + fila, 2, 1)

        cuerpo = pygame.Rect(ox, oy + dy * p, bw * p, bh * p)
        if etiqueta:
            self.texto(
                s, etiqueta, cuerpo.center, self.BLANCO,
                self.tam_para_alto(cuerpo.h, tam), ancho_max=cuerpo.w - 4 * p,
            )
        return cuerpo

    def panel(self, s, rect, relleno=(15, 20, 40, 210), borde=None):
        """Panel con marco doble (acento + tinta), esquinas mordidas y sombra
        dura. El relleno puede ser semitransparente."""
        p = self.px
        borde = borde or self.ACENTO
        bw = max(6, rect.w // p)
        bh = max(6, rect.h // p)
        x = self._snap(rect.x)
        y = self._snap(rect.y)

        self._muescas_real(s, self.SOMBRA, x + 2 * p, y + 2 * p, bw * p, bh * p, p)

        clave = (bw, bh, tuple(relleno), tuple(borde), p)
        superficie = self._cache_paneles.get(clave)
        if superficie is None:
            superficie = pygame.Surface((bw * p, bh * p), pygame.SRCALPHA)

            def m(c, ux, uy, w, h):
                self._muescas_real(superficie, c, ux * p, uy * p, w * p, h * p, p)

            m((*borde, 255), 0, 0, bw, bh)
            m((*self.TINTA, 255), 1, 1, bw - 2, bh - 2)
            m(tuple(relleno), 2, 2, bw - 4, bh - 4)
            if len(self._cache_paneles) > 32:
                self._cache_paneles.clear()
            self._cache_paneles[clave] = superficie
        s.blit(superficie, (x, y))
        return pygame.Rect(x, y, bw * p, bh * p)

    def barra(self, s, centro_x, y, ancho, color_a=(0, 255, 204), color_b=None):
        """Raya decorativa de dos tonos con contorno."""
        p = self.px
        color_b = color_b or self.ACENTO
        w = max(3, ancho // p) * p
        x = self._snap(centro_x - w / 2)
        y = self._snap(y)
        s.fill(self.TINTA, (x - p, y - p, w + 2 * p, 4 * p))
        s.fill(color_a, (x, y, w, p))
        s.fill(color_b, (x, y + p, w, p))

    def scanlines(self, s, alpha=36):
        """Líneas CRT: una oscura por cada fila de pixeles de arte."""
        tamano = s.get_size()
        clave = (tamano, alpha)
        capa = self._cache_scan.get(clave)
        if capa is None:
            capa = pygame.Surface(tamano, pygame.SRCALPHA)
            for y in range(self.px - 1, tamano[1], self.px):
                capa.fill((0, 0, 0, alpha), (0, y, tamano[0], 1))
            self._cache_scan[clave] = capa
        s.blit(capa, (0, 0))


class FormasPixel:
    """Fondo de formas geométricas flotantes hechas de bloques (cuadrados,
    rombos, triángulos, cruces y rayas) que se mueven en pasos de pixel.
    Sustituye al "arte abstracto" con rotación y suavizado."""

    TIPOS = ("cuadrado", "rombo", "triangulo", "cruz", "linea")

    def __init__(self, ui, ancho, alto, colores, semilla, cantidad=12):
        self.ui = ui
        self.ancho = ancho
        self.alto = alto
        azar = random.Random(semilla)
        self.formas = [
            {
                "tipo": azar.choice(self.TIPOS),
                "x": azar.uniform(0, ancho),
                "y": azar.uniform(0, alto),
                "n": azar.randint(5, 14),
                "color": azar.choice(colores),
                "vel": azar.uniform(0.25, 0.7),
                "fase": azar.uniform(0, math.tau),
            }
            for _ in range(cantidad)
        ]
        self._capa = None

    def dibujar(self, s, tiempo):
        p = self.ui.px
        if self._capa is None or self._capa.get_size() != (self.ancho, self.alto):
            self._capa = pygame.Surface((self.ancho, self.alto), pygame.SRCALPHA)
        capa = self._capa
        capa.fill((0, 0, 0, 0))

        def f(c, x, y, w, h):
            capa.fill(c, (x * p, y * p, w * p, h * p))

        for forma in self.formas:
            ux = int(forma["x"] / p + math.cos(tiempo * forma["vel"] + forma["fase"]) * 6)
            uy = int(forma["y"] / p + math.sin(tiempo * forma["vel"] * 0.8 + forma["fase"]) * 6)
            n, c, tipo = forma["n"], forma["color"], forma["tipo"]
            if tipo == "cuadrado":
                f(c, ux - n, uy - n, 2 * n, 2)
                f(c, ux - n, uy + n - 2, 2 * n, 2)
                f(c, ux - n, uy - n, 2, 2 * n)
                f(c, ux + n - 2, uy - n, 2, 2 * n)
            elif tipo == "rombo":
                for fila in range(-n, n + 1):
                    ancho = n - abs(fila)
                    f(c, ux - ancho, uy + fila, 2 * ancho + 1, 1)
            elif tipo == "triangulo":
                for fila in range(n):
                    f(c, ux - fila, uy - n // 2 + fila, 2 * fila + 1, 1)
            elif tipo == "cruz":
                f(c, ux - n, uy - 1, 2 * n, 2)
                f(c, ux - 1, uy - n, 2, 2 * n)
            else:  # raya discontinua
                for i in range(-n, n, 3):
                    f(c, ux + i, uy, 2, 2)
        s.blit(capa, (0, 0))