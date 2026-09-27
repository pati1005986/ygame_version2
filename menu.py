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

    ANCHO_REFERENCIA = 800
    ALTO_REFERENCIA = 600
    ESCALA_MIN = 0.55
    ESCALA_MAX = 1.6

    # Paleta "punk-fanzine": colores plancha de poster, nada de degradados
    # arcoiris. Cada boton toma un color estable de aqui segun su posicion.
    PALETA_BOTONES = (
        (255, 61, 127),   # rosa neon
        (198, 255, 61),   # verde lima acido
        (61, 217, 255),   # cian electrico
        (255, 145, 41),   # naranja blaze
        (167, 96, 255),   # violeta zap
    )
    COLOR_TINTA = (24, 18, 24)           # "marcador" negro calido del contorno
    COLOR_SOMBRA_STICKER = (10, 6, 12)   # sombra dura, sin difuminado
    COLOR_DORSO_STICKER = (235, 235, 225)  # reverso de la esquina despegada
    COLOR_ACENTO = (255, 221, 87)
    COLOR_FONDO = (10, 12, 18)

    def __init__(self, ancho, alto, nombre_video="image.gif", idioma="en", escala_ui=1.0):
        self.ancho = ancho
        self.alto = alto
        self.idioma = idioma
        self.escala_ui = escala_ui
        self.ruta_video = os.path.join("assets", nombre_video)
        self.cap = None
        self.frame_actual = None
        self.ultimo_frame = 0

        self.tiempo_inicio = pygame.time.get_ticks()
        self.reloj_pulso = 0.0

        self._crear_fuentes()
        self._crear_rectangulos()

        self._cargar_video()

        # --- Cachés de renderizado ---
        # La viñeta y el degradado del panel son idénticos en cada
        # fotograma; antes se reconstruían por completo 60 veces por
        # segundo. Se calculan una sola vez aquí y en dibujar() solo se
        # hace un blit barato. Los botones se dibujan con la textura
        # comic-punk (_dibujar_boton_comic), que sí necesita
        # recalcularse cada fotograma porque se anima.
        self._capa_vineta = self._construir_vineta()
        self._capa_panel_base = self._construir_panel_base()

    def _escala(self):
        """Factor de escala relativo a la resolucion de referencia, con
        limites para que el texto nunca sea ilegible ni gigante, multiplicado
        por la preferencia de escala de UI del jugador."""
        base = max(
            self.ESCALA_MIN,
            min(
                self.ancho / self.ANCHO_REFERENCIA,
                self.alto / self.ALTO_REFERENCIA,
                self.ESCALA_MAX,
            ),
        )
        return base * self.escala_ui

    def _crear_fuentes(self):
        escala = self._escala()
        self.font_titulo = pygame.font.SysFont(
            "arialblack,arial", max(26, int(54 * escala)), bold=True
        )
        self.font_subtitulo = pygame.font.SysFont("arial", max(13, int(20 * escala)))
        self.font_prompt = pygame.font.SysFont(
            "comicsansms", max(14, int(22 * escala)), bold=True
        )

    def _crear_rectangulos(self):
        boton_ancho = int(max(110, min(170, self.ancho * 0.19)))
        boton_alto = int(max(36, min(58, self.alto * 0.1)))
        espacio_entre_botones = max(8, int(boton_ancho * 0.1))
        x_izq = (self.ancho - (boton_ancho * 3 + espacio_entre_botones * 2)) // 2
        alto_panel = max(120, min(170, int(self.alto * 0.3)))
        y_boton = self.alto - int(alto_panel * 0.55)

        self.boton_jugar = pygame.Rect(x_izq, y_boton, boton_ancho, boton_alto)
        self.boton_opciones = pygame.Rect(
            x_izq + boton_ancho + espacio_entre_botones, y_boton, boton_ancho, boton_alto
        )
        self.boton_salir = pygame.Rect(
            x_izq + (boton_ancho + espacio_entre_botones) * 2, y_boton, boton_ancho, boton_alto
        )
        self._alto_panel = alto_panel

    def establecer_idioma(self, idioma):
        self.idioma = idioma

    def establecer_escala_ui(self, escala_ui):
        self.escala_ui = escala_ui
        self._crear_fuentes()
        self._crear_rectangulos()

    def actualizar_tamano(self, ancho, alto):
        self.ancho = ancho
        self.alto = alto
        self._crear_fuentes()
        self._crear_rectangulos()
        self._capa_vineta = self._construir_vineta()
        self._capa_panel_base = self._construir_panel_base()

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
        alto_vineta = max(60, min(140, int(self.alto * 0.24)))
        capa = pygame.Surface((self.ancho, alto_vineta), pygame.SRCALPHA)
        for y in range(alto_vineta):
            alpha = int(150 * (1 - y / alto_vineta))
            pygame.draw.line(capa, (0, 0, 0, alpha), (0, y), (self.ancho, y))
        return capa

    def _construir_panel_base(self):
        """Degradado del panel inferior, sin la línea de acento (esa se
        redibuja aparte cada fotograma para poder darle un pulso de brillo
        sin tener que reconstruir todo el panel)."""
        alto_panel = getattr(self, "_alto_panel", 170)
        capa = pygame.Surface((self.ancho, alto_panel), pygame.SRCALPHA)
        for y in range(alto_panel):
            alpha = int(190 * (y / alto_panel))
            pygame.draw.line(capa, (0, 0, 0, alpha), (0, y), (self.ancho, y))
        return capa

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

    def _puntos_garabateados(self, rect, fase, semilla, amplitud=1.3, segmentos=3):
        """Devuelve los puntos de un rectangulo con bordes "temblorosos" a
        mano en vez de lineas perfectas: la base del estilo comic
        independiente/fanzine, con temblor estable por boton pero vivo
        gracias a la fase (tiempo)."""
        aleatorio = random.Random(semilla)
        esquinas = [
            (rect.left, rect.top),
            (rect.right, rect.top),
            (rect.right, rect.bottom),
            (rect.left, rect.bottom),
        ]
        puntos = []
        for i in range(4):
            x0, y0 = esquinas[i]
            x1, y1 = esquinas[(i + 1) % 4]
            fase_arista = aleatorio.uniform(0, math.tau)
            vertical = x0 == x1
            for s in range(segmentos):
                t = s / segmentos
                x = x0 + (x1 - x0) * t
                y = y0 + (y1 - y0) * t
                offset = math.sin(fase * 2.1 + fase_arista + t * 6.0) * amplitud
                if vertical:
                    x += offset
                else:
                    y += offset
                puntos.append((x, y))
        return puntos

    def _rotar_punto(self, punto, centro, angulo_grados):
        angulo = math.radians(angulo_grados)
        dx, dy = punto[0] - centro[0], punto[1] - centro[1]
        cos_a, sin_a = math.cos(angulo), math.sin(angulo)
        return (centro[0] + dx * cos_a - dy * sin_a, centro[1] + dx * sin_a + dy * cos_a)

    def _dibujar_relleno_halftone(self, superficie, puntos, color_base):
        """Relleno plano tipo poster con una trama de puntos (Ben-Day) hacia
        la esquina inferior-derecha para sugerir volumen, y un brillo
        triangular de "sticker" en la esquina superior-izquierda."""
        pygame.draw.polygon(superficie, color_base, puntos)

        min_x = min(p[0] for p in puntos)
        min_y = min(p[1] for p in puntos)
        max_x = max(p[0] for p in puntos)
        max_y = max(p[1] for p in puntos)
        interior = pygame.Rect(min_x, min_y, max_x - min_x, max_y - min_y).inflate(-5, -5)
        if interior.width < 6 or interior.height < 6:
            return

        color_trama = tuple(max(0, int(c * 0.6)) for c in color_base)
        espaciado = max(5, interior.height // 5)
        radio = max(1, espaciado * 0.26)
        fila = 0
        y = interior.top
        while y < interior.bottom:
            x = interior.left + (espaciado // 2 if fila % 2 else 0)
            while x < interior.right:
                if (x - interior.left) + (y - interior.top) > (interior.width + interior.height) * 0.34:
                    pygame.draw.circle(superficie, color_trama, (int(x), int(y)), radio)
                x += espaciado
            y += espaciado
            fila += 1

        brillo = pygame.Surface((interior.width, interior.height), pygame.SRCALPHA)
        puntos_brillo = [
            (0, interior.height * 0.42),
            (interior.width * 0.5, 0),
            (interior.width * 0.2, 0),
            (0, interior.height * 0.18),
        ]
        pygame.draw.polygon(brillo, (255, 255, 255, 75), puntos_brillo)
        superficie.blit(brillo, interior.topleft)

    def _dibujar_esquina_pelada(self, superficie, rect, hover):
        """Pequeña esquina de sticker despegandose, para el toque
        "alternativo" de collage de fanzine."""
        tam = 12 if hover else 7
        x, y = rect.right - 2, rect.top + 2
        flap = [(x, y), (x - tam, y), (x, y + tam)]
        pygame.draw.polygon(superficie, self.COLOR_SOMBRA_STICKER, [(p[0] + 1, p[1] + 1) for p in flap])
        pygame.draw.polygon(superficie, self.COLOR_DORSO_STICKER, flap)
        pygame.draw.line(superficie, self.COLOR_TINTA, (x - tam, y), (x, y + tam), 1)

    def _dibujar_salpicadura(self, superficie, rect, fase):
        """Motitas de pintura en aerosol alrededor del boton al pasar el
        mouse, como un sticker recien pegado en una pared de fanzine."""
        aleatorio = random.Random(f"splash-{rect.x}-{rect.y}-{int(fase * 6)}")
        color = random.Random(f"splashcolor-{rect.x}-{rect.y}").choice(self.PALETA_BOTONES)
        for _ in range(4):
            angulo = aleatorio.uniform(0, math.tau)
            distancia = aleatorio.uniform(rect.width * 0.4, rect.width * 0.6)
            x = rect.centerx + math.cos(angulo) * distancia
            y = rect.centery + math.sin(angulo) * distancia * 0.5
            radio = aleatorio.uniform(1.3, 3.0)
            pygame.draw.circle(superficie, color, (int(x), int(y)), radio)

    def _dibujar_boton_comic(self, superficie, rect, hover=False, radio=14):
        """Botón estilo cómic-punk/fanzine: relleno plano con trama de
        puntos, contorno "dibujado a mano" con temblor y sombra dura de
        sticker despegado."""
        indice_color = (rect.x * 7 + rect.y * 13) % len(self.PALETA_BOTONES)
        color_base = self.PALETA_BOTONES[indice_color]
        if hover:
            color_base = tuple(min(255, int(c * 1.12) + 8) for c in color_base)

        amplitud = 2.6 if hover else 1.3
        velocidad = 2.4 if hover else 1.0
        semilla = f"boton-{rect.x}-{rect.y}"
        puntos = self._puntos_garabateados(rect, self.reloj_pulso * velocidad, semilla, amplitud=amplitud)

        elevacion = -3 if hover else 0
        puntos = [(x, y + elevacion) for x, y in puntos]

        despl_sombra = (3, 4) if hover else (5, 6)
        angulo_sombra = 2.0 if hover else 3.5
        centro = (rect.centerx, rect.centery + elevacion)
        puntos_sombra = [self._rotar_punto(p, centro, angulo_sombra) for p in puntos]
        puntos_sombra = [(x + despl_sombra[0], y + despl_sombra[1]) for x, y in puntos_sombra]
        pygame.draw.polygon(superficie, self.COLOR_SOMBRA_STICKER, puntos_sombra)

        self._dibujar_relleno_halftone(superficie, puntos, color_base)
        pygame.draw.polygon(superficie, self.COLOR_TINTA, puntos, width=max(2, int(rect.height * 0.08)))

        rect_dibujo = pygame.Rect(rect.left, rect.top + elevacion, rect.width, rect.height)
        if rect.width >= 90:
            self._dibujar_esquina_pelada(superficie, rect_dibujo, hover)
        if hover:
            self._dibujar_salpicadura(superficie, rect_dibujo, self.reloj_pulso)

        return rect_dibujo

    def _texto_centrado(self, superficie, contenido, fuente, centro, color):
        sombra = fuente.render(contenido, True, self.COLOR_TINTA)
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