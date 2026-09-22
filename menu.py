import os
import math
import random

import pygame

from idioma import texto
from opciones import MenuOpciones

try:
    import cv2
except ImportError:  # pragma: no cover - opcional para la intro
    cv2 = None


class MenuInicio:
    """Pantalla de inicio con fondo animado y overlay con diseño cuidado."""

    COLOR_BOTON = (255, 138, 61)
    COLOR_BOTON_HOVER = (255, 179, 71)
    COLOR_BOTON_SOMBRA = (120, 40, 10)
    COLOR_BOTON_BORDE = (40, 20, 10)
    COLOR_TEXTO_BOTON = (40, 20, 10)
    COLOR_ACENTO = (255, 221, 87)
    COLOR_FONDO = (10, 12, 18)

    def __init__(self, ancho, alto, nombre_video="image.gif", idioma="en"):
        self.ancho = ancho
        self.alto = alto
        self.idioma = idioma
        self.ruta_video = os.path.join("assets", nombre_video)
        self.cap = None
        self.frame_actual = None
        self.ultimo_frame = 0

        self.font_titulo = pygame.font.SysFont("arialblack,arial", 54, bold=True)
        self.font_subtitulo = pygame.font.SysFont("arial", 20)
        self.font_prompt = pygame.font.SysFont("comicsansms", 22, bold=True)

        self.tiempo_inicio = pygame.time.get_ticks()
        self.reloj_pulso = 0.0

        boton_ancho = 150
        boton_alto = 54
        espacio_entre_botones = 16
        x_izq = (self.ancho - (boton_ancho * 3 + espacio_entre_botones * 2)) // 2
        y_boton = self.alto - 120

        self.boton_jugar = pygame.Rect(x_izq, y_boton, boton_ancho, boton_alto)
        self.boton_opciones = pygame.Rect(x_izq + boton_ancho + espacio_entre_botones, y_boton, boton_ancho, boton_alto)
        self.boton_salir = pygame.Rect(x_izq + (boton_ancho + espacio_entre_botones) * 2, y_boton, boton_ancho, boton_alto)

        self._cargar_video()

        # --- Cachés de renderizado ---
        # La viñeta, el degradado del panel y cada botón (normal/hover) son
        # idénticos en cada fotograma; antes se reconstruían por completo
        # 60 veces por segundo (líneas del degradado, polígonos del botón,
        # incluso el texto con font.render). Se calculan una sola vez aquí
        # y en dibujar() solo se hace un blit barato, dejando el
        # presupuesto de CPU para el pulso animado de abajo.
        self._capa_vineta = self._construir_vineta()
        self._capa_panel_base = self._construir_panel_base()
        self._cache_botones = {
            ("jugar", False): self._construir_boton(self.boton_jugar, texto(self.idioma, "play"), (2, 2, 2)),
            ("jugar", True): self._construir_boton(self.boton_jugar, texto(self.idioma, "play"), (90, 200, 255), hover=True),
            ("opciones", False): self._construir_boton(self.boton_opciones, texto(self.idioma, "options"), (2, 2, 2)),
            ("opciones", True): self._construir_boton(self.boton_opciones, texto(self.idioma, "options"), (90, 200, 255), hover=True),
            ("salir", False): self._construir_boton(self.boton_salir, texto(self.idioma, "exit"), (2, 2, 2)),
            ("salir", True): self._construir_boton(self.boton_salir, texto(self.idioma, "exit"), (255, 120, 150), hover=True),
        }

    def establecer_idioma(self, idioma):
        self.idioma = idioma
        etiquetas = {"jugar": "play", "opciones": "options", "salir": "exit"}
        self._cache_botones = {
            (nombre, hover): self._construir_boton(
                getattr(self, f"boton_{nombre}"),
                texto(self.idioma, clave),
                (90, 200, 255) if hover else (2, 2, 2),
                hover=hover,
            )
            for nombre, clave in etiquetas.items()
            for hover in (False, True)
        }

    def actualizar_tamano(self, ancho, alto):
        self.ancho = ancho
        self.alto = alto
        boton_ancho = 150
        boton_alto = 54
        espacio_entre_botones = 16
        x_izq = (self.ancho - (boton_ancho * 3 + espacio_entre_botones * 2)) // 2
        y_boton = self.alto - 120
        self.boton_jugar = pygame.Rect(x_izq, y_boton, boton_ancho, boton_alto)
        self.boton_opciones = pygame.Rect(x_izq + boton_ancho + espacio_entre_botones, y_boton, boton_ancho, boton_alto)
        self.boton_salir = pygame.Rect(x_izq + (boton_ancho + espacio_entre_botones) * 2, y_boton, boton_ancho, boton_alto)
        self._capa_vineta = self._construir_vineta()
        self._capa_panel_base = self._construir_panel_base()
        self._cache_botones = {
            ("jugar", False): self._construir_boton(self.boton_jugar, texto(self.idioma, "play"), (2, 2, 2)),
            ("jugar", True): self._construir_boton(self.boton_jugar, texto(self.idioma, "play"), (90, 200, 255), hover=True),
            ("opciones", False): self._construir_boton(self.boton_opciones, texto(self.idioma, "options"), (2, 2, 2)),
            ("opciones", True): self._construir_boton(self.boton_opciones, texto(self.idioma, "options"), (90, 200, 255), hover=True),
            ("salir", False): self._construir_boton(self.boton_salir, texto(self.idioma, "exit"), (2, 2, 2)),
            ("salir", True): self._construir_boton(self.boton_salir, texto(self.idioma, "exit"), (255, 120, 150), hover=True),
        }

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
            return

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # Redimensionar con un filtro de mejor calidad que el bilinear
        # por defecto de smoothscale evita el doble reescalado borroso.
        frame_rgb = cv2.resize(
            frame_rgb, (self.ancho, self.alto), interpolation=cv2.INTER_LANCZOS4
        )
        self.frame_actual = pygame.image.frombuffer(
            frame_rgb.tobytes(), (self.ancho, self.alto), "RGB"
        )
        self.ultimo_frame = pygame.time.get_ticks()

    def actualizar(self):
        if self.cap is not None and self.frame_actual is not None:
            ahora = pygame.time.get_ticks()
            if ahora - self.ultimo_frame >= 1000 / self.fps_video:
                self._avanzar_frame()

        # Reloj interno para las animaciones de pulso (independiente del video)
        self.reloj_pulso = (pygame.time.get_ticks() - self.tiempo_inicio) / 1000.0

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------
    def dibujar(self, superficie, mouse_pos=None):
        if self.frame_actual is not None:
            superficie.blit(self.frame_actual, (0, 0))
        else:
            superficie.fill(self.COLOR_FONDO)

        self._dibujar_vineta(superficie)
        self._dibujar_panel_inferior(superficie, mouse_pos)

    def _dibujar_vineta(self, superficie):
        """Aplica la viñeta superior precalculada (ver ``_construir_vineta``)."""
        superficie.blit(self._capa_vineta, (0, 0))

    def _construir_vineta(self):
        """Degradado que oscurece el borde superior para que el texto sea
        legible sobre cualquier fotograma del video. No depende de nada que
        cambie fotograma a fotograma, así que se calcula una sola vez."""
        capa = pygame.Surface((self.ancho, 140), pygame.SRCALPHA)
        for y in range(140):
            alpha = int(150 * (1 - y / 140))
            pygame.draw.line(capa, (0, 0, 0, alpha), (0, y), (self.ancho, y))
        return capa

    def _construir_panel_base(self):
        """Degradado del panel inferior, sin la línea de acento (esa se
        redibuja aparte cada fotograma para poder darle un pulso de brillo
        sin tener que reconstruir todo el panel)."""
        alto_panel = 170
        capa = pygame.Surface((self.ancho, alto_panel), pygame.SRCALPHA)
        for y in range(alto_panel):
            alpha = int(190 * (y / alto_panel))
            pygame.draw.line(capa, (0, 0, 0, alpha), (0, y), (self.ancho, y))
        return capa

    def _construir_boton(self, rect, texto, color, hover=False):
        """Precalcula la forma del botón con capas abstractas y colores vivos."""
        escala = 1.12 if hover else 1.0
        forma = pygame.Surface((int(rect.width * escala), int(rect.height * escala)), pygame.SRCALPHA)
        cx = forma.get_width() // 2
        cy = forma.get_height() // 2

        puntos = [
            (cx - 70, 8),
            (cx + 60, 0),
            (cx + 78, cy - 10),
            (cx + 70, cy + 24),
            (cx + 82, cy + 32),
            (cx + 52, forma.get_height() - 8),
            (cx - 58, forma.get_height() - 2),
            (cx - 75, cy + 20),
            (cx - 84, cy - 6),
        ]

        paleta = [
            (255, 108, 92),
            (255, 201, 90),
            (98, 224, 168),
            (128, 145, 255),
            (255, 117, 190),
        ]
        for indice, tono in enumerate(paleta):
            capa = pygame.Surface((forma.get_width(), forma.get_height()), pygame.SRCALPHA)
            rect_parche = pygame.Rect(8 + indice * 10, 4 + indice * 2, forma.get_width() - 14 - indice * 18, forma.get_height() - 10)
            pygame.draw.rect(capa, (*tono, 150 + indice * 18), rect_parche, border_radius=18)
            pygame.draw.ellipse(capa, (*tono, 120), (0, 0, forma.get_width(), forma.get_height() * 0.6))
            forma.blit(capa, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        pygame.draw.polygon(forma, (*color, 200), puntos)
        pygame.draw.polygon(forma, (255, 255, 255, 60), [(cx - 60, 14), (cx + 58, 10), (cx + 40, cy - 4), (cx - 48, cy + 6)], 0)
        pygame.draw.polygon(forma, (255, 255, 255, 70), [(cx - 52, cy), (cx + 68, cy - 10), (cx + 52, forma.get_height() - 10), (cx - 44, forma.get_height() - 8)], 0)

        barras = pygame.Surface((forma.get_width(), forma.get_height()), pygame.SRCALPHA)
        for i in range(6):
            x = 20 + i * 12
            ancho = 12 + i * 3
            alto = forma.get_height() * (0.24 + i * 0.07)
            y = forma.get_height() - alto - 6
            pygame.draw.ellipse(barras, (*self._hue_to_rgb(0.15 + i * 0.12, 0.8, 0.7), 110), (x, y, ancho, alto))
        forma.blit(barras, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        sombra = pygame.Surface((forma.get_width(), forma.get_height()), pygame.SRCALPHA)
        pygame.draw.polygon(sombra, (0, 0, 0, 90), puntos)

        label = self.font_prompt.render(texto, True, (255, 255, 255))

        return {
            "forma": forma,
            "sombra": sombra,
            "label": label,
            "offset_forma": (
                -int((escala - 1) * rect.width / 2),
                -int((escala - 1) * rect.height / 2),
            ),
            "offset_sombra": (8, 10),
        }

    def _dibujar_panel_inferior(self, superficie, mouse_pos=None):
        superficie.blit(self._capa_panel_base, (0, self.alto - self._capa_panel_base.get_height()))

        # Pulso barato (un valor de seno por fotograma) para que la línea
        # de acento y el resplandor de los botones respiren un poco en vez
        # de quedar completamente estáticos, sin recrear ninguna Surface.
        pulso = 0.65 + 0.35 * math.sin(self.reloj_pulso * 2.4)
        y_linea = self.alto - self._capa_panel_base.get_height()
        alpha_acento = int(140 + 100 * pulso)
        pygame.draw.line(
            superficie, (*self.COLOR_ACENTO, alpha_acento), (0, y_linea), (self.ancho, y_linea), 2
        )

        for rect, nombre in (
            (self.boton_jugar, "jugar"),
            (self.boton_opciones, "opciones"),
            (self.boton_salir, "salir"),
        ):
            hover = mouse_pos is not None and rect.collidepoint(mouse_pos)
            rect_dibujo = self._dibujar_boton_comic(superficie, rect, hover)
            clave = {"jugar": "play", "opciones": "options", "salir": "exit"}[nombre]
            self._texto_centrado(
                superficie,
                texto(self.idioma, clave),
                self.font_prompt,
                rect_dibujo.center,
                (255, 255, 255),
            )

    def _color_arcoiris_pixel(self, x_norm, y_norm, fase):
        """Calcula un color de arcoíris tipo 8-bit para una celda de pixel,
        con bandas diagonales que se desplazan con el tiempo (reutiliza el
        conversor HSL->RGB ya definido en esta clase)."""
        matiz = (x_norm * 0.55 + y_norm * 0.2 + fase * 0.12) % 1.0
        return self._hue_to_rgb(matiz, 0.85, 0.55)

    def _generar_textura_boton_pixelada(self, ancho, alto, fase, hover, semilla):
        """Genera la textura arcoíris pixelada de un botón como una superficie
        de baja resolución, lista para escalarse sin suavizado (look 8-bit)."""
        tam_pixel = 7
        columnas = max(4, ancho // tam_pixel)
        filas = max(4, alto // tam_pixel)

        lienzo_bajo = pygame.Surface((columnas, filas))
        aleatorio_destellos = random.Random(semilla)

        for fila in range(filas):
            for col in range(columnas):
                en_borde = fila in (0, 1, filas - 2, filas - 1) or col in (0, 1, columnas - 2, columnas - 1)
                if en_borde:
                    lienzo_bajo.set_at((col, fila), self.COLOR_BOTON_BORDE)
                    continue
                x_norm = col / max(1, columnas - 1)
                y_norm = fila / max(1, filas - 1)
                color = self._color_arcoiris_pixel(x_norm, y_norm, fase)
                # franja de "brillo" pixelado tipo comic en la parte superior
                if y_norm < 0.28 and (col + fila) % 3 != 0:
                    color = tuple(min(255, c + 70) for c in color)
                lienzo_bajo.set_at((col, fila), color)

        # destellos blancos tipo "estrellita" 8-bit, más activos con el hover
        num_destellos = 4 if hover else 2
        for _ in range(num_destellos):
            col = aleatorio_destellos.randint(2, columnas - 3)
            fila = aleatorio_destellos.randint(2, filas - 3)
            lienzo_bajo.set_at((col, fila), (255, 255, 255))

        return pygame.transform.scale(lienzo_bajo, (ancho, alto))

    def _dibujar_boton_comic(self, superficie, rect, hover=False, radio=14):
        """Botón arcoíris pixelado y caricaturesco: relleno tipo 8-bit con
        bandas de color que se desplazan y contorno grueso estilo comic."""
        desplazamiento_sombra = 6 if not hover else 3
        rect_sombra = rect.move(desplazamiento_sombra, desplazamiento_sombra)
        pygame.draw.rect(superficie, self.COLOR_BOTON_SOMBRA, rect_sombra)

        rect_dibujo = rect.move(-3 if hover else 0, -3 if hover else 0)

        velocidad_desfile = 1.4 if hover else 0.7
        semilla_destellos = f"boton-{rect.x}-{rect.y}-{int(self.reloj_pulso * (10 if hover else 3))}"
        textura = self._generar_textura_boton_pixelada(
            rect_dibujo.width,
            rect_dibujo.height,
            self.reloj_pulso * velocidad_desfile,
            hover,
            semilla_destellos,
        )
        superficie.blit(textura, rect_dibujo.topleft)

        pygame.draw.rect(superficie, self.COLOR_BOTON_BORDE, rect_dibujo, width=3)
        return rect_dibujo

    def _hue_to_rgb(self, hue, saturation, lightness):
        hue = hue % 1.0
        c = (1 - abs(2 * lightness - 1)) * saturation
        x = c * (1 - abs((hue * 6) % 2 - 1))
        m = lightness - c / 2

        if 0 <= hue < 1 / 6:
            r, g, b = c, x, 0
        elif hue < 2 / 6:
            r, g, b = x, c, 0
        elif hue < 3 / 6:
            r, g, b = 0, c, x
        elif hue < 4 / 6:
            r, g, b = 0, x, c
        elif hue < 5 / 6:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x

        return (int(round((r + m) * 255)), int(round((g + m) * 255)), int(round((b + m) * 255)))

    def _texto_con_sombra(self, superficie, texto, font, color, centro, offset_sombra=(2, 2)):
        sombra = font.render(texto, True, (0, 0, 0))
        sombra.set_alpha(160)
        superficie.blit(
            sombra,
            sombra.get_rect(center=(centro[0] + offset_sombra[0], centro[1] + offset_sombra[1])),
        )
        principal = font.render(texto, True, color)
        superficie.blit(principal, principal.get_rect(center=centro))

    def _texto_centrado(self, superficie, contenido, fuente, centro, color):
        sombra = fuente.render(contenido, True, self.COLOR_BOTON_BORDE)
        superficie.blit(sombra, sombra.get_rect(center=(centro[0] + 1, centro[1] + 1)))
        imagen = fuente.render(contenido, True, color)
        superficie.blit(imagen, imagen.get_rect(center=centro))

    # ------------------------------------------------------------------
    def manejar_evento(self, evento):
        if evento.type != pygame.MOUSEBUTTONDOWN or evento.button != 1:
            return None

        if self.boton_jugar.collidepoint(evento.pos):
            return "jugar"
        if self.boton_opciones.collidepoint(evento.pos):
            return "opciones"
        if self.boton_salir.collidepoint(evento.pos):
            return "salir"
        return None