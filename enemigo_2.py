"""Copia del jugador, en negativo y desesperada, que lo persigue.

Es el mismo personaje (mismo esqueleto, gráficos y física), pero con la
paleta invertida y la expresión de desesperación del jugador (ojos
entornados con ojeras, sudor y temblor). Corre encorvado y de vez en
cuando el negativo parpadea, como un fallo de imagen.
"""

import math
import random

import pygame

from constantes import HEIGHT
from personaje import PersonajeHumanoide


class _EstadoTeclas:
    def __init__(self, pulsadas):
        self.pulsadas = pulsadas

    def __getitem__(self, tecla):
        return tecla in self.pulsadas


class _ClonNegativo(PersonajeHumanoide):
    """El personaje con la paleta en negativo y cara de desesperación.

    Solo cambia lo visual: la física y las colisiones son las del jugador.
    """

    def __init__(self, x, y, color, volumen_efectos=0.0):
        super().__init__(x, y, color, volumen_efectos=volumen_efectos)
        # Mismo aspecto que el jugador en los niveles de desesperación.
        self.paranoico = True
        self.desesperado = True
        self._negativo = True
        self._encorvado = 0.0
        self._glitch_frames = 0
        self._glitch_dx = 0
        self._proximo_glitch = pygame.time.get_ticks() + random.randint(1500, 3000)

    # ------------------------------------------------------------------
    # Negativo: se invierte cada color de la paleta ya sombreada, así que
    # lo oscuro (contornos, ojos) pasa a claro y lo claro (cara) a oscuro.
    # ------------------------------------------------------------------
    def _tono(self, factor):
        base = super()._tono(factor)
        if self._negativo:
            return (255 - base[0], 255 - base[1], 255 - base[2])
        return base

    def _dibujar_cara(self, superficie, centro_x, cabeza_y, lado_cabeza, color_trazo, color_ojo):
        # El trazo ya llega invertido (sale de ``_tono``); el blanco del ojo
        # está fijo en el código base, así que se invierte aquí.
        if self._negativo:
            color_ojo = (255 - color_ojo[0], 255 - color_ojo[1], 255 - color_ojo[2])
        super()._dibujar_cara(superficie, centro_x, cabeza_y, lado_cabeza, color_trazo, color_ojo)

    # ------------------------------------------------------------------
    # Lógica visual por fotograma
    # ------------------------------------------------------------------
    def mover(self, plataformas, controles=None, estado_teclas=None):
        super().mover(plataformas, controles, estado_teclas)

        # Postura encorvada al correr; erguido en reposo y en el aire.
        caminando = abs(self.vel_x) > 0.4 and self.en_suelo
        self._encorvado = self._lerp(self._encorvado, 0.35 if caminando else 0.0, 0.2)

        # Parpadeo del negativo: unos pocos cuadros con los colores
        # originales y un pequeño tirón lateral.
        ahora = pygame.time.get_ticks()
        if self._glitch_frames > 0:
            self._glitch_frames -= 1
            self._glitch_dx = random.choice((-3, -2, 2, 3)) if self._glitch_frames else 0
            self._negativo = self._glitch_frames == 0
        elif ahora >= self._proximo_glitch:
            self._glitch_frames = random.randint(3, 5)
            self._negativo = False
            self._proximo_glitch = ahora + random.randint(1800, 4200)

    def _sentido(self):
        """Hacia dónde avanza (o mira, si está quieto)."""
        if self.vel_x > 0.4:
            return 1
        if self.vel_x < -0.4:
            return -1
        return self.direccion

    def dibujar(self, superficie):
        # Ajustes temporales de pose: solo durante el dibujo, porque
        # ``mover`` recalcula estos valores en cada fotograma.
        guardado = (
            self.inclinacion_actual,
            self.cabeza_retraso,
            self.agachado_animacion,
            self.rect.x,
        )
        sentido = self._sentido()
        try:
            # Se echa hacia delante, con la cabeza adelantada.
            self.inclinacion_actual += sentido * self.amplitud_paso * 3.0
            self.cabeza_retraso += sentido * self.amplitud_paso * 4
            self.agachado_animacion = max(self.agachado_animacion, self._encorvado)
            self.rect.x += self._glitch_dx
            super().dibujar(superficie)
        finally:
            (
                self.inclinacion_actual,
                self.cabeza_retraso,
                self.agachado_animacion,
                self.rect.x,
            ) = guardado


class PerseguidorSepia:
    """Clon del jugador (en negativo y desesperado) que lo persigue."""

    # Color de respaldo: en cuanto se llama a ``sincronizar_jugador`` el
    # clon adopta el color del jugador (y lo muestra en negativo).
    COLOR_SEPIA = (156, 112, 66)
    CONTROLES = {
        "left": pygame.K_a,
        "right": pygame.K_d,
        "down": pygame.K_s,
        "jump": pygame.K_SPACE,
    }

    def __init__(self, x, y):
        self.personaje = _ClonNegativo(
            x, y, self.COLOR_SEPIA, volumen_efectos=0.0
        )
        self.personaje.dash_habilitado = False
        self.activa = True
        self._manteniendo_salto = False
        self._destino_salto = None
        self._posicion_inicial = self.personaje.rect.topleft
        self._plataforma_inicial = None

    @property
    def rect(self):
        return self.personaje.rect

    @property
    def en_suelo(self):
        return self.personaje.en_suelo

    @en_suelo.setter
    def en_suelo(self, valor):
        self.personaje.en_suelo = valor

    @property
    def plataforma_actual(self):
        return self.personaje.plataforma_actual

    @plataforma_actual.setter
    def plataforma_actual(self, plataforma):
        self.personaje.plataforma_actual = plataforma

    def sincronizar_jugador(self, jugador):
        """Mantiene la velocidad, la física y el color del clon al ritmo del jugador.

        No se copia ``euforico``: ese modo cambia la cara a una alegre y
        desquiciada y anularía la expresión de desesperación del clon.
        """
        clon = self.personaje
        clon.velocidad = jugador.velocidad
        clon.gravedad = jugador.gravedad
        clon.fuerza_salto = jugador.fuerza_salto
        clon.acel_suelo = jugador.acel_suelo
        clon.friccion_suelo = jugador.friccion_suelo
        clon.acel_aire = jugador.acel_aire
        clon.acel_aire_doble_salto = jugador.acel_aire_doble_salto
        clon.friccion_aire = jugador.friccion_aire
        clon.factor_giro = jugador.factor_giro

        # Mismo color que el jugador: el negativo se aplica al dibujar.
        color = getattr(jugador, "color", None)
        if color is not None and tuple(color[:3]) != tuple(clon.color[:3]):
            clon.color = tuple(color[:3])
            clon._halo_personaje = None
            clon._silueta_color = None

    def _plataforma_siguiente(self, plataformas, direccion, objetivo):
        actual = self.personaje.plataforma_actual
        if actual is None:
            return None

        hitbox_actual = actual.rect
        altura_salto = PersonajeHumanoide.altura_maxima_salto(
            self.personaje.gravedad
        )
        fuerza_salto = abs(self.personaje.fuerza_salto)
        gravedad = max(0.01, self.personaje.gravedad)
        candidatas = []
        for plataforma in plataformas:
            if plataforma is actual or plataforma.es_trampa:
                continue
            hitbox = plataforma.rect
            avance = (hitbox.centerx - hitbox_actual.centerx) * direccion
            diferencia_altura = hitbox_actual.top - hitbox.top
            discriminante = fuerza_salto ** 2 - 2 * gravedad * diferencia_altura
            if discriminante < 0:
                continue
            tiempo_salto = (fuerza_salto + math.sqrt(discriminante)) / gravedad
            alcance_horizontal = self.personaje.velocidad * tiempo_salto * 0.75
            distancia_hueco = (
                max(0, hitbox_actual.left - hitbox.right)
                if direccion < 0
                else max(0, hitbox.left - hitbox_actual.right)
            )
            if (
                0 < avance <= 300
                and -180 <= diferencia_altura <= altura_salto - 20
                and distancia_hueco <= alcance_horizontal
                and abs(hitbox.centerx - objetivo.centerx)
                < abs(hitbox_actual.centerx - objetivo.centerx)
            ):
                candidatas.append(plataforma)
        return min(
            candidatas,
            key=lambda plataforma: abs(plataforma.rect.centerx - hitbox_actual.centerx),
            default=None,
        )

    def mover(self, plataformas, objetivo):
        if not self.activa:
            return

        clon = self.personaje
        if (
            clon.en_suelo
            and clon.plataforma_actual is self._destino_salto
            and self._destino_salto is not None
        ):
            self._destino_salto = None

        destino = self._destino_salto if not clon.en_suelo else None
        referencia_x = destino.rect.centerx if destino is not None else objetivo.centerx
        diferencia_x = referencia_x - clon.rect.centerx
        direccion = 1 if diferencia_x > 12 else -1 if diferencia_x < -12 else 0
        if destino is not None and direccion:
            aceleracion_frenado = max(
                0.1, clon.acel_aire * clon.factor_giro
            )
            distancia_frenado = clon.vel_x ** 2 / (2 * aceleracion_frenado)
            if abs(diferencia_x) <= distancia_frenado + clon.rect.width / 2:
                direccion = -1 if clon.vel_x > 0 else 1 if clon.vel_x < 0 else 0

        plataforma_siguiente = (
            self._plataforma_siguiente(plataformas, direccion, objetivo)
            if direccion and clon.en_suelo
            else None
        )

        pulsar_salto = False
        actual = clon.plataforma_actual
        if clon.en_suelo and actual is not None and direccion:
            distancia_borde = (
                actual.rect.right - clon.rect.right
                if direccion > 0
                else clon.rect.left - actual.rect.left
            )
            necesita_salto = plataforma_siguiente is not None and (
                plataforma_siguiente.rect.top < actual.rect.top - 15
                or (
                    plataforma_siguiente.rect.left > actual.rect.right
                    if direccion > 0
                    else plataforma_siguiente.rect.right < actual.rect.left
                )
            )
            if necesita_salto and distancia_borde <= max(20, clon.velocidad * 4):
                pulsar_salto = True
            elif (
                plataforma_siguiente is not None
                and distancia_borde <= max(20, clon.velocidad * 4)
            ):
                self._destino_salto = plataforma_siguiente
            elif (
                plataforma_siguiente is None
                and distancia_borde <= max(24, abs(clon.vel_x) * 4)
            ):
                direccion = 0
                clon.vel_x = 0.0
                clon._resto_x = 0.0
        elif clon.en_suelo and actual is None:
            direccion = 0

        if clon.en_suelo or clon.vel_y >= 0:
            self._manteniendo_salto = False

        if pulsar_salto and not self._manteniendo_salto:
            clon.solicitar_salto()
            self._manteniendo_salto = True
            self._destino_salto = plataforma_siguiente

        teclas_pulsadas = set()
        if direccion < 0:
            teclas_pulsadas.add(self.CONTROLES["left"])
        elif direccion > 0:
            teclas_pulsadas.add(self.CONTROLES["right"])
        if self._manteniendo_salto and clon.vel_y < 0:
            teclas_pulsadas.add(self.CONTROLES["jump"])

        clon.mover(
            plataformas,
            self.CONTROLES,
            estado_teclas=_EstadoTeclas(teclas_pulsadas),
        )
        if clon.rect.top >= HEIGHT - 40:
            clon.rect.topleft = self._posicion_inicial
            clon.reiniciar_movimiento()
            clon.plataforma_actual = self._plataforma_inicial
            clon.en_suelo = True
            self._manteniendo_salto = False
            self._destino_salto = None

    def nivel_alerta(self):
        return 0.0

    def derrotar(self, direccion):
        if not self.activa:
            return False
        self.activa = False
        return True

    def dibujar(self, superficie, tiempo):
        if self.activa:
            self.personaje.dibujar(superficie)


def crear_perseguidor(plataforma, punto_a_perseguir):
    """Coloca el clon apoyado en la parte superior de una plataforma."""
    x = (
        plataforma.rect.right - 40
        if punto_a_perseguir.x < plataforma.rect.centerx
        else plataforma.rect.left
    )
    y = plataforma.rect_colision().top - 70
    perseguidor = PerseguidorSepia(x, y)
    perseguidor.plataforma_actual = plataforma
    perseguidor._plataforma_inicial = plataforma
    perseguidor.en_suelo = True
    return perseguidor