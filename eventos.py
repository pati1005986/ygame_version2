"""Procesamiento de entradas y efectos visuales del juego."""

from dataclasses import dataclass
import os
import random
from typing import Any

import cv2
import numpy as np
import pygame

from despertar import CarboncilloAnimado


ESTADO_MENU = "menu"
ESTADO_ADVERTENCIA = "advertencia"
ESTADO_OPCIONES = "opciones"
ESTADO_PAUSA = "pausa"
ESTADO_JUGANDO = "jugando"
ESTADO_TRANSICION = "transicion"
ESTADO_GAME_OVER = "game_over"


@dataclass
class EstadoEventos:
    screen: pygame.Surface
    jugando: bool
    estado: str
    estado_despues_opciones: str
    jugador: Any
    nivel: int
    plataformas: list
    hue_fondo: float
    hue_jugador: float
    entidades: list
    transicion: Any
    boton_reintentar: pygame.Rect
    texto_boton: str
    tamano_fuente: int
    fuente_boton: pygame.font.Font
    superficie_texto_boton: pygame.Surface
    idioma_mostrado: Any


@dataclass
class DependenciasEventos:
    width: int
    height: int
    pos_spawn: pygame.Vector2
    menu: Any
    pausa: Any
    opciones: Any
    configuracion: dict
    generar_nivel: Any
    color_desde_hue: Any
    crear_jugador: Any
    ajustar_dificultad_jugador: Any
    aplicar_volumen_audio: Any
    guardar_configuracion: Any
    texto: Any


def _aplicar_modo_pantalla(contexto, dependencias):
    ancho, alto = dependencias.configuracion["resoluciones"][
        dependencias.configuracion["resolucion"]
    ]
    modo_ventana = (
        pygame.FULLSCREEN
        if dependencias.configuracion["pantalla_completa"]
        else 0
    )
    contexto.screen = pygame.display.set_mode((ancho, alto), modo_ventana)


def _evento_con_posicion_logica(evento, contexto, dependencias):
    return pygame.event.Event(
        evento.type,
        {
            "button": evento.button,
            "pos": (
                int(evento.pos[0] * dependencias.width / contexto.screen.get_width()),
                int(evento.pos[1] * dependencias.height / contexto.screen.get_height()),
            ),
        },
    )


def _reiniciar_juego(contexto, dependencias):
    contexto.nivel = 1
    (
        contexto.plataformas,
        contexto.hue_fondo,
        contexto.hue_jugador,
        contexto.entidades,
    ) = dependencias.generar_nivel(contexto.nivel)
    contexto.jugador = dependencias.crear_jugador(
        *dependencias.pos_spawn,
        dependencias.color_desde_hue(contexto.hue_jugador),
        dependencias.configuracion["volumen_efectos"],
        dash_habilitado=True,
    )
    contexto.jugador.rect.center = dependencias.pos_spawn
    dependencias.ajustar_dificultad_jugador(contexto.jugador, contexto.nivel)
    contexto.transicion = None
    contexto.estado = ESTADO_JUGANDO


def procesar_eventos(eventos, contexto, dependencias):
    """Actualiza el estado del juego en respuesta a los eventos de Pygame."""
    for evento in eventos:
        if evento.type == pygame.QUIT:
            contexto.jugando = False
        elif evento.type == pygame.KEYDOWN and evento.key == pygame.K_F11:
            dependencias.configuracion["pantalla_completa"] = not dependencias.configuracion[
                "pantalla_completa"
            ]
            _aplicar_modo_pantalla(contexto, dependencias)

        if contexto.estado == ESTADO_ADVERTENCIA and evento.type in (
            pygame.KEYDOWN,
            pygame.MOUSEBUTTONDOWN,
        ):
            contexto.estado = ESTADO_MENU
        elif contexto.estado == ESTADO_MENU:
            evento_menu = evento
            if evento.type == pygame.MOUSEBUTTONDOWN:
                evento_menu = _evento_con_posicion_logica(
                    evento, contexto, dependencias
                )
            accion_menu = dependencias.menu.manejar_evento(evento_menu)
            if accion_menu == "jugar":
                contexto.estado = ESTADO_JUGANDO
            elif accion_menu == "opciones":
                contexto.estado_despues_opciones = ESTADO_MENU
                contexto.estado = ESTADO_OPCIONES
            elif accion_menu == "salir":
                contexto.jugando = False
        elif contexto.estado == ESTADO_PAUSA:
            evento_pausa = evento
            if evento.type == pygame.MOUSEBUTTONDOWN:
                evento_pausa = _evento_con_posicion_logica(
                    evento, contexto, dependencias
                )
            accion_pausa = dependencias.pausa.manejar_evento(evento_pausa)
            if accion_pausa == "continuar":
                contexto.estado = ESTADO_JUGANDO
            elif accion_pausa == "opciones":
                contexto.estado_despues_opciones = ESTADO_PAUSA
                contexto.estado = ESTADO_OPCIONES
            elif accion_pausa == "salir":
                contexto.jugando = False
        elif contexto.estado == ESTADO_OPCIONES:
            evento_opciones = evento
            if evento.type == pygame.MOUSEBUTTONDOWN:
                evento_opciones = _evento_con_posicion_logica(
                    evento, contexto, dependencias
                )
            accion_opciones = dependencias.opciones.manejar_evento(
                evento_opciones
            )
            if accion_opciones == "volver":
                contexto.estado = contexto.estado_despues_opciones
            elif accion_opciones == "aplicar":
                dependencias.guardar_configuracion(dependencias.configuracion)
                dependencias.aplicar_volumen_audio(
                    dependencias.configuracion, contexto.jugador
                )
                _aplicar_modo_pantalla(contexto, dependencias)
                dependencias.menu.actualizar_tamano(
                    dependencias.width, dependencias.height
                )
                dependencias.menu.establecer_idioma(
                    dependencias.configuracion["idioma"]
                )
                dependencias.menu.establecer_escala_ui(
                    dependencias.configuracion["escala_ui"]
                )
                dependencias.pausa.actualizar_tamano(
                    dependencias.width, dependencias.height
                )
                dependencias.pausa.establecer_idioma(
                    dependencias.configuracion["idioma"]
                )
                dependencias.pausa.establecer_escala_ui(
                    dependencias.configuracion["escala_ui"]
                )
                dependencias.opciones.actualizar_tamano(
                    dependencias.width, dependencias.height
                )
                pygame.display.set_caption(
                    dependencias.texto(
                        dependencias.configuracion["idioma"], "window_title"
                    )
                )
                contexto.texto_boton = dependencias.texto(
                    dependencias.configuracion["idioma"], "retry"
                )
                contexto.tamano_fuente = 36
                contexto.fuente_boton = pygame.font.Font(
                    None, contexto.tamano_fuente
                )
                contexto.fuente_boton.set_bold(True)
                while (
                    contexto.tamano_fuente > 16
                    and contexto.fuente_boton.size(contexto.texto_boton)[0]
                    > contexto.boton_reintentar.width - 28
                ):
                    contexto.tamano_fuente -= 1
                    contexto.fuente_boton = pygame.font.Font(
                        None, contexto.tamano_fuente
                    )
                    contexto.fuente_boton.set_bold(True)
                contexto.superficie_texto_boton = contexto.fuente_boton.render(
                    contexto.texto_boton, True, (255, 245, 255)
                )
                contexto.idioma_mostrado = None
                contexto.estado = contexto.estado_despues_opciones

        if contexto.estado == ESTADO_JUGANDO and evento.type == pygame.KEYDOWN:
            if evento.key == pygame.K_ESCAPE:
                dependencias.pausa.establecer_idioma(
                    dependencias.configuracion["idioma"]
                )
                contexto.estado = ESTADO_PAUSA
            elif evento.key == dependencias.configuracion["controles"]["jump"]:
                contexto.jugador.solicitar_salto()
            elif evento.key == dependencias.configuracion["controles"]["dash"]:
                contexto.jugador.solicitar_dash()
        elif (
            contexto.estado == ESTADO_GAME_OVER
            and evento.type == pygame.KEYDOWN
            and evento.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r)
        ):
            _reiniciar_juego(contexto, dependencias)

        if (
            evento.type == pygame.MOUSEBUTTONDOWN
            and evento.button == pygame.BUTTON_LEFT
            and contexto.estado == ESTADO_GAME_OVER
            and contexto.boton_reintentar.collidepoint(
                (
                    int(
                        evento.pos[0]
                        * dependencias.width
                        / contexto.screen.get_width()
                    ),
                    int(
                        evento.pos[1]
                        * dependencias.height
                        / contexto.screen.get_height()
                    ),
                )
            )
        ):
            _reiniciar_juego(contexto, dependencias)


PESOS_LUMINOSIDAD = np.array([0.299, 0.587, 0.114], dtype=np.float32)


def opacidad_nivel(nivel):
    """Devuelve la intensidad de oscurecimiento acumulada por nivel."""
    return min(40, nivel * 3)


def saturacion_nivel(nivel):
    """Devuelve la pérdida de color acumulada por nivel."""
    return min(1.0, nivel / 12)


def escala_grises(superficie, factor):
    """Mezcla una superficie de Pygame con su versión en escala de grises."""
    if factor <= 0:
        return superficie
    factor = min(1.0, factor)

    ancho, alto = superficie.get_size()
    reduccion = 3
    tam_chico = (max(1, ancho // reduccion), max(1, alto // reduccion))
    chica = pygame.transform.scale(superficie, tam_chico)

    colores = pygame.surfarray.array3d(chica).astype(np.float32)
    gris = (colores @ PESOS_LUMINOSIDAD)[:, :, None]

    mezcla = colores * (1 - factor) + gris * factor
    resultado_chico = pygame.surfarray.make_surface(mezcla.astype(np.uint8))
    pygame.transform.scale(resultado_chico, (ancho, alto), superficie)
    return superficie


def cargar_gif(ruta, tamano):
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
        fotograma = cv2.resize(fotograma, tamano, interpolation=cv2.INTER_NEAREST)
        superficie = pygame.image.frombuffer(fotograma.tobytes(), tamano, "RGB")
        fotogramas.append(
            superficie.convert()
            if pygame.display.get_surface()
            else superficie.copy()
        )
    captura.release()
    return fotogramas, 1.0 / fps


class EventosVisuales:
    """Administra flashbacks, animaciones de game over y efectos por nivel."""

    def __init__(self, ancho, alto, carpeta_assets="assets"):
        self.ancho = ancho
        self.alto = alto

        self.gifs_game_over = self._cargar_secuencia(
            carpeta_assets,
            (
                "image1.gif",
                "image2.gif",
                "image3.gif",
                "image4.gif",
                "image12.gif",
                "image13.gif",
            ),
        )
        self.gif_game_over_nivel_alto = self._cargar_secuencia(
            carpeta_assets, ("image14.gif",)
        )
        self.secuencia_game_over = self._cargar_secuencia(
            carpeta_assets, ("image7.gif", "image8.gif", "image9.gif")
        )
        self.duracion_imagen_game_over = 3.0
        self.gif_game_over = []
        self.duracion_fotograma_gif = 0.1
        self.indice_imagen_game_over = 0
        self.animacion_despertar = CarboncilloAnimado()
        self.game_over_nivel_alto_activo = False

        self.flashbacks_por_nivel = {
            1: self._cargar_gif(carpeta_assets, "image15.gif"),
            6: self._cargar_gif(carpeta_assets, "image6.gif"),
            10: self._cargar_gif(carpeta_assets, "image5.gif"),
            20: self._cargar_gif(carpeta_assets, "image16.gif"),
        }
        self.flashback_activo = False
        self.flashback_inicio = 0.0
        self.flashback_duracion_total = 0.0
        self.fotogramas_flashback = []
        self.duracion_flashback = 0.1
        self.proximo_flashback = 0.0
        self.flashbacks_habilitados = False

        self.flashback_nivel_10_activo = False
        self.inicio_flashback_nivel_10 = 0.0
        self.duracion_flashback_nivel_10 = 3.0
        self.flashback_nivel_20_activo = False
        self.inicio_flashback_nivel_20 = 0.0
        self.duracion_flashback_nivel_20 = 2.5

    def _cargar_gif(self, carpeta_assets, nombre):
        return cargar_gif(
            os.path.join(carpeta_assets, nombre), (self.ancho, self.alto)
        )

    def _cargar_secuencia(self, carpeta_assets, nombres):
        secuencia = []
        for nombre in nombres:
            fotogramas, duracion = self._cargar_gif(carpeta_assets, nombre)
            if fotogramas:
                secuencia.append((fotogramas, duracion))
        return secuencia

    def actualizar_flashback(self, nivel, estado, tiempo, estado_jugando):
        """Actualiza la programación de flashbacks de fondo aleatorios."""
        if 1 <= nivel <= 5:
            fotogramas_disponibles, duracion_disponible = self.flashbacks_por_nivel[1]
        elif nivel >= 20:
            fotogramas_disponibles, duracion_disponible = self.flashbacks_por_nivel[20]
        elif nivel >= 10:
            fotogramas_disponibles, duracion_disponible = self.flashbacks_por_nivel[10]
        elif nivel >= 6:
            fotogramas_disponibles, duracion_disponible = self.flashbacks_por_nivel[6]
        else:
            fotogramas_disponibles, duracion_disponible = [], 0.1

        if estado != estado_jugando or not fotogramas_disponibles:
            self.flashback_activo = False
            self.flashbacks_habilitados = False
        elif not self.flashbacks_habilitados:
            self.flashbacks_habilitados = True
            self.fotogramas_flashback = fotogramas_disponibles
            self.duracion_flashback = duracion_disponible
            self.proximo_flashback = tiempo + random.uniform(3.0, 8.0)
        elif (
            not self.flashback_activo
            and estado == estado_jugando
            and tiempo >= self.proximo_flashback
        ):
            self.flashback_activo = True
            self.flashback_inicio = tiempo
            self.flashback_duracion_total = random.uniform(1.0, 2.0)
        elif (
            self.flashback_activo
            and tiempo - self.flashback_inicio >= self.flashback_duracion_total
        ):
            self.flashback_activo = False
            self.proximo_flashback = tiempo + random.uniform(6.0, 14.0)

    @property
    def evento_flashback_especial_activo(self):
        return self.flashback_nivel_10_activo or self.flashback_nivel_20_activo

    def entrar_nivel(self, nivel, tiempo):
        if nivel == 10:
            self.flashback_nivel_10_activo = True
            self.inicio_flashback_nivel_10 = tiempo
        elif nivel == 20:
            self.flashback_nivel_20_activo = True
            self.inicio_flashback_nivel_20 = tiempo

    def actualizar_flashbacks_especiales(self, tiempo):
        if (
            self.flashback_nivel_10_activo
            and tiempo - self.inicio_flashback_nivel_10
            >= self.duracion_flashback_nivel_10
        ):
            self.flashback_nivel_10_activo = False
        if (
            self.flashback_nivel_20_activo
            and tiempo - self.inicio_flashback_nivel_20
            >= self.duracion_flashback_nivel_20
        ):
            self.flashback_nivel_20_activo = False

    def obtener_fotograma_flashback(self, tiempo):
        if not self.flashback_activo:
            return None
        indice = int((tiempo - self.flashback_inicio) / self.duracion_flashback)
        indice %= len(self.fotogramas_flashback)
        return self.fotogramas_flashback[indice]

    def iniciar_game_over(self, nivel, inicio, seleccionar_por_nivel=True):
        self.indice_imagen_game_over = 0
        self.inicio_game_over = inicio
        self.game_over_nivel_alto_activo = nivel >= 20
        if self.game_over_nivel_alto_activo:
            self.gif_game_over = []
        elif seleccionar_por_nivel and nivel >= 20 and self.gif_game_over_nivel_alto:
            self.gif_game_over, self.duracion_fotograma_gif = (
                self.gif_game_over_nivel_alto[0]
            )
        elif seleccionar_por_nivel and nivel >= 10 and self.secuencia_game_over:
            self.gif_game_over, self.duracion_fotograma_gif = (
                self.secuencia_game_over[0]
            )
        elif self.gifs_game_over:
            self.gif_game_over, self.duracion_fotograma_gif = random.choice(
                self.gifs_game_over
            )

    def dibujar_game_over(self, lienzo, nivel, tiempo_ms, tiempo):
        if self.game_over_nivel_alto_activo:
            self.animacion_despertar.dibujar(
                lienzo, max(0.0, (tiempo_ms - self.inicio_game_over) / 1000)
            )
            return

        if nivel >= 20 and self.gif_game_over_nivel_alto:
            self.gif_game_over, self.duracion_fotograma_gif = (
                self.gif_game_over_nivel_alto[0]
            )
        elif nivel >= 10 and self.secuencia_game_over:
            indice = min(
                int(
                    (tiempo_ms - self.inicio_game_over)
                    / 1000
                    / self.duracion_imagen_game_over
                ),
                len(self.secuencia_game_over) - 1,
            )
            self.gif_game_over, self.duracion_fotograma_gif = (
                self.secuencia_game_over[indice]
            )

        if self.gif_game_over:
            indice = int(
                (tiempo_ms - self.inicio_game_over)
                / (self.duracion_fotograma_gif * 1000)
            ) % len(self.gif_game_over)
            fotograma = self.gif_game_over[indice]
            offset = (
                int(2 * np.sin(tiempo * 28.0)),
                int(2 * np.cos(tiempo * 31.0)),
            )
            lienzo.blit(fotograma, offset)

    def dibujar_flashback_especial(
        self, lienzo, tiempo, idioma, fuente, fuente_titulo, texto
    ):
        if self.flashback_nivel_10_activo:
            lienzo.fill((0, 0, 0))
            frase = fuente.render(
                texto(idioma, "level_10_flashback"), True, (255, 255, 255)
            )
            desplazamiento = int(3 * np.sin(tiempo * 40.0))
            rect = frase.get_rect(center=(self.ancho // 2, self.alto // 2))
            rect.x += desplazamiento
            lienzo.blit(frase, rect)
        elif self.flashback_nivel_20_activo:
            lienzo.fill((0, 0, 0))
            veladura = pygame.Surface((self.ancho, self.alto), pygame.SRCALPHA)
            veladura.fill((0, 0, 0, 185))
            lienzo.blit(veladura, (0, 0))

            edad = max(0.0, tiempo - self.inicio_flashback_nivel_20)
            intensidad = max(
                0.0, 1.0 - edad / self.duracion_flashback_nivel_20
            )
            alpha = int(
                210 * intensidad * (0.5 + 0.5 * np.sin(tiempo * 34.0))
            )
            if alpha > 0:
                flash = pygame.Surface(
                    (self.ancho, self.alto), pygame.SRCALPHA
                )
                flash.fill((255, 255, 255, alpha))
                lienzo.blit(flash, (0, 0))

            for _ in range(22):
                x = random.randint(0, self.ancho - 1)
                y = random.randint(0, self.alto - 1)
                ancho = random.randint(2, 7)
                alto = random.randint(2, 7)
                pygame.draw.rect(
                    lienzo,
                    (245, 245, 245, 80),
                    pygame.Rect(x, y, ancho, alto),
                )

            frase = texto(idioma, "level_20_flashback").upper()
            titulo = fuente_titulo.render(frase, True, (255, 245, 245))
            sombra = fuente_titulo.render(frase, True, (18, 18, 18))
            rect = titulo.get_rect(center=(self.ancho // 2, self.alto // 2))
            desplazamiento_x = int(12 * np.sin(tiempo * 45.0))
            desplazamiento_y = int(9 * np.cos(tiempo * 38.0))
            rect_sombra = rect.copy().move(
                6 + desplazamiento_x, 7 + desplazamiento_y
            )
            rect_temblor = rect.move(desplazamiento_x, desplazamiento_y)
            lienzo.blit(sombra, rect_sombra)
            lienzo.blit(titulo, rect_temblor)
