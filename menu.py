import math
import os
import random

import pygame

from idioma import texto
from opciones import MenuOpciones  # noqa: F401  (se conserva por compatibilidad)

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover - opcional para la intro
    cv2 = None
    np = None


class MenuInicio:
    """Pantalla de inicio estilo retro pixel art.

    Todo se dibuja en un lienzo de baja resolución (cada "pixel" del arte
    ocupa ``self.px`` pixeles reales) que se amplía con vecino más cercano.
    Así, fondo, botones y texto comparten la misma rejilla de pixeles, igual
    que en una consola clásica. Encima se aplica una capa de scanlines CRT.

    Novedades respecto a la versión anterior:
    - Botones biselados con esquinas "mordidas", sombra dura y brillo animado.
    - Video posterizado a pocos colores con tramado (dither) Bayer.
    - Fondo de estrellas con parallax cuando no hay video.
    - Navegación con teclado (izq/der, arriba/abajo, A/D, W/S, Enter, Espacio).
    - Flecha parpadeante sobre el botón seleccionado.
    - Título opcional con letras que ondulan (parámetro ``titulo``).
    - Fuente pixel opcional: coloca un .ttf en ``RUTA_FUENTE`` (por ejemplo
      Press Start 2P). Si no existe, usa una fuente monoespaciada del sistema.
    """

    ANCHO_REFERENCIA = 800
    ALTO_REFERENCIA = 600
    ESCALA_MIN = 0.55
    ESCALA_MAX = 1.6

    PIXEL_BASE = 3          # tamaño del "pixel" de arte a escala 1.0
    NIVELES_COLOR = 5       # niveles por canal al posterizar el video
    ALPHA_SCANLINES = 38    # 0 desactiva las scanlines
    RUTA_FUENTE = os.path.join("assets", "fonts", "pixel.ttf")
    FUENTES_SISTEMA = "consolas,couriernew,dejavusansmono,monospace"

    # Paleta limitada, de colores planos y saturados (estilo 16 bits).
    PALETA_BOTONES = (
        (255, 0, 77),     # rojo arcade
        (0, 200, 70),     # verde fosforito
        (41, 173, 255),   # azul cielo
        (255, 163, 0),    # naranja
        (170, 100, 255),  # violeta
    )
    COLOR_TINTA = (20, 12, 28)      # contorno
    COLOR_SOMBRA = (8, 4, 14)       # sombra dura
    COLOR_ACENTO = (255, 236, 39)
    COLOR_TEXTO = (255, 255, 255)
    COLOR_FONDO = (10, 12, 18)
    COLOR_PANEL = (20, 12, 28)

    def __init__(self, ancho, alto, nombre_video="image.gif", idioma="en",
                 escala_ui=1.0, titulo=""):
        self.ancho = ancho
        self.alto = alto
        self.idioma = idioma
        self.escala_ui = escala_ui
        self.titulo = titulo
        self.nivel_guardado = 1
        self.modo_infinito_desbloqueado = False
        self.mejor_puntaje_infinito = 0
        self.ruta_video = os.path.join("assets", nombre_video)
        self.cap = None
        self.frame_actual = None
        self.ultimo_frame = 0
        self._rgb_original = None

        self.indice_seleccionado = 0
        self._ultimo_mouse = None
        self._cache_texto = {}

        self.tiempo_inicio = pygame.time.get_ticks()
        self.reloj_pulso = 0.0

        self._reconstruir()
        self._cargar_video()

    # ------------------------------------------------------------------
    # Escala, rejilla de pixeles y capas precalculadas
    # ------------------------------------------------------------------
    def _escala(self):
        """Factor de escala relativo a la resolución de referencia, con
        límites, multiplicado por la preferencia de escala de UI."""
        base = max(
            self.ESCALA_MIN,
            min(
                self.ancho / self.ANCHO_REFERENCIA,
                self.alto / self.ALTO_REFERENCIA,
                self.ESCALA_MAX,
            ),
        )
        return base * self.escala_ui

    def _calcular_pixel(self):
        self.px = max(2, min(8, int(round(self.PIXEL_BASE * self._escala()))))
        self.ancho_bajo = -(-self.ancho // self.px)
        self.alto_bajo = -(-self.alto // self.px)

    def _ajustar(self, valor):
        """Redondea una medida real al múltiplo más cercano del pixel."""
        return max(self.px, int(round(valor / self.px)) * self.px)

    def _reconstruir(self):
        self._calcular_pixel()
        self._crear_fuentes()
        self._crear_rectangulos()
        self._construir_capas()
        if cv2 is not None and self._rgb_original is not None:
            self._actualizar_superficie_frame()

    def _construir_capas(self):
        self._lienzo = pygame.Surface((self.ancho_bajo, self.alto_bajo))
        self._tam_ampliado = (self.ancho_bajo * self.px, self.alto_bajo * self.px)
        self._ampliado = pygame.Surface(self._tam_ampliado)

        self._capa_vineta = self._construir_vineta()
        self._capa_panel_base = self._construir_panel_base()
        self._capa_scanlines = self._construir_scanlines()
        self._fondo_estatico = self._construir_fondo()
        self._estrellas = self._construir_estrellas()

        if np is not None:
            matriz = np.array(
                [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]],
                dtype=np.float32,
            )
            matriz = ((matriz + 0.5) / 16.0 - 0.5) * 0.8
            reps = (self.alto_bajo // 4 + 1, self.ancho_bajo // 4 + 1)
            self._umbral_bayer = np.tile(matriz, reps)[
                : self.alto_bajo, : self.ancho_bajo, None
            ]

    def _construir_vineta(self):
        """Oscurece el borde superior en bandas escalonadas (sin degradado
        suave) para que el título se lea sobre cualquier fotograma."""
        alto_v = max(8, min(46, int(self.alto_bajo * 0.24)))
        capa = pygame.Surface((self.ancho_bajo, alto_v), pygame.SRCALPHA)
        bandas = (150, 105, 65, 30)
        alto_banda = max(1, alto_v // len(bandas))
        for i, alpha in enumerate(bandas):
            capa.fill((0, 0, 0, alpha), (0, i * alto_banda, self.ancho_bajo, alto_banda))
        return capa

    def _construir_panel_base(self):
        """Panel inferior sólido con borde superior tramado."""
        alto_p = max(8, self._alto_panel // self.px)
        capa = pygame.Surface((self.ancho_bajo, alto_p), pygame.SRCALPHA)
        capa.fill((*self.COLOR_PANEL, 210), (0, 2, self.ancho_bajo, alto_p - 2))
        for x in range(self.ancho_bajo):
            capa.set_at((x, 0), (*self.COLOR_PANEL, 90 if x % 2 == 0 else 0))
            capa.set_at((x, 1), (*self.COLOR_PANEL, 150 if x % 2 else 90))
        return capa

    def _construir_scanlines(self):
        capa = pygame.Surface(self._tam_ampliado, pygame.SRCALPHA)
        if self.ALPHA_SCANLINES > 0:
            for y in range(self.px - 1, self._tam_ampliado[1], self.px):
                capa.fill((0, 0, 0, self.ALPHA_SCANLINES), (0, y, self._tam_ampliado[0], 1))
        return capa

    def _construir_fondo(self):
        """Cielo nocturno en bandas, con filas tramadas entre bandas. Se usa
        solo si no hay video."""
        fondo = pygame.Surface((self.ancho_bajo, self.alto_bajo))
        colores = (
            (12, 10, 30), (20, 12, 42), (30, 14, 52),
            (42, 18, 62), (58, 24, 70), (76, 32, 78),
        )
        alto_banda = -(-self.alto_bajo // len(colores))
        for i, color in enumerate(colores):
            fondo.fill(color, (0, i * alto_banda, self.ancho_bajo, alto_banda))
            if i > 0:
                y = i * alto_banda
                for x in range(1, self.ancho_bajo, 2):
                    fondo.set_at((x, y), color)
                    if y > 0:
                        fondo.set_at((x - 1, y - 1), color)
        return fondo

    def _construir_estrellas(self):
        rnd = random.Random(7)
        n = max(24, self.ancho_bajo * self.alto_bajo // 300)
        return [
            (
                rnd.randrange(self.ancho_bajo),
                rnd.uniform(0, self.alto_bajo),
                rnd.choice((1, 2, 3)),
                rnd.uniform(0, math.tau),
            )
            for _ in range(n)
        ]

    # ------------------------------------------------------------------
    # Fuentes y texto
    # ------------------------------------------------------------------
    def _cargar_fuente(self, tam):
        if os.path.exists(self.RUTA_FUENTE):
            try:
                return pygame.font.Font(self.RUTA_FUENTE, tam)
            except pygame.error:
                pass
        return pygame.font.SysFont(self.FUENTES_SISTEMA, tam, bold=True)

    def _crear_fuentes(self):
        """Los tamaños son en pixeles del lienzo bajo. Con una fuente pixel
        propia conviene usar múltiplos de su rejilla (8 para Press Start 2P)."""
        self._cache_texto = {}
        if os.path.exists(self.RUTA_FUENTE):
            tam_boton, tam_record, tam_titulo = (8,), (8,), (24, 16, 8)
        else:
            tam_boton = (11, 10, 9, 8, 7)
            tam_record = (8, 7)
            tam_titulo = (26, 22, 18, 14, 10)
        self._fuentes_boton = [self._cargar_fuente(t) for t in tam_boton]
        self._fuentes_record = [self._cargar_fuente(t) for t in tam_record]
        self._fuentes_titulo = [self._cargar_fuente(t) for t in tam_titulo]
        self.font_prompt = self._fuentes_boton[0]
        self.font_record = self._fuentes_record[0]
        self.font_titulo = self._fuentes_titulo[0]

    def _imagen_texto(self, fuente, contenido, color):
        clave = (id(fuente), contenido, color)
        imagen = self._cache_texto.get(clave)
        if imagen is None:
            # antialias=False: bordes duros, sin suavizado.
            imagen = fuente.render(contenido, False, color)
            self._cache_texto[clave] = imagen
        return imagen

    @staticmethod
    def _mejor_fuente(fuentes, contenido, ancho_max):
        for fuente in fuentes:
            if fuente.size(contenido)[0] <= ancho_max:
                return fuente
        return fuentes[-1]

    def _dibujar_texto(self, lienzo, contenido, fuente, pos, color, centrado=True):
        """Texto con contorno de 1 pixel y sombra dura abajo a la derecha."""
        imagen = self._imagen_texto(fuente, contenido, color)
        rect = imagen.get_rect(center=pos) if centrado else imagen.get_rect(topleft=pos)
        borde = self._imagen_texto(fuente, contenido, self.COLOR_TINTA)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1)):
            lienzo.blit(borde, rect.move(dx, dy))
        lienzo.blit(imagen, rect)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _crear_rectangulos(self):
        nombres = ["historia"]
        if self.modo_infinito_desbloqueado:
            nombres.append("infinito")
        nombres.extend(("opciones", "salir"))

        boton_ancho = self._ajustar(max(90, min(170, (self.ancho - 48) / len(nombres) - 12)))
        boton_alto = self._ajustar(max(36, min(58, self.alto * 0.1)))
        espacio = self._ajustar(max(8, boton_ancho * 0.08))
        ancho_total = boton_ancho * len(nombres) + espacio * (len(nombres) - 1)
        x_izq = self._ajustar((self.ancho - ancho_total) / 2)
        alto_panel = self._ajustar(max(120, min(170, self.alto * 0.3)))
        y_boton = self._ajustar(self.alto - alto_panel * 0.55)

        self.botones_inicio = {}
        for indice, nombre in enumerate(nombres):
            self.botones_inicio[nombre] = pygame.Rect(
                x_izq + (boton_ancho + espacio) * indice,
                y_boton,
                boton_ancho,
                boton_alto,
            )
        self.boton_jugar = self.botones_inicio["historia"]
        self.boton_infinito = self.botones_inicio.get("infinito")
        self.boton_opciones = self.botones_inicio["opciones"]
        self.boton_salir = self.botones_inicio["salir"]
        self._alto_panel = alto_panel
        self.indice_seleccionado = min(self.indice_seleccionado, len(nombres) - 1)

    def _rect_bajo(self, rect):
        return pygame.Rect(
            rect.x // self.px, rect.y // self.px,
            max(1, rect.w // self.px), max(1, rect.h // self.px),
        )

    # ------------------------------------------------------------------
    # API pública de configuración
    # ------------------------------------------------------------------
    def establecer_idioma(self, idioma):
        self.idioma = idioma

    def establecer_nivel_guardado(self, nivel):
        self.nivel_guardado = max(1, int(nivel))

    def establecer_modo_infinito_desbloqueado(self, desbloqueado):
        desbloqueado = bool(desbloqueado)
        if desbloqueado == self.modo_infinito_desbloqueado:
            return
        self.modo_infinito_desbloqueado = desbloqueado
        self._crear_rectangulos()

    def establecer_mejor_puntaje_infinito(self, puntaje):
        self.mejor_puntaje_infinito = max(0, int(puntaje))

    def establecer_escala_ui(self, escala_ui):
        self.escala_ui = escala_ui
        self._reconstruir()

    def establecer_video(self, nombre_video):
        """Cambia el video de fondo del menú (por ejemplo, cuando el jugador
        ya completó el juego y corresponde mostrar la imagen final)."""
        ruta = os.path.join("assets", nombre_video)
        if ruta == self.ruta_video:
            return
        self.ruta_video = ruta
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.frame_actual = None
        self._rgb_original = None
        self._cargar_video()

    def actualizar_tamano(self, ancho, alto):
        self.ancho = ancho
        self.alto = alto
        self._reconstruir()

    # ------------------------------------------------------------------
    # Carga y reproducción de video
    # ------------------------------------------------------------------
    def _cargar_video(self):
        if cv2 is None:
            return

        self.cap = cv2.VideoCapture(self.ruta_video)
        if not self.cap.isOpened():
            self.cap = None
            return
        self.fps_video = self.cap.get(cv2.CAP_PROP_FPS) or 24.0
        self._avanzar_frame()

    def _avanzar_frame(self):
        if self.cap is None:
            return

        ok, frame = self.cap.read()
        if not ok:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.cap.read()

        if not ok:
            self.frame_actual = None
            self._rgb_original = None
            return

        self._rgb_original = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self._actualizar_superficie_frame()
        self.ultimo_frame = pygame.time.get_ticks()

    def _actualizar_superficie_frame(self):
        """Reduce el fotograma a la resolución del lienzo (INTER_AREA conserva
        el detalle al bajar tamaño) y lo posteriza con tramado Bayer."""
        rgb = cv2.resize(
            self._rgb_original, (self.ancho_bajo, self.alto_bajo),
            interpolation=cv2.INTER_AREA,
        )
        niveles = self.NIVELES_COLOR
        if niveles and niveles > 1:
            paso = 255.0 / (niveles - 1)
            f = rgb.astype(np.float32) / paso + self._umbral_bayer
            f = np.clip(np.floor(f + 0.5), 0, niveles - 1) * paso
            rgb = f.astype(np.uint8)
        rgb = np.ascontiguousarray(rgb)
        self.frame_actual = pygame.image.frombuffer(
            rgb.tobytes(), (self.ancho_bajo, self.alto_bajo), "RGB"
        )

    def actualizar(self):
        if self.cap is not None and self.frame_actual is not None:
            ahora = pygame.time.get_ticks()
            if ahora - self.ultimo_frame >= 1000 / self.fps_video:
                self._avanzar_frame()

        # Reloj interno para las animaciones (independiente del video)
        self.reloj_pulso = (pygame.time.get_ticks() - self.tiempo_inicio) / 1000.0

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------
    def dibujar(self, superficie, mouse_pos=None):
        if mouse_pos is not None and mouse_pos != self._ultimo_mouse:
            self._ultimo_mouse = mouse_pos
            self._seleccionar_por_mouse(mouse_pos)

        lienzo = self._lienzo
        if self.frame_actual is not None:
            lienzo.blit(self.frame_actual, (0, 0))
        else:
            self._dibujar_fondo_estrellas(lienzo)

        self._dibujar_vineta(lienzo)
        self._dibujar_titulo(lienzo)
        self._dibujar_panel_inferior(lienzo)

        # Ampliación con vecino más cercano: pixeles nítidos, sin suavizado.
        pygame.transform.scale(lienzo, self._tam_ampliado, self._ampliado)
        superficie.blit(self._ampliado, (0, 0))
        if self.ALPHA_SCANLINES > 0:
            superficie.blit(self._capa_scanlines, (0, 0))

    def _dibujar_fondo_estrellas(self, lienzo):
        lienzo.blit(self._fondo_estatico, (0, 0))
        t = self.reloj_pulso
        for x, y0, capa, fase in self._estrellas:
            y = int((y0 + t * capa * 2.5) % self.alto_bajo)
            if math.sin(t * 3 + fase) > 0.92:
                color = (255, 255, 255)
            else:
                v = 70 + capa * 50
                color = (v, v, min(255, v + 30))
            lienzo.set_at((x, y), color)

    def _dibujar_vineta(self, lienzo):
        lienzo.blit(self._capa_vineta, (0, 0))

    def _dibujar_titulo(self, lienzo):
        """Título opcional: letras que ondulan en pasos de pixel entero."""
        if not self.titulo:
            return
        fuente = self._mejor_fuente(
            self._fuentes_titulo, self.titulo, self.ancho_bajo - 12
        )
        anchos = [fuente.size(c)[0] for c in self.titulo]
        x = (self.ancho_bajo - sum(anchos)) // 2
        y_base = int(self.alto_bajo * 0.16)
        t = self.reloj_pulso
        for i, caracter in enumerate(self.titulo):
            if caracter != " ":
                dy = int(round(math.sin(t * 3 + i * 0.55) * 1.5))
                self._dibujar_texto(
                    lienzo, caracter, fuente, (x, y_base + dy),
                    self.COLOR_ACENTO, centrado=False,
                )
            x += anchos[i]

    def _dibujar_panel_inferior(self, lienzo):
        alto_p = self._capa_panel_base.get_height()
        y_panel = self.alto_bajo - alto_p
        lienzo.blit(self._capa_panel_base, (0, y_panel))

        # Línea de acento que "respira" en 3 pasos de color (sin degradado).
        pulso = 0.5 + 0.5 * math.sin(self.reloj_pulso * 2.4)
        paso = min(2, int(pulso * 3))
        color_linea = self._mezclar(self.COLOR_TINTA, self.COLOR_ACENTO, (paso + 1) / 3)
        lienzo.fill(color_linea, (0, y_panel + 2, self.ancho_bajo, 1))
        lienzo.fill(self.COLOR_TINTA, (0, y_panel + 3, self.ancho_bajo, 1))

        claves = {
            "historia": "continue" if self.nivel_guardado > 1 else "story",
            "infinito": "infinite",
            "opciones": "options",
            "salir": "exit",
        }
        for indice, (nombre, rect) in enumerate(self.botones_inicio.items()):
            activo = indice == self.indice_seleccionado
            color = self.PALETA_BOTONES[indice % len(self.PALETA_BOTONES)]
            cuerpo = self._dibujar_boton_pixel(lienzo, self._rect_bajo(rect), color, activo)

            etiqueta = texto(self.idioma, claves[nombre]).upper()
            fuente = self._mejor_fuente(self._fuentes_boton, etiqueta, cuerpo.w - 4)
            self._dibujar_texto(lienzo, etiqueta, fuente, cuerpo.center, self.COLOR_TEXTO)

            if activo:
                self._dibujar_flecha(lienzo, cuerpo)

            if nombre == "infinito":
                record = (
                    f"{texto(self.idioma, 'best_score')}: "
                    f"{self.mejor_puntaje_infinito}"
                ).upper()
                fuente_r = self._mejor_fuente(self._fuentes_record, record, cuerpo.w + 16)
                self._dibujar_texto(
                    lienzo, record, fuente_r,
                    (cuerpo.centerx, cuerpo.bottom + 5), self.COLOR_ACENTO,
                )

    @staticmethod
    def _mezclar(color, objetivo, t):
        return tuple(int(a + (b - a) * t) for a, b in zip(color, objetivo))

    @staticmethod
    def _rect_muescas(lienzo, r, color):
        """Rectángulo con las 4 esquinas mordidas por 1 pixel."""
        if r.w < 3 or r.h < 3:
            lienzo.fill(color, r)
            return
        lienzo.fill(color, (r.x + 1, r.y, r.w - 2, r.h))
        lienzo.fill(color, (r.x, r.y + 1, r.w, r.h - 2))

    def _dibujar_boton_pixel(self, lienzo, rect, color_base, activo):
        """Botón biselado: sombra dura, contorno, relleno plano, luz arriba/
        izquierda, sombra abajo/derecha y, si está activo, un brillo
        diagonal que lo recorre. Devuelve el rect del cuerpo dibujado."""
        if activo:
            color_base = self._mezclar(color_base, (255, 255, 255), 0.18)
        claro = self._mezclar(color_base, (255, 255, 255), 0.45)
        oscuro = self._mezclar(color_base, (0, 0, 0), 0.4)

        cuerpo = rect.move(0, -1) if activo else rect.copy()

        self._rect_muescas(lienzo, rect.move(1, 1), self.COLOR_SOMBRA)
        self._rect_muescas(lienzo, cuerpo, self.COLOR_TINTA)

        interior = cuerpo.inflate(-2, -2)
        self._rect_muescas(lienzo, interior, color_base)
        if interior.w >= 4 and interior.h >= 4:
            lienzo.fill(claro, (interior.x + 1, interior.y, interior.w - 2, 1))
            lienzo.fill(claro, (interior.x, interior.y + 1, 1, interior.h - 2))
            lienzo.fill(oscuro, (interior.x + 1, interior.bottom - 1, interior.w - 2, 1))
            lienzo.fill(oscuro, (interior.right - 1, interior.y + 1, 1, interior.h - 2))

        if activo and interior.w > 12:
            brillo = self._mezclar(color_base, (255, 255, 255), 0.6)
            ciclo = interior.w + 16
            x0 = interior.x + int((self.reloj_pulso * 18) % ciclo) - 8
            for fila in range(1, interior.h - 1):
                x = x0 + (interior.h - fila)
                if interior.x + 1 <= x <= interior.right - 3:
                    lienzo.fill(brillo, (x, interior.y + fila, 2, 1))

        return cuerpo

    def _dibujar_boton_comic(self, lienzo, rect, hover=False):
        """Dibuja un botón en el lienzo lógico para las pantallas del juego."""
        color = self.PALETA_BOTONES[2]
        return self._dibujar_boton_pixel(lienzo, rect, color, hover)

    def _texto_centrado(self, lienzo, contenido, fuente, centro,
                        color=(255, 255, 255), ancho_max=None):
        """Dibuja texto centrado, escalando las fuentes internas del menú."""
        pixelado = fuente in self._fuentes_boton
        fuentes = self._fuentes_boton if pixelado else (fuente,)
        factor = self.px if pixelado else 1

        imagen = borde = None
        for candidata in fuentes:
            imagen = candidata.render(contenido, False, color)
            borde = candidata.render(contenido, False, self.COLOR_TINTA)
            if factor > 1:
                tamano = (imagen.get_width() * factor, imagen.get_height() * factor)
                imagen = pygame.transform.scale(imagen, tamano)
                borde = pygame.transform.scale(borde, tamano)
            if ancho_max is None or imagen.get_width() <= ancho_max:
                break

        if ancho_max is not None and imagen.get_width() > ancho_max:
            alto = max(1, round(imagen.get_height() * ancho_max / imagen.get_width()))
            tamano = (ancho_max, alto)
            imagen = pygame.transform.scale(imagen, tamano)
            borde = pygame.transform.scale(borde, tamano)

        rect = imagen.get_rect(center=centro)
        grosor = max(1, self.px) if pixelado else 1
        for dx, dy in ((-grosor, 0), (grosor, 0), (0, -grosor), (0, grosor)):
            lienzo.blit(borde, rect.move(dx, dy))
        lienzo.blit(imagen, rect)
        return rect

    def _dibujar_flecha(self, lienzo, cuerpo):
        """Flecha hacia abajo que rebota sobre el botón seleccionado."""
        rebote = int(self.reloj_pulso * 4) % 2
        cx = cuerpo.centerx
        y0 = cuerpo.top - 6 + rebote
        filas = (5, 3, 1)
        lienzo.fill(self.COLOR_TINTA, (cx - 3, y0 - 1, 7, 1))
        for k, w in enumerate(filas):
            lienzo.fill(self.COLOR_TINTA, (cx - w // 2 - 1, y0 + k, w + 2, 1))
        lienzo.fill(self.COLOR_TINTA, (cx - 1, y0 + len(filas), 3, 1))
        for k, w in enumerate(filas):
            lienzo.fill(self.COLOR_ACENTO, (cx - w // 2, y0 + k, w, 1))

    # ------------------------------------------------------------------
    # Entrada
    # ------------------------------------------------------------------
    def _seleccionar_por_mouse(self, pos):
        for indice, rect in enumerate(self.botones_inicio.values()):
            if rect.collidepoint(pos):
                self.indice_seleccionado = indice
                return

    def _mover_seleccion(self, paso):
        total = len(self.botones_inicio)
        self.indice_seleccionado = (self.indice_seleccionado + paso) % total

    def manejar_evento(self, evento):
        if evento.type == pygame.MOUSEMOTION:
            self._seleccionar_por_mouse(evento.pos)
            return None

        if evento.type == pygame.KEYDOWN:
            if evento.key in (pygame.K_LEFT, pygame.K_UP, pygame.K_a, pygame.K_w):
                self._mover_seleccion(-1)
            elif evento.key in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_d, pygame.K_s):
                self._mover_seleccion(1)
            elif evento.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return list(self.botones_inicio)[self.indice_seleccionado]
            return None

        if evento.type != pygame.MOUSEBUTTONDOWN or evento.button != 1:
            return None

        for nombre, rect in self.botones_inicio.items():
            if rect.collidepoint(evento.pos):
                return nombre
        return None