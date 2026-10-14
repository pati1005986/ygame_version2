"""Pantalla final y carrusel de GIFs de créditos."""

import os
import random

import cv2
import numpy as np
import pygame


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
    """Dibuja los créditos y reproduce en carrusel los GIF usados por el juego."""

    COLOR_ORO = (232, 205, 153)
    COLOR_ORO_SUAVE = (126, 104, 68)
    COLOR_TEXTO = (247, 242, 230)

    def __init__(self, ancho, alto, carpeta_assets, gifs):
        self.ancho = ancho
        self.alto = alto
        self.carpeta_assets = carpeta_assets
        self.gifs = tuple(dict.fromkeys(gifs))
        self.duracion_gif = 3.5
        self.indice_gif = None
        self.fotogramas = []
        self.duracion_fotograma = 0.1

        self.fuente_sobrelinea = pygame.font.SysFont("georgia", 16)
        self.fuente_titulo = pygame.font.SysFont("georgia", 52, bold=True)
        self.fuente_rol = pygame.font.SysFont("georgia", 20)
        self.fuente_nombre = pygame.font.SysFont("georgia", 32)
        self.fuente_pie = pygame.font.SysFont("georgia", 13)

        self.tarjetas = (
            ("DISEÑO Y PROGRAMACIÓN", "MR PATI"),
            ("ARTE Y ANIMACIÓN", "MR PATI"),
            ("HISTORIA Y CONCEPTO", "MR PATI"),
            ("DISEÑO DE NIVELES", "MR PATI"),
            ("HECHO CON", "Python · Pygame · OpenCV · NumPy"),
            ("GRACIAS POR JUGAR", "Gracias por llegar hasta el final"),
        )
        self.duracion_fundido = 0.45
        self.duracion_entrada = 1.6

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

    def dibujar(self, lienzo, tiempo_creditos):
        duracion = self.duracion_gif
        indice = int(tiempo_creditos / duracion) % len(self.gifs)
        self._cargar_gif(indice)
        tiempo_turno = tiempo_creditos % duracion
        centro_x = self.ancho // 2

        if self.fondo is None or self.fondo.get_size() != (self.ancho, self.alto):
            self.fondo = self._crear_fondo()
        lienzo.blit(self.fondo, (0, 0))
        self._dibujar_estrellas(lienzo, tiempo_creditos)

        sobrelinea = self._texto(
            self.fuente_sobrelinea,
            "UNA PRODUCCIÓN INDEPENDIENTE",
            self.COLOR_ORO_SUAVE,
        )
        lienzo.blit(
            sobrelinea,
            sobrelinea.get_rect(center=(centro_x, int(self.alto * 0.052))),
        )
        y_titulo = int(self.alto * 0.125)
        titulo = self._texto(self.fuente_titulo, "MR PATI", self.COLOR_TEXTO)
        lienzo.blit(titulo, titulo.get_rect(center=(centro_x, y_titulo)))
        self._dibujar_adorno(
            lienzo, centro_x, y_titulo + 34, 115, self.COLOR_ORO_SUAVE
        )

        centro_gif = (centro_x, int(self.alto * 0.43))
        marco = pygame.Rect(0, 0, 418, 278)
        marco.center = centro_gif
        pygame.draw.rect(
            lienzo, (4, 5, 12), marco.inflate(16, 16), border_radius=20
        )
        pygame.draw.rect(lienzo, (14, 16, 30), marco, border_radius=14)
        pygame.draw.rect(
            lienzo,
            self.COLOR_ORO_SUAVE,
            marco.inflate(10, 10),
            1,
            border_radius=17,
        )
        pygame.draw.rect(lienzo, self.COLOR_ORO, marco, 3, border_radius=14)

        fotograma = self.fotogramas[
            int(tiempo_creditos / self.duracion_fotograma) % len(self.fotogramas)
        ]
        zona_gif = fotograma.get_rect(center=centro_gif)
        lienzo.blit(fotograma, zona_gif)

        if tiempo_turno < self.duracion_fundido:
            factor = 1 - tiempo_turno / self.duracion_fundido
        elif tiempo_turno > duracion - self.duracion_fundido:
            factor = (tiempo_turno - (duracion - self.duracion_fundido)) / self.duracion_fundido
        else:
            factor = 0
        if factor > 0:
            lienzo.blit(self._velo_negro(zona_gif.size, 255 * factor), zona_gif)

        barra = pygame.Rect(0, 0, marco.width - 40, 4)
        barra.midtop = (centro_x, marco.bottom + 14)
        pygame.draw.rect(lienzo, (40, 44, 66), barra, border_radius=2)
        relleno = barra.copy()
        relleno.width = max(4, int(barra.width * (indice + 1) / len(self.gifs)))
        pygame.draw.rect(lienzo, self.COLOR_ORO, relleno, border_radius=2)
        pie = self._texto(
            self.fuente_pie,
            f"RECUERDO {indice + 1:02d}  /  {len(self.gifs):02d}",
            self.COLOR_ORO_SUAVE,
        )
        lienzo.blit(pie, pie.get_rect(center=(centro_x, barra.bottom + 19)))

        rol, nombre = self.tarjetas[
            int(tiempo_creditos / duracion) % len(self.tarjetas)
        ]
        y_rol = barra.bottom + 45
        texto_rol = self._texto(self.fuente_rol, rol, self.COLOR_ORO)
        texto_nombre = self._texto(self.fuente_nombre, nombre, self.COLOR_TEXTO)
        ancho_maximo = self.ancho - 120
        if texto_nombre.get_width() > ancho_maximo:
            escala = ancho_maximo / texto_nombre.get_width()
            texto_nombre = pygame.transform.smoothscale(
                texto_nombre,
                (ancho_maximo, max(1, int(texto_nombre.get_height() * escala))),
            )
        zona_tarjeta = pygame.Rect(0, 0, self.ancho - 120, 74)
        zona_tarjeta.midtop = (centro_x, y_rol - 18)
        tarjeta = pygame.Surface(zona_tarjeta.size, pygame.SRCALPHA)
        tarjeta.blit(texto_rol, texto_rol.get_rect(center=(zona_tarjeta.width // 2, 17)))
        tarjeta.blit(
            texto_nombre,
            texto_nombre.get_rect(center=(zona_tarjeta.width // 2, 51)),
        )
        if tiempo_turno < self.duracion_fundido:
            alpha_tarjeta = int(255 * tiempo_turno / self.duracion_fundido)
        elif tiempo_turno > duracion - self.duracion_fundido:
            alpha_tarjeta = int(
                255 * (duracion - tiempo_turno) / self.duracion_fundido
            )
        else:
            alpha_tarjeta = 255
        tarjeta.set_alpha(alpha_tarjeta)
        lienzo.blit(tarjeta, zona_tarjeta)

        if tiempo_creditos < self.duracion_entrada:
            progreso = tiempo_creditos / self.duracion_entrada
            lienzo.blit(
                self._velo_negro((self.ancho, self.alto), 255 * (1 - progreso)),
                (0, 0),
            )
        pygame.draw.rect(lienzo, (0, 0, 0), (0, 0, self.ancho, 24))
        pygame.draw.rect(
            lienzo, (0, 0, 0), (0, self.alto - 24, self.ancho, 24)
        )

    def _texto(self, fuente, texto, color):
        clave = (id(fuente), texto, color)
        superficie = self.cache_texto.get(clave)
        if superficie is None:
            superficie = fuente.render(texto, True, color)
            self.cache_texto[clave] = superficie
        return superficie

    def _velo_negro(self, tamano, alpha):
        velo = self.velos.get(tamano)
        if velo is None:
            velo = pygame.Surface(tamano)
            velo.fill((0, 0, 0))
            self.velos[tamano] = velo
        velo.set_alpha(max(0, min(255, int(alpha))))
        return velo

    def _crear_fondo(self):
        fondo = pygame.Surface((self.ancho, self.alto))
        arriba, abajo = (8, 10, 24), (26, 16, 40)
        for y in range(self.alto):
            t = y / max(1, self.alto - 1)
            color = tuple(int(a + (b - a) * t) for a, b in zip(arriba, abajo))
            pygame.draw.line(fondo, color, (0, y), (self.ancho, y))
        borde = pygame.Surface((self.ancho, self.alto), pygame.SRCALPHA)
        for i in range(36):
            alpha = int(90 * (1 - i / 36) ** 2)
            pygame.draw.rect(
                borde,
                (0, 0, 0, alpha),
                (i, i, self.ancho - 2 * i, self.alto - 2 * i),
                1,
            )
        fondo.blit(borde, (0, 0))
        return fondo

    def _dibujar_estrellas(self, lienzo, tiempo):
        for x, y, radio, fase, velocidad in self.estrellas:
            brillo = 0.5 + 0.5 * np.sin(tiempo * velocidad + fase)
            nivel = int(70 + 150 * brillo)
            color = (nivel, nivel, min(255, nivel + 30))
            posicion = (int(x * self.ancho), int(y * self.alto))
            if radio == 1:
                lienzo.set_at(posicion, color)
            else:
                pygame.draw.circle(lienzo, color, posicion, 1)
                pygame.draw.circle(lienzo, color, posicion, radio, 1)

    @staticmethod
    def _dibujar_adorno(lienzo, centro_x, y, semiancho, color):
        hueco = 10
        pygame.draw.line(
            lienzo, color, (centro_x - semiancho, y), (centro_x - hueco - 6, y), 1
        )
        pygame.draw.line(
            lienzo, color, (centro_x + hueco + 6, y), (centro_x + semiancho, y), 1
        )
        pygame.draw.polygon(
            lienzo,
            color,
            [
                (centro_x, y - 5),
                (centro_x + 6, y),
                (centro_x, y + 5),
                (centro_x - 6, y),
            ],
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
