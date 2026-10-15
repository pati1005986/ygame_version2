"""Pantalla final y carrusel de GIFs de créditos."""

import os
import random

import cv2
import numpy as np
import pygame


TEXTOS_CREDITOS = {
    "en": {
        "production": "AN INDEPENDENT PRODUCTION",
        "design": "DESIGN & PROGRAMMING",
        "art": "ART & ANIMATION",
        "story": "STORY & CONCEPT",
        "levels": "LEVEL DESIGN",
        "made_with": "MADE WITH",
        "thanks": "THANKS FOR PLAYING",
        "thanks_subtitle": "Thanks for making it to the end",
        "memory": "MEMORY",
    },
    "es": {
        "production": "UNA PRODUCCIÓN INDEPENDIENTE",
        "design": "DISEÑO Y PROGRAMACIÓN",
        "art": "ARTE Y ANIMACIÓN",
        "story": "HISTORIA Y CONCEPTO",
        "levels": "DISEÑO DE NIVELES",
        "made_with": "HECHO CON",
        "thanks": "GRACIAS POR JUGAR",
        "thanks_subtitle": "Gracias por llegar hasta el final",
        "memory": "RECUERDO",
    },
    "pt": {
        "production": "UMA PRODUÇÃO INDEPENDENTE",
        "design": "DESIGN E PROGRAMAÇÃO",
        "art": "ARTE E ANIMAÇÃO",
        "story": "HISTÓRIA E CONCEITO",
        "levels": "DESIGN DE NÍVEIS",
        "made_with": "FEITO COM",
        "thanks": "OBRIGADO POR JOGAR",
        "thanks_subtitle": "Obrigado por chegar até o final",
        "memory": "LEMBRANÇA",
    },
    "ru": {
        "production": "НЕЗАВИСИМОЕ ПРОИЗВОДСТВО",
        "design": "ДИЗАЙН И ПРОГРАММИРОВАНИЕ",
        "art": "ИСКУССТВО И АНИМАЦИЯ",
        "story": "ИСТОРИЯ И КОНЦЕПЦИЯ",
        "levels": "ДИЗАЙН УРОВНЕЙ",
        "made_with": "СОЗДАНО С ПОМОЩЬЮ",
        "thanks": "СПАСИБО ЗА ИГРУ",
        "thanks_subtitle": "Спасибо, что дошли до конца",
        "memory": "ВОСПОМИНАНИЕ",
    },
}


def cargar_gif(ruta, tamano, ajustar_aspecto=False):
    """Carga los fotogramas de un GIF para animarlo en Pygame."""
    captura = cv2.VideoCapture(ruta)
    if not captura.isOpened():
        return [], 0.1

    fps = captura.get(cv2.CAP_PROP_FPS) or 10.0
    fotogramas = []
    while True:
        ok, fotograma = captura.read()
        if not ok:
            break
        fotograma = cv2.cvtColor(fotograma, cv2.COLOR_BGR2RGB)
        tamano_fotograma = tamano
        if ajustar_aspecto:
            alto_original, ancho_original = fotograma.shape[:2]
            escala = min(
                tamano[0] / ancho_original,
                tamano[1] / alto_original,
            )
            tamano_fotograma = (
                max(1, int(ancho_original * escala)),
                max(1, int(alto_original * escala)),
            )
        fotograma = cv2.resize(
            fotograma, tamano_fotograma, interpolation=cv2.INTER_NEAREST
        )
        superficie = pygame.image.frombuffer(
            fotograma.tobytes(), tamano_fotograma, "RGB"
        )
        fotogramas.append(
            superficie.convert()
            if pygame.display.get_surface()
            else superficie.copy()
        )
    captura.release()
    return fotogramas, 1.0 / fps


class CreditosFinales:
    """Créditos estilo película con acabado pixel art y carrusel de GIFs."""

    COLOR_ORO = (232, 205, 153)
    COLOR_ORO_SUAVE = (126, 104, 68)
    COLOR_TEXTO = (247, 242, 230)
    COLOR_SOMBRA = (52, 40, 28)
    PX = 4  # tamaño del "píxel" de la interfaz

    def __init__(self, ancho, alto, carpeta_assets, gifs):
        self.ancho = ancho
        self.alto = alto
        self.carpeta_assets = carpeta_assets
        self.gifs = tuple(dict.fromkeys(gifs))
        self.duracion_gif = 3.5
        self.indice_gif = None
        self.fotogramas = []
        self.duracion_fotograma = 0.1

        # Tipografía sencilla: monoespaciada y sin suavizado; se renderiza
        # pequeña y se amplía en enteros para que quede con aspecto pixelado.
        familias = "couriernew,consolas,dejavusansmono,liberationmono,monospace"
        self.fuente_sobrelinea = pygame.font.SysFont(familias, 10, bold=True)
        self.fuente_titulo = pygame.font.SysFont(familias, 13, bold=True)
        self.fuente_rol = pygame.font.SysFont(familias, 12, bold=True)
        self.fuente_nombre = pygame.font.SysFont(familias, 14, bold=True)
        self.fuente_pie = pygame.font.SysFont(familias, 9, bold=True)

        self.duracion_fundido = 0.45
        self.duracion_entrada = 1.6
        self.alto_barra_cine = 28

        generador = random.Random(2024)
        self.estrellas = [
            (
                generador.random(),
                generador.random(),
                generador.choice((1, 1, 1, 2)),
                generador.uniform(0.0, 6.28),
                generador.uniform(0.8, 2.4),
            )
            for _ in range(90)
        ]
        self.cache_texto = {}
        self.fondo = None
        self.velos = {}

    def listos(self, tiempo_transcurrido_ms, duracion_animacion):
        return tiempo_transcurrido_ms >= duracion_animacion * 1000

    # ------------------------------------------------------------------
    def dibujar(self, lienzo, tiempo_creditos, idioma="es"):
        textos = TEXTOS_CREDITOS.get(idioma, TEXTOS_CREDITOS["en"])
        px = self.PX
        duracion = self.duracion_gif
        indice = int(tiempo_creditos / duracion) % len(self.gifs)
        self._cargar_gif(indice)
        tiempo_turno = tiempo_creditos % duracion
        centro_x = self.ancho // 2

        if self.fondo is None or self.fondo.get_size() != (self.ancho, self.alto):
            self.fondo = self._crear_fondo()
        lienzo.blit(self.fondo, (0, 0))
        self._dibujar_estrellas(lienzo, tiempo_creditos)

        # Encabezado
        sobrelinea = self._texto(
            self.fuente_sobrelinea,
            textos["production"],
            self.COLOR_ORO_SUAVE,
            2,
        )
        lienzo.blit(
            sobrelinea,
            sobrelinea.get_rect(center=(centro_x, int(self.alto * 0.075))),
        )
        y_titulo = int(self.alto * 0.15)
        sombra = self._texto(self.fuente_titulo, "MR PATI", self.COLOR_SOMBRA, 4)
        titulo = self._texto(self.fuente_titulo, "MR PATI", self.COLOR_TEXTO, 4)
        lienzo.blit(sombra, sombra.get_rect(center=(centro_x + px, y_titulo + px)))
        lienzo.blit(titulo, titulo.get_rect(center=(centro_x, y_titulo)))
        self._dibujar_adorno(
            lienzo, centro_x, y_titulo + 9 * px, 112, self.COLOR_ORO_SUAVE
        )

        # Marco del GIF (esquinas escalonadas + perforaciones de película)
        centro_gif = (centro_x, int(self.alto * 0.45))
        marco = pygame.Rect(0, 0, 418, 278)
        marco.center = centro_gif
        self._rect_muescas(lienzo, (4, 5, 12), marco.inflate(6 * px, 6 * px))
        self._rect_muescas(lienzo, self.COLOR_ORO_SUAVE, marco.inflate(4 * px, 4 * px))
        self._rect_muescas(lienzo, (4, 5, 12), marco.inflate(3 * px, 3 * px))
        self._rect_muescas(lienzo, self.COLOR_ORO, marco.inflate(2 * px, 2 * px))
        self._rect_muescas(lienzo, (14, 16, 30), marco)
        self._dibujar_perforaciones(lienzo, marco)

        fotograma = self.fotogramas[
            int(tiempo_creditos / self.duracion_fotograma) % len(self.fotogramas)
        ]
        zona_gif = fotograma.get_rect(center=centro_gif)
        lienzo.blit(fotograma, zona_gif)

        # Fundido entre recuerdos (por niveles, como película pixelada)
        if tiempo_turno < self.duracion_fundido:
            factor = 1 - tiempo_turno / self.duracion_fundido
        elif tiempo_turno > duracion - self.duracion_fundido:
            factor = (
                tiempo_turno - (duracion - self.duracion_fundido)
            ) / self.duracion_fundido
        else:
            factor = 0
        if factor > 0:
            lienzo.blit(self._velo_negro(zona_gif.size, 255 * factor), zona_gif)

        # Barra de progreso segmentada
        total = len(self.gifs)
        separacion = px
        ancho_barra = marco.width - 40
        ancho_seg = max(px, (ancho_barra - separacion * (total - 1)) // total)
        ancho_real = ancho_seg * total + separacion * (total - 1)
        x0 = centro_x - ancho_real // 2
        y_barra = marco.bottom + 4 * px
        for i in range(total):
            if i == indice:
                color = self.COLOR_ORO
            elif i < indice:
                color = self.COLOR_ORO_SUAVE
            else:
                color = (40, 44, 66)
            pygame.draw.rect(
                lienzo, color, (x0 + i * (ancho_seg + separacion), y_barra, ancho_seg, 2 * px)
            )
        pie = self._texto(
            self.fuente_pie,
            f"{textos['memory']} {indice + 1:02d} / {total:02d}",
            self.COLOR_ORO_SUAVE,
            2,
        )
        lienzo.blit(pie, pie.get_rect(center=(centro_x, y_barra + 2 * px + 14)))

        # Tarjeta de créditos
        tarjetas = (
            (textos["design"], "MR PATI"),
            (textos["art"], "MR PATI"),
            (textos["story"], "MR PATI"),
            (textos["levels"], "MR PATI"),
            (textos["made_with"], "Python · Pygame · OpenCV · NumPy"),
            (textos["thanks"], textos["thanks_subtitle"]),
        )
        rol, nombre = tarjetas[int(tiempo_creditos / duracion) % len(tarjetas)]
        ancho_maximo = self.ancho - 120
        texto_rol = self._texto(self.fuente_rol, rol, self.COLOR_ORO, 2, ancho_maximo)
        texto_nombre = self._texto(
            self.fuente_nombre, nombre, self.COLOR_TEXTO, 2, ancho_maximo
        )
        zona_tarjeta = pygame.Rect(0, 0, self.ancho - 120, 80)
        zona_tarjeta.midtop = (centro_x, y_barra + 2 * px + 32)
        tarjeta = pygame.Surface(zona_tarjeta.size, pygame.SRCALPHA)
        tarjeta.blit(texto_rol, texto_rol.get_rect(center=(zona_tarjeta.width // 2, 16)))
        tarjeta.blit(
            texto_nombre, texto_nombre.get_rect(center=(zona_tarjeta.width // 2, 54))
        )
        if tiempo_turno < self.duracion_fundido:
            alpha_tarjeta = 255 * tiempo_turno / self.duracion_fundido
        elif tiempo_turno > duracion - self.duracion_fundido:
            alpha_tarjeta = 255 * (duracion - tiempo_turno) / self.duracion_fundido
        else:
            alpha_tarjeta = 255
        tarjeta.set_alpha(self._nivel_alpha(alpha_tarjeta))
        lienzo.blit(tarjeta, zona_tarjeta)

        # Entrada desde negro
        if tiempo_creditos < self.duracion_entrada:
            progreso = tiempo_creditos / self.duracion_entrada
            lienzo.blit(
                self._velo_negro((self.ancho, self.alto), 255 * (1 - progreso)),
                (0, 0),
            )

        # Franjas de cine
        barra_cine = self.alto_barra_cine
        pygame.draw.rect(lienzo, (0, 0, 0), (0, 0, self.ancho, barra_cine))
        pygame.draw.rect(
            lienzo, (0, 0, 0), (0, self.alto - barra_cine, self.ancho, barra_cine)
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _nivel_alpha(alpha, niveles=8):
        """Cuantiza la opacidad para que los fundidos se vean escalonados."""
        paso = 256 / niveles
        return max(0, min(255, int(round(alpha / paso) * paso)))

    def _texto(self, fuente, texto, color, escala=1, ancho_max=None):
        clave = (id(fuente), texto, color, escala, ancho_max)
        superficie = self.cache_texto.get(clave)
        if superficie is None:
            base = fuente.render(texto, False, color)
            superficie = base
            for e in range(escala, 0, -1):
                if ancho_max is None or base.get_width() * e <= ancho_max:
                    superficie = pygame.transform.scale(
                        base, (base.get_width() * e, base.get_height() * e)
                    )
                    break
            else:
                superficie = pygame.transform.scale(
                    base,
                    (
                        ancho_max,
                        max(1, int(base.get_height() * ancho_max / base.get_width())),
                    ),
                )
            self.cache_texto[clave] = superficie
        return superficie

    def _velo_negro(self, tamano, alpha):
        velo = self.velos.get(tamano)
        if velo is None:
            velo = pygame.Surface(tamano)
            velo.fill((0, 0, 0))
            self.velos[tamano] = velo
        velo.set_alpha(self._nivel_alpha(alpha))
        return velo

    def _crear_fondo(self):
        px = self.PX
        fondo = pygame.Surface((self.ancho, self.alto))
        arriba, abajo = (8, 10, 24), (26, 16, 40)
        banda = 2 * px
        for y in range(0, self.alto, banda):
            t = y / max(1, self.alto - 1)
            color = tuple(int(a + (b - a) * t) for a, b in zip(arriba, abajo))
            pygame.draw.rect(fondo, color, (0, y, self.ancho, banda))

        # Viñeta escalonada
        capa = pygame.Surface((self.ancho, self.alto), pygame.SRCALPHA)
        pasos = 9
        for i in range(pasos):
            alpha = int(110 * (1 - i / pasos) ** 2)
            pygame.draw.rect(
                capa,
                (0, 0, 0, alpha),
                (i * px, i * px, self.ancho - 2 * i * px, self.alto - 2 * i * px),
                px,
            )
        # Líneas de escaneo suaves
        for y in range(0, self.alto, px):
            pygame.draw.rect(capa, (0, 0, 0, 34), (0, y, self.ancho, 1))
        fondo.blit(capa, (0, 0))
        return fondo

    def _dibujar_estrellas(self, lienzo, tiempo):
        px = self.PX
        for x, y, radio, fase, velocidad in self.estrellas:
            brillo = 0.5 + 0.5 * np.sin(tiempo * velocidad + fase)
            nivel = (70, 130, 190, 235)[min(3, int(brillo * 4))]
            color = (nivel, nivel, min(255, nivel + 30))
            cx = (int(x * self.ancho) // px) * px
            cy = (int(y * self.alto) // px) * px
            if radio == 1:
                pygame.draw.rect(lienzo, color, (cx, cy, px // 2, px // 2))
            else:
                pygame.draw.rect(lienzo, color, (cx, cy, px, px))
                if brillo > 0.8:
                    for dx, dy in ((-px, 0), (px, 0), (0, -px), (0, px)):
                        pygame.draw.rect(
                            lienzo, self.COLOR_ORO_SUAVE, (cx + dx, cy + dy, px, px)
                        )

    def _rect_muescas(self, lienzo, color, rect, muesca=None):
        """Rectángulo relleno con esquinas escalonadas (look pixel art)."""
        n = muesca or self.PX
        pygame.draw.rect(lienzo, color, (rect.x + n, rect.y, rect.w - 2 * n, rect.h))
        pygame.draw.rect(lienzo, color, (rect.x, rect.y + n, rect.w, rect.h - 2 * n))

    def _dibujar_perforaciones(self, lienzo, marco):
        """Agujeros de película a los lados del marco, si caben en pantalla."""
        px = self.PX
        x_izq = marco.left - 8 * px
        x_der = marco.right + 8 * px - px * 2
        if x_izq < 0 or x_der + 2 * px > self.ancho:
            return
        y = marco.top - 2 * px
        while y + 3 * px <= marco.bottom + 2 * px:
            for x in (x_izq, x_der):
                pygame.draw.rect(lienzo, self.COLOR_ORO_SUAVE, (x, y, 2 * px, 3 * px))
                pygame.draw.rect(lienzo, (8, 10, 24), (x + 2, y + 2, 2 * px - 4, 3 * px - 4))
            y += 6 * px

    def _dibujar_adorno(self, lienzo, centro_x, y, semiancho, color):
        px = self.PX
        # Líneas punteadas en bloques
        for lado in (-1, 1):
            x = 3 * px
            while x < semiancho:
                bx = centro_x + lado * x - (px if lado < 0 else 0)
                pygame.draw.rect(lienzo, color, (bx, y - px // 2, px, px // 2 * 2))
                x += 2 * px
        # Rombo de píxeles
        filas = ((0, 1), (-1, 3), (0, 1))
        for fila, (inicio, ancho_f) in zip((-px, 0, px), filas):
            pygame.draw.rect(
                lienzo,
                self.COLOR_ORO,
                (centro_x - (ancho_f * px) // 2, y + fila - px // 2, ancho_f * px, px),
            )

    def _cargar_gif(self, indice):
        if indice == self.indice_gif:
            return
        nombre = self.gifs[indice]
        ruta = os.path.join(self.carpeta_assets, nombre)
        if not os.path.isfile(ruta):
            raise FileNotFoundError(f"No se encontró el GIF de créditos: {ruta}")
        self.fotogramas, self.duracion_fotograma = cargar_gif(
            ruta, (390, 250), ajustar_aspecto=True
        )
        if not self.fotogramas:
            raise RuntimeError(f"No se pudieron cargar los fotogramas de {ruta}")
        self.indice_gif = indice