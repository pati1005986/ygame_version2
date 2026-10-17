"""Punto de entrada del juego de plataformas procedural.

Este módulo contiene la clase ``Juego``, que coordina el bucle principal
(eventos -> física -> hitos de historia -> render). El resto vive aparte:

* ``constantes``  tamaño de pantalla, FPS, spawn y niveles clave.
* ``ajustes``     carga/validación de configuración y volumen.
* ``niveles``     generación de niveles y creación del jugador.
* ``combo``       seguimiento del combo de trucos.
* ``render``      ventana/escalado del lienzo y viñeta de peligro.
* ``hud``         fuentes, aviso inicial y textos del HUD.
* ``eventos``, ``personaje``, ``transicion``... lógica especializada.
"""

import math
import random
import sys

import pygame

from ajustes import IDIOMAS_DISPONIBLES, aplicar_volumen_audio, preparar_configuracion
from catarsis import play_catarsis_animation
from combo import Combo
from constantes import FPS, HEIGHT, NIVEL_DESPERTAR, NIVEL_FINAL, POS_SPAWN, WIDTH
from eventos import (
    ESTADO_ADVERTENCIA,
    ESTADO_CREDITOS,
    ESTADO_GAME_OVER,
    ESTADO_JUGANDO,
    ESTADO_MENU,
    ESTADO_OPCIONES,
    ESTADO_PAUSA,
    ESTADO_TRANSICION,
    DependenciasEventos,
    EstadoEventos,
    EventosVisuales,
    escala_grises,
    opacidad_nivel,
    procesar_eventos,
    saturacion_nivel,
)
from fondo import ParticulaAbstracta, dibujar_fondo_segmentado
from hud import HUD, Fuentes, PantallaAdvertencia, crear_fuente_boton
from idioma import texto
from menu import MenuInicio
from niveles import (
    ajustar_dificultad_jugador,
    crear_jugador,
    dibujar_nivel,
    generar_nivel,
)
from opciones import MenuOpciones, guardar_configuracion
from pausa import MenuPausa
from personaje import PersonajeHumanoide
from plataformas import color_desde_hue
from render import Presentador, crear_vineta_peligro
from transicion import TransicionCaricaturesca

# Atributos de ``Juego`` que ``procesar_eventos`` puede leer y modificar a
# través de ``EstadoEventos`` (se copian ida y vuelta en cada fotograma).
CAMPOS_EVENTOS = (
    "jugando", "estado", "estado_despues_opciones", "jugador", "nivel",
    "modo_infinito", "puntaje", "plataformas", "hue_fondo", "hue_jugador",
    "entidades", "transicion", "texto_boton", "tamano_fuente", "fuente_boton",
    "superficie_texto_boton",
)

FRECUENCIA_FONDO = 1 / 20  # el fondo abstracto se redibuja a 20 Hz


class Juego:
    def __init__(self, nivel_inicial=None, idioma_inicial="en"):
        if idioma_inicial not in IDIOMAS_DISPONIBLES:
            idioma_inicial = "en"

        pygame.init()
        if not pygame.mixer.get_init():
            pygame.mixer.init()

        self.configuracion = preparar_configuracion(idioma_inicial)
        self._crear_ventana()
        self.reloj = pygame.time.Clock()

        self.fuentes = Fuentes()
        self.hud = HUD(self.fuentes, WIDTH, HEIGHT)
        self.advertencia = PantallaAdvertencia(self.fuentes, WIDTH)
        self._crear_boton_reintentar(idioma_inicial)
        self.boton_creditos_menu = pygame.Rect(20, 62, 245, 38)
        self._crear_capas()

        self.eventos_visuales = EventosVisuales(WIDTH, HEIGHT)
        self.combo = Combo()

        # Estado de la partida
        self.estado = ESTADO_ADVERTENCIA
        self.jugando = True
        self.modo_infinito = False
        self.puntaje = 0
        self.transicion = None
        self.despertar_mostrado = False
        self.estado_despues_opciones = ESTADO_MENU
        self.resumen_combo = 0
        self.resumen_expira = 0

        # Efectos de cámara
        self.intensidad_shake = 0.0  # sacudida: da sensación de impacto/velocidad
        self.alerta_enemigos = 0.0   # 0-1: cercanía del enemigo más próximo

        if nivel_inicial is None:
            self.nivel = self.configuracion["nivel_guardado"]
        else:
            self.nivel = max(1, int(nivel_inicial))
        self._preparar_partida(self.nivel)
        self.particulas = [ParticulaAbstracta(WIDTH, HEIGHT) for _ in range(12)]
        aplicar_volumen_audio(self.configuracion, self.jugador)

        self._crear_menus()
        self.dependencias_eventos = DependenciasEventos(
            width=WIDTH,
            height=HEIGHT,
            pos_spawn=POS_SPAWN,
            menu=self.menu,
            pausa=self.pausa,
            opciones=self.opciones,
            configuracion=self.configuracion,
            generar_nivel=generar_nivel,
            color_desde_hue=color_desde_hue,
            crear_jugador=PersonajeHumanoide,
            ajustar_dificultad_jugador=ajustar_dificultad_jugador,
            aplicar_volumen_audio=aplicar_volumen_audio,
            guardar_configuracion=guardar_configuracion,
            texto=texto,
        )

        # Física con paso fijo, desacoplada del render.
        self.paso_fisica = 1 / FPS
        self.acumulador_fisica = self.paso_fisica

    # ------------------------------------------------------------------
    # Inicialización
    # ------------------------------------------------------------------
    def _crear_ventana(self):
        resolucion = MenuOpciones.RESOLUCIONES[self.configuracion["resolucion"]]
        flags = pygame.FULLSCREEN if self.configuracion["pantalla_completa"] else 0
        self.pantalla = Presentador(WIDTH, HEIGHT, resolucion, flags)
        self.lienzo = self.pantalla.lienzo
        pygame.display.set_caption(texto(self.configuracion["idioma"], "window_title"))

    def _crear_boton_reintentar(self, idioma):
        self.boton_reintentar = pygame.Rect(WIDTH // 2 - 110, HEIGHT // 2 + 45, 220, 52)
        self.texto_boton = texto(idioma, "retry")
        self.tamano_fuente, self.fuente_boton = crear_fuente_boton(
            self.texto_boton, self.boton_reintentar.width - 28
        )
        self.superficie_texto_boton = self.fuente_boton.render(
            self.texto_boton, True, (255, 245, 255)
        )

    def _crear_capas(self):
        """Superficies reutilizadas en cada fotograma (se crean una sola vez)."""
        tamano = (WIDTH, HEIGHT)
        self.escena = pygame.Surface(tamano)
        self.capa_nivel_anterior = pygame.Surface(tamano)  # foto fija del nivel que se deja atrás
        self.capa_nivel_nuevo = pygame.Surface(tamano)
        self.fondo_cache = pygame.Surface(tamano)
        self.capa_opacidad = pygame.Surface(tamano, pygame.SRCALPHA)
        self.vineta_peligro = crear_vineta_peligro(WIDTH, HEIGHT)
        self.opacidad_mostrada = None
        self.nivel_fondo = None
        self.tiempo_ultimo_fondo = -1.0

    def _crear_menus(self):
        cfg = self.configuracion
        self.menu = MenuInicio(
            WIDTH,
            HEIGHT,
            nombre_video="image29.gif" if cfg.get("juego_completado") else "image.gif",
            idioma=cfg["idioma"],
            escala_ui=cfg["escala_ui"],
        )
        self.menu.establecer_nivel_guardado(self.nivel)
        self.menu.establecer_modo_infinito_desbloqueado(cfg.get("juego_completado", False))
        self.menu.establecer_mejor_puntaje_infinito(cfg["mejor_puntaje_infinito"])
        self.pausa = MenuPausa(
            WIDTH, HEIGHT, idioma=cfg["idioma"], escala_ui=cfg["escala_ui"]
        )
        self.opciones = MenuOpciones(WIDTH, HEIGHT, cfg)

    def _preparar_partida(self, nivel):
        """Genera el nivel dado y un jugador nuevo ajustado a su dificultad."""
        self.plataformas, self.hue_fondo, self.hue_jugador, self.entidades = (
            generar_nivel(nivel)
        )
        self.jugador = crear_jugador(
            self.hue_jugador, self.configuracion["volumen_efectos"]
        )
        ajustar_dificultad_jugador(self.jugador, nivel)

    def guardar_nivel_guardado(self, nivel_a_guardar):
        self.configuracion["nivel_guardado"] = max(1, int(nivel_a_guardar))
        guardar_configuracion(self.configuracion)
        self.menu.establecer_nivel_guardado(self.configuracion["nivel_guardado"])

    @property
    def hay_gif_game_over(self):
        ev = self.eventos_visuales
        return self.estado == ESTADO_GAME_OVER and (
            bool(ev.gif_game_over) or ev.game_over_nivel_alto_activo
        )

    # ------------------------------------------------------------------
    # Bucle principal
    # ------------------------------------------------------------------
    def ejecutar(self):
        while self.jugando:
            # Limita el avance tras una pausa del sistema; el acumulador hace
            # varios pasos pequeños si el render no alcanza los 60 FPS.
            dt = min(self.reloj.tick(FPS) / 1000.0, 0.25)
            self.acumulador_fisica += dt
            tiempo = pygame.time.get_ticks() / 1000.0

            self.eventos_visuales.actualizar_flashback(
                self.nivel, self.estado, tiempo, ESTADO_JUGANDO
            )
            self._procesar_eventos()

            if self.estado == ESTADO_MENU:
                self.menu.actualizar()

            while self.acumulador_fisica >= self.paso_fisica:
                self._actualizar_mundo(self.paso_fisica)
                self.acumulador_fisica -= self.paso_fisica

            self._comprobar_hitos_de_historia()
            self.eventos_visuales.actualizar_flashbacks_especiales(tiempo)

            self._dibujar(dt, tiempo)
            pygame.display.flip()

        self._cerrar()

    def _cerrar(self):
        if not self.modo_infinito:
            volver_al_inicio = self.estado in (ESTADO_GAME_OVER, ESTADO_CREDITOS)
            self.guardar_nivel_guardado(1 if volver_al_inicio else self.nivel)
        self.eventos_visuales.detener_audio_game_over()
        pygame.quit()

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------
    def _procesar_eventos(self):
        estado_antes = self.estado
        contexto = EstadoEventos(
            screen=self.pantalla.screen,
            boton_reintentar=self.boton_reintentar,
            idioma_mostrado=self.hud.idioma_mostrado,
            boton_creditos_menu=self.boton_creditos_menu,
            creditos_listos=self.eventos_visuales.creditos_listos(
                pygame.time.get_ticks()
            ),
            **{campo: getattr(self, campo) for campo in CAMPOS_EVENTOS},
        )
        procesar_eventos(pygame.event.get(), contexto, self.dependencias_eventos)

        self.pantalla.screen = contexto.screen
        self.hud.idioma_mostrado = contexto.idioma_mostrado
        for campo in CAMPOS_EVENTOS:
            setattr(self, campo, getattr(contexto, campo))

        if estado_antes == ESTADO_GAME_OVER and self.estado != ESTADO_GAME_OVER:
            self.eventos_visuales.detener_audio_game_over()
        if estado_antes == ESTADO_CREDITOS and self.estado == ESTADO_MENU:
            self._reiniciar_tras_creditos()

    def _reiniciar_tras_creditos(self):
        self.eventos_visuales.final_juego_activo = False
        # Tras completar el juego, el menú muestra la imagen de victoria.
        self.menu.establecer_video("image29.gif")
        self.modo_infinito = False
        self.puntaje = 0
        self.nivel = 1
        self.guardar_nivel_guardado(1)
        self._preparar_partida(self.nivel)

    # ------------------------------------------------------------------
    # Actualización del mundo (un paso de física)
    # ------------------------------------------------------------------
    def _actualizar_mundo(self, dt):
        self._decaer_efectos()

        if self.estado == ESTADO_JUGANDO:
            self._actualizar_jugando()
        elif self.estado == ESTADO_GAME_OVER:
            self._actualizar_game_over(dt)
        elif self.estado == ESTADO_TRANSICION:
            self._actualizar_transicion()

        if self.estado == ESTADO_JUGANDO:
            for plataforma in self.plataformas:
                plataforma.actualizar(dt)

        if (
            self.estado in (ESTADO_JUGANDO, ESTADO_TRANSICION, ESTADO_GAME_OVER)
            and not self.hay_gif_game_over
        ):
            for particula in self.particulas:
                particula.actualizar(dt)

        self.combo.actualizar(pygame.time.get_ticks())
        self._sincronizar_nivel_guardado()

    def _decaer_efectos(self):
        self.intensidad_shake *= 0.82
        if self.intensidad_shake < 0.05:
            self.intensidad_shake = 0.0
        self.alerta_enemigos *= 0.9
        if self.alerta_enemigos < 0.02:
            self.alerta_enemigos = 0.0

    def _actualizar_jugando(self):
        jugador = self.jugador
        en_aire_antes = not jugador.en_suelo
        dash_activo = jugador.dash_restante > 0

        jugador.mover(self.plataformas, self.configuracion["controles"])
        ahora = pygame.time.get_ticks()
        if jugador._salto_ejecutado_este_frame and en_aire_antes:
            self.combo.registrar(ahora)
        if jugador.dash_ejecutado_este_frame:
            self.combo.registrar(ahora)
            jugador.dash_ejecutado_este_frame = False

        if not self.eventos_visuales.evento_flashback_especial_activo:
            self._mover_enemigos()

        if jugador.en_suelo and en_aire_antes:
            self.intensidad_shake = max(self.intensidad_shake, 3.5)

        self._comprobar_trampa()

        if self.estado == ESTADO_JUGANDO and self.modo_infinito:
            for entidad in self.entidades:
                if entidad.activa and entidad.rect.colliderect(jugador.rect):
                    direccion = (
                        1 if entidad.rect.centerx >= jugador.rect.centerx else -1
                    )
                    if entidad.derrotar(direccion):
                        self.combo.registrar(ahora)
                        self.intensidad_shake = max(self.intensidad_shake, 5.0)
        elif (
            self.estado == ESTADO_JUGANDO
            and not dash_activo
            and any(e.rect.colliderect(jugador.rect) for e in self.entidades)
        ):
            self._iniciar_game_over()
            self.combo.reiniciar()

        salio_por_la_derecha = jugador.rect.centerx >= WIDTH
        salio_por_otro_borde = jugador.rect.top > HEIGHT or jugador.rect.right < 0
        if salio_por_la_derecha:
            self._pasar_al_siguiente_nivel()
        elif salio_por_otro_borde:
            self._iniciar_game_over(seleccionar_por_nivel=False)
            self.combo.reiniciar()

    def _mover_enemigos(self):
        for entidad in self.entidades:
            entidad.mover(self.plataformas, self.jugador.rect)
        self.entidades = [entidad for entidad in self.entidades if entidad.activa]
        self.alerta_enemigos = max(
            self.alerta_enemigos,
            max((e.nivel_alerta() for e in self.entidades), default=0.0),
        )
        if self.alerta_enemigos > 0:
            self.intensidad_shake = max(
                self.intensidad_shake, self.alerta_enemigos * 2.2
            )

    def _comprobar_trampa(self):
        jugador = self.jugador
        plataforma = jugador.plataforma_actual
        if not (jugador.en_suelo and plataforma is not None and plataforma.es_trampa):
            return
        plataforma.activar_trampa()
        if plataforma.lista_para_caer:
            jugador.iniciar_engullido(plataforma)
            self._iniciar_game_over()
        else:
            self.intensidad_shake = max(self.intensidad_shake, 2.0)

    def _iniciar_game_over(self, **opciones):
        """Dispara el game over; ``opciones`` se pasan a ``iniciar_game_over``."""
        self.intensidad_shake = 9.0
        self.eventos_visuales.iniciar_game_over(
            self.nivel,
            pygame.time.get_ticks(),
            volumen_efectos=self.configuracion["volumen_efectos"],
            modo_infinito=self.modo_infinito,
            **opciones,
        )
        self.estado = ESTADO_GAME_OVER

    def _pasar_al_siguiente_nivel(self):
        cfg = self.configuracion
        tiempo_mundo = pygame.time.get_ticks() / 1000.0

        self.resumen_combo = self.combo.mejor_nivel
        self.resumen_expira = pygame.time.get_ticks() + 1800
        if self.modo_infinito:
            self.puntaje += self.nivel * 100 + self.combo.mejor_nivel * 25
            if self.puntaje > cfg["mejor_puntaje_infinito"]:
                cfg["mejor_puntaje_infinito"] = self.puntaje
                guardar_configuracion(cfg)
                self.menu.establecer_mejor_puntaje_infinito(self.puntaje)
        self.combo.reiniciar_mejor_nivel()

        # Foto del nivel que se deja atrás para la transición de cámara.
        dibujar_nivel(
            self.capa_nivel_anterior, self.fondo_cache, self.plataformas,
            self.entidades, tiempo_mundo, self.nivel,
        )
        self.nivel += 1
        if not self.modo_infinito:
            self.eventos_visuales.entrar_nivel(self.nivel, tiempo_mundo)

        color_origen = self.jugador.color
        pos_origen = pygame.Vector2(self.jugador.rect.center)
        self.plataformas, self.hue_fondo, self.hue_jugador, self.entidades = (
            generar_nivel(self.nivel, self.modo_infinito)
        )
        self.transicion = TransicionCaricaturesca(
            color_origen,
            color_desde_hue(self.hue_jugador),
            pos_origen,
            POS_SPAWN,
            nivel=self.nivel,
            volumen_efectos=cfg["volumen_efectos"],
            suelo_spawn=self.plataformas[0].rect.top,
            ancho_pantalla=WIDTH,
        )
        self.jugador.vel_y = 0
        ajustar_dificultad_jugador(self.jugador, self.nivel, self.modo_infinito)
        self.estado = ESTADO_TRANSICION

    def _actualizar_game_over(self, dt):
        self.combo.reiniciar()
        self.resumen_expira = 0
        for plataforma in self.plataformas:
            plataforma.actualizar(dt)
        if self.jugador.muriendo:
            self.jugador.actualizar_engullido()
        elif any(p.trampa_activada for p in self.plataformas):
            self.jugador.rect.y += 3

    def _actualizar_transicion(self):
        terminada = self.transicion.actualizar(self.jugador)
        for fuerza in self.transicion.recoger_impactos():
            self.intensidad_shake = max(self.intensidad_shake, fuerza)
        if not terminada:
            return
        jugador = self.jugador
        plataforma_spawn = self.plataformas[0]
        jugador.rect.bottom = plataforma_spawn.rect_colision().top
        jugador.en_suelo = True
        jugador.plataforma_actual = plataforma_spawn
        jugador.vel_y = 0
        jugador._resto_y = 0.0
        aplicar_volumen_audio(self.configuracion, jugador)
        self.estado = ESTADO_JUGANDO

    def _sincronizar_nivel_guardado(self):
        if self.modo_infinito:
            return
        if self.estado == ESTADO_GAME_OVER:
            if self.configuracion["nivel_guardado"] != 1:
                self.guardar_nivel_guardado(1)
        elif self.estado in (ESTADO_JUGANDO, ESTADO_TRANSICION):
            if self.configuracion["nivel_guardado"] != self.nivel:
                self.guardar_nivel_guardado(self.nivel)

    # ------------------------------------------------------------------
    # Hitos de historia
    # ------------------------------------------------------------------
    def _comprobar_hitos_de_historia(self):
        en_historia = self.estado == ESTADO_JUGANDO and not self.modo_infinito

        if en_historia and self.nivel == NIVEL_DESPERTAR and not self.despertar_mostrado:
            self.despertar_mostrado = True
            play_catarsis_animation(
                self.pantalla.screen,
                self.reloj,
                exit_text=texto(self.configuracion["idioma"], "exit"),
                button_renderer=self.menu,
            )

        if (
            en_historia
            and self.nivel >= NIVEL_FINAL
            and not self.eventos_visuales.final_juego_activo
        ):
            self.eventos_visuales.iniciar_final_juego(pygame.time.get_ticks())
            self.estado = ESTADO_CREDITOS
            self.nivel = NIVEL_FINAL
            # El juego queda completado: el menú pasará a mostrar la imagen
            # de victoria y se desbloquea el modo infinito.
            if not self.configuracion.get("juego_completado"):
                self.configuracion["juego_completado"] = True
                guardar_configuracion(self.configuracion)
            self.menu.establecer_modo_infinito_desbloqueado(True)

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------
    def _dibujar(self, dt, tiempo):
        idioma = self.configuracion["idioma"]
        estado = self.estado

        if estado == ESTADO_ADVERTENCIA:
            self.advertencia.dibujar(self.lienzo, idioma)
        elif estado == ESTADO_MENU:
            self.menu.dibujar(self.lienzo, self.pantalla.posicion_raton_logica())
        elif estado == ESTADO_CREDITOS:
            self._dibujar_creditos()
        elif estado == ESTADO_PAUSA:
            self.pausa.dibujar(self.lienzo, self.pantalla.posicion_raton_logica(), dt)
        elif estado == ESTADO_OPCIONES:
            self.opciones.dibujar(self.lienzo, dt=dt)
        else:
            self._dibujar_partida(tiempo)

        self.pantalla.presentar()

    def _dibujar_creditos(self):
        idioma = self.configuracion["idioma"]
        ahora = pygame.time.get_ticks()
        creditos_listos = self.eventos_visuales.creditos_listos(ahora)
        self.eventos_visuales.dibujar_final_juego(self.lienzo, ahora, self.jugador, idioma)
        if not creditos_listos:
            return
        hover = self.boton_creditos_menu.collidepoint(
            self.pantalla.posicion_raton_logica()
        )
        rect = self.menu._dibujar_boton_comic(self.lienzo, self.boton_creditos_menu, hover)
        self.menu._texto_centrado(
            self.lienzo,
            texto(idioma, "return_main_menu"),
            self.fuentes.boton_creditos,
            rect.center,
            (255, 255, 255),
        )

    def _dibujar_partida(self, tiempo):
        """Escena de juego (jugando, transición o game over) con su HUD."""
        if not self.hay_gif_game_over:
            self._dibujar_escena(tiempo)
        self._dibujar_opacidad()
        self._dibujar_hud(tiempo)
        if self.estado == ESTADO_GAME_OVER:
            self._dibujar_game_over(tiempo)
        self.eventos_visuales.dibujar_flashback_especial(
            self.lienzo,
            tiempo,
            self.configuracion["idioma"],
            self.fuentes.base,
            self.fuentes.titulo_advertencia,
            texto,
        )

    def _dibujar_escena(self, tiempo):
        """La escena se dibuja aparte para poder desaturarla como un todo
        antes de mezclarla con el resto de la interfaz."""
        fotograma_flashback = self.eventos_visuales.obtener_fotograma_flashback(tiempo)
        self._actualizar_fondo(tiempo)

        if self.estado == ESTADO_TRANSICION:
            self._componer_transicion(tiempo)
        else:
            self._componer_nivel(tiempo, fotograma_flashback)

        # El color se atenúa al avanzar; desde el nivel 30 vuelve en tonos
        # apagados. Durante la transición el cambio sigue a la cámara.
        nivel_visual = self.nivel
        if self.estado == ESTADO_TRANSICION:
            nivel_visual = self.nivel - 1 + self.transicion.progreso_camara()
        escala_grises(self.escena, saturacion_nivel(nivel_visual))

        self._volcar_escena_con_shake()
        self._dibujar_vineta_peligro(tiempo)

    def _actualizar_fondo(self, tiempo):
        # El fondo abstracto es lo más pesado de dibujar y sus formas se
        # mueven lento: a 20 Hz sigue viéndose fluido.
        if (
            tiempo - self.tiempo_ultimo_fondo >= FRECUENCIA_FONDO
            or self.nivel != self.nivel_fondo
        ):
            dibujar_fondo_segmentado(
                self.fondo_cache, tiempo, self.hue_fondo, WIDTH, HEIGHT, self.nivel
            )
            self.nivel_fondo = self.nivel
            self.tiempo_ultimo_fondo = tiempo

    def _componer_transicion(self, tiempo):
        # Los dos niveles se dibujan uno junto al otro y la cámara se desliza
        # del viejo al nuevo siguiendo al personaje.
        camara = int(round(self.transicion.desplazamiento_camara()))
        dibujar_nivel(
            self.capa_nivel_nuevo, self.fondo_cache, self.plataformas,
            self.entidades, tiempo, self.nivel,
        )
        self.escena.blit(self.capa_nivel_anterior, (-camara, 0))
        self.escena.blit(self.capa_nivel_nuevo, (WIDTH - camara, 0))
        for particula in self.particulas:
            particula.dibujar(self.escena, tiempo)
        # Foco y cara primero; el personaje va por encima para que no lo
        # tape la oscuridad.
        self.transicion.dibujar(self.escena)
        self.jugador.dibujar(self.escena)

    def _componer_nivel(self, tiempo, fotograma_flashback):
        escena = self.escena
        if fotograma_flashback is not None:
            escena.blit(fotograma_flashback, (0, 0))
        else:
            escena.blit(self.fondo_cache, (0, 0))
        for particula in self.particulas:
            particula.dibujar(escena, tiempo)
        for plataforma in self.plataformas:
            plataforma.dibujar(escena, tiempo, self.nivel)
        for entidad in self.entidades:
            entidad.dibujar(escena, tiempo)
        self.jugador.dibujar(escena)

    def _volcar_escena_con_shake(self):
        if self.intensidad_shake > 0:
            self.lienzo.fill((0, 0, 0))
            offset = (
                random.uniform(-self.intensidad_shake, self.intensidad_shake),
                random.uniform(-self.intensidad_shake, self.intensidad_shake),
            )
            self.lienzo.blit(self.escena, offset)
        else:
            self.lienzo.blit(self.escena, (0, 0))

    def _dibujar_vineta_peligro(self, tiempo):
        if self.alerta_enemigos <= 0.02:
            return
        # Pulso suave: un latido que se acelera con el peligro (el halo del
        # enemigo, en enemigo.py, ya pulsa más rápido cerca; esto lo refuerza
        # en toda la pantalla).
        pulso = 0.85 + 0.15 * math.sin(tiempo * (4.0 + 4.0 * self.alerta_enemigos))
        self.vineta_peligro.set_alpha(
            int(255 * min(1.0, self.alerta_enemigos) * pulso)
        )
        self.lienzo.blit(self.vineta_peligro, (0, 0))

    def _dibujar_opacidad(self):
        """La escena se vuelve progresivamente más opaca al avanzar."""
        alpha = opacidad_nivel(self.nivel)
        if alpha <= 0:
            return
        if alpha != self.opacidad_mostrada:
            self.capa_opacidad.fill((0, 0, 0, alpha))
            self.opacidad_mostrada = alpha
        self.lienzo.blit(self.capa_opacidad, (0, 0))

    def _dibujar_hud(self, tiempo):
        cfg = self.configuracion
        idioma = cfg["idioma"]
        hud, lienzo = self.hud, self.lienzo

        en_primera_mitad = (
            self.estado == ESTADO_TRANSICION
            and self.transicion.progreso_camara() < 0.5
        )
        hud.dibujar_nivel(lienzo, idioma, self.nivel - 1 if en_primera_mitad else self.nivel)
        if self.modo_infinito and self.estado != ESTADO_GAME_OVER:
            hud.dibujar_puntaje(lienzo, idioma, self.puntaje)

        jugador = self.jugador
        dash_listo = jugador.dashes_disponibles > 0 and jugador.dash_enfriamiento <= 0
        combo_visible = self.combo.visible(tiempo)
        hud.dibujar_combo_y_dash(
            lienzo,
            idioma,
            0 if self.modo_infinito else combo_visible,
            cfg["controles"]["dash"],
            dash_listo,
        )
        if self.modo_infinito and self.estado == ESTADO_JUGANDO:
            hud.dibujar_combo_infinito(lienzo, idioma, combo_visible, tiempo)

        if (
            self.estado == ESTADO_TRANSICION
            and pygame.time.get_ticks() <= self.resumen_expira
        ):
            hud.dibujar_resumen_nivel(lienzo, idioma, self.nivel - 1, self.resumen_combo)

    def _dibujar_game_over(self, tiempo):
        cfg = self.configuracion
        self.eventos_visuales.dibujar_game_over(
            self.lienzo, self.nivel, pygame.time.get_ticks(), tiempo
        )
        if self.modo_infinito:
            self.hud.dibujar_resultado_infinito(
                self.lienzo,
                cfg["idioma"],
                self.puntaje,
                cfg["mejor_puntaje_infinito"],
            )
        self._dibujar_boton_reintentar()

    def _dibujar_boton_reintentar(self):
        lienzo, menu = self.lienzo, self.menu
        hover = self.boton_reintentar.collidepoint(self.pantalla.posicion_raton_logica())
        rect = menu._dibujar_boton_comic(lienzo, self.boton_reintentar, hover)
        menu._texto_centrado(
            lienzo,
            texto(self.configuracion["idioma"], "retry"),
            menu.font_prompt,
            rect.center,
            (255, 255, 255),
        )
        if hover:
            pulso = (math.sin(pygame.time.get_ticks() / 1000.0 * 4.0) + 1.0) * 0.5
            brillo = int(180 + pulso * 75)
            pygame.draw.line(
                lienzo, (255, brillo, 255), rect.topleft, (rect.right, rect.top), 2
            )


# --------------------------------------------------------------------------
# Punto de entrada
# --------------------------------------------------------------------------
def main(nivel_inicial=None, idioma_inicial="en"):
    """Crea el juego y ejecuta el bucle principal."""
    Juego(nivel_inicial, idioma_inicial).ejecutar()


def _valor_de_opcion(argv, opcion):
    """Devuelve el valor que sigue a ``opcion`` en ``argv`` (o None)."""
    if opcion in argv:
        indice = argv.index(opcion) + 1
        if indice < len(argv):
            return argv[indice]
    return None


if __name__ == "__main__":
    nivel_inicial = None
    valor_nivel = _valor_de_opcion(sys.argv, "--nivel")
    if valor_nivel is not None:
        try:
            nivel_inicial = int(valor_nivel)
        except ValueError:
            pass

    valor_idioma = _valor_de_opcion(sys.argv, "--idioma")
    idioma_inicial = valor_idioma.lower() if valor_idioma is not None else "en"

    main(nivel_inicial, idioma_inicial)