"""Entidad enemiga del juego: una presencia gris, simple y sin rostro, ajena
a la paleta de color del resto del mundo.

Mientras las plataformas y el jugador derivan sus colores de un ``hue``
(``color_desde_hue``), esta entidad se construye a partir de un único gris
puro (r == g == b), así que ningún matiz se le puede filtrar por accidente:
sea cual sea la iluminación o la animación, sigue siendo gris. Es un
contraste deliberado con lo vívido y expresivo del resto del juego, y encaja
con la desaturación progresiva de los niveles (``saturacion_nivel`` en
``juego.py``): a medida que el mundo pierde color, estas entidades se
vuelven más frecuentes, como si fueran un anticipo de lo que se avecina.
"""

import math
import random

import pygame


class EntidadGris:
    """Enemigo simple: patrulla su plataforma y persigue al jugador si lo
    detecta cerca, sin más gesto que una franja vacía en vez de rostro.

    Args:
        x: Posición horizontal inicial del rectángulo de colisión.
        y: Posición vertical inicial del rectángulo de colisión.
    """

    COLOR_BASE = (132, 132, 132)

    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 32, 58)
        self.vel_y = 0
        self.velocidad_patrulla = 1.8
        self.velocidad_persecucion = 3.0
        self.rango_deteccion = 220
        self.en_suelo = False
        self.plataforma_actual = None
        self.direccion = random.choice((-1, 1))
        self.pixel = 4
        self.fase = random.uniform(0, math.tau)
        self.activa = True  # permite congelarla desde fuera si hace falta

    # ------------------------------------------------------------------
    # Utilidades de dibujo (mismo estilo de bloques que PersonajeHumanoide,
    # para que encaje visualmente con el resto del juego).
    # ------------------------------------------------------------------
    def _tono(self, factor):
        """Variante de brillo de ``COLOR_BASE``. Como sus tres canales son
        iguales, el resultado es siempre un gris puro, nunca un color."""
        v = max(0, min(255, int(self.COLOR_BASE[0] * factor)))
        return (v, v, v)

    def _bloque(self, superficie, x, y, ancho, alto, color):
        p = self.pixel
        rx = round(x / p) * p
        ry = round(y / p) * p
        ranch = max(p, round(ancho / p) * p)
        ralto = max(p, round(alto / p) * p)
        pygame.draw.rect(superficie, color, (rx, ry, ranch, ralto))

    def _bloque_contorneado(self, superficie, x, y, ancho, alto, color, color_contorno):
        g = self.pixel
        self._bloque(superficie, x - g // 2, y - g // 2, ancho + g, alto + g, color_contorno)
        self._bloque(superficie, x, y, ancho, alto, color)

    # ------------------------------------------------------------------
    # Movimiento
    # ------------------------------------------------------------------
    def mover(self, plataformas, objetivo_rect=None):
        """Aplica gravedad, resuelve colisiones con las plataformas y decide
        si patrulla o persigue al jugador.

        ``objetivo_rect`` es opcional: si se pasa el rect del jugador y está
        lo bastante cerca (``rango_deteccion``) y a una altura parecida, la
        entidad avanza hacia él en vez de seguir su patrulla habitual. Al
        perseguir puede llegar a caminar fuera del borde de su plataforma
        (y caer), lo que abre una vía de escape legítima para el jugador.
        """
        if not self.activa:
            return

        persiguiendo = False
        if objetivo_rect is not None:
            dx = objetivo_rect.centerx - self.rect.centerx
            dy = abs(objetivo_rect.centery - self.rect.centery)
            if abs(dx) < self.rango_deteccion and dy < 80:
                persiguiendo = True
                self.direccion = 1 if dx > 0 else -1

        velocidad = self.velocidad_persecucion if persiguiendo else self.velocidad_patrulla
        dx_mov = velocidad * self.direccion

        self.vel_y += 0.6
        dy_mov = self.vel_y

        self.rect.x += dx_mov
        for plataforma in plataformas:
            if self.rect.colliderect(plataforma.rect):
                if dx_mov > 0:
                    self.rect.right = plataforma.rect.left
                elif dx_mov < 0:
                    self.rect.left = plataforma.rect.right
                self.direccion *= -1

        self.rect.y += dy_mov
        self.en_suelo = False
        self.plataforma_actual = None
        for plataforma in plataformas:
            if self.rect.colliderect(plataforma.rect):
                if dy_mov > 0:
                    self.rect.bottom = plataforma.rect.top
                    self.vel_y = 0
                    self.en_suelo = True
                    self.plataforma_actual = plataforma
                elif dy_mov < 0:
                    self.rect.top = plataforma.rect.bottom
                    self.vel_y = 0

        # En patrulla (sin perseguir), da la vuelta al llegar al borde de su
        # propia plataforma para no caminar hacia el vacío por accidente.
        if self.en_suelo and not persiguiendo and self.plataforma_actual is not None:
            borde = self.plataforma_actual.rect
            if self.rect.right >= borde.right and self.direccion > 0:
                self.direccion = -1
            elif self.rect.left <= borde.left and self.direccion < 0:
                self.direccion = 1

    # ------------------------------------------------------------------
    # Dibujado
    # ------------------------------------------------------------------
    def dibujar(self, superficie, tiempo):
        """Dibuja la entidad con silueta más definida, máscara facial y
        detalles de armadura para que se sienta más amenazante sin perder la
        estética minimalista del juego."""
        centro_x = self.rect.centerx
        pie_y = self.rect.bottom

        claro = self._tono(1.45)
        base = self._tono(1.0)
        medio = self._tono(0.8)
        oscuro = self._tono(0.55)
        contorno = self._tono(0.18)
        sombra_oscura = self._tono(0.08)

        self._dibujar_sombra(superficie, centro_x, pie_y)
        self._dibujar_halo(superficie, tiempo)

        # Cuerpo principal con armadura compacta y hombros más anchos.
        alto_cuerpo = self.rect.height - 18
        cuerpo_y = pie_y - alto_cuerpo
        self._bloque_contorneado(
            superficie, centro_x - 15, cuerpo_y + 4, 30, alto_cuerpo - 8, base, contorno
        )

        # Placas laterales y refuerzo de hombros.
        self._bloque_contorneado(
            superficie, centro_x - 20, cuerpo_y + 8, 6, 20, oscuro, contorno
        )
        self._bloque_contorneado(
            superficie, centro_x + 14, cuerpo_y + 8, 6, 20, oscuro, contorno
        )

        # Cinturón / costura central para dar sensación de estructura.
        self._bloque(superficie, centro_x - 9, cuerpo_y + 12, 18, 4, medio)

        # Piernas y rodillas más definidas.
        ancho_pierna = 8
        x_izq = centro_x - 11
        x_der = centro_x + 3
        y_pierna = cuerpo_y + 18
        alta_pierna = 22
        self._bloque_contorneado(superficie, x_izq, y_pierna, ancho_pierna, alta_pierna, medio, contorno)
        self._bloque_contorneado(superficie, x_der, y_pierna, ancho_pierna, alta_pierna, medio, contorno)
        self._bloque(superficie, x_izq + 1, y_pierna + 12, 6, 4, oscuro)
        self._bloque(superficie, x_der + 1, y_pierna + 12, 6, 4, oscuro)

        # Cabeza con máscara: más alta, más angular, con una franja central
        # que parece una “ranura de visión” vacía.
        lado_cabeza = 22
        cabeza_y = cuerpo_y - lado_cabeza - 4
        self._bloque_contorneado(
            superficie,
            centro_x - lado_cabeza // 2,
            cabeza_y,
            lado_cabeza,
            lado_cabeza,
            claro,
            contorno,
        )

        # Coronilla / elemento de energía flotante.
        self._bloque(superficie, centro_x - 8, cabeza_y - 5, 16, 4, medio)

        # Máscara con dos rendijas oscuras y una línea central ligeramente más
        # luminosa para reforzar el vacío de la mirada.
        p = self.pixel
        ancho_ranura = p * 3
        y_ranura = cabeza_y + 9
        self._bloque(superficie, centro_x - 10, y_ranura, 7, p, sombra_oscura)
        self._bloque(superficie, centro_x + 3, y_ranura, 7, p, sombra_oscura)
        self._bloque(superficie, centro_x - 2, y_ranura - 1, 4, p + 2, contorno)

        # Sombra lateral para “peso” y dirección de movimiento.
        lado_sombra_x = centro_x + 10 if self.direccion > 0 else centro_x - 15
        self._bloque(superficie, lado_sombra_x, cuerpo_y + 2, 4, alto_cuerpo - 6, oscuro)

    def _dibujar_sombra(self, superficie, centro_x, pie_y):
        """Sombra de contacto simple, igual de discreta que el resto de su
        diseño."""
        sombra = pygame.Surface((28, 6), pygame.SRCALPHA)
        sombra.fill((0, 0, 0, 110))
        rect = sombra.get_rect(center=(centro_x, pie_y + 2))
        superficie.blit(sombra, rect.topleft)

    def _dibujar_halo(self, superficie, tiempo):
        """Aura gris muy tenue, pulsando despacio: sugiere que algo a su
        alrededor pierde color, sin llegar a afectar realmente los píxeles
        de la escena (más barato de calcular y suficiente para el efecto)."""
        radio = self.rect.height * 0.85
        pulso = 0.5 + 0.5 * math.sin(tiempo * 1.4 + self.fase)
        capa = pygame.Surface((radio * 2, radio * 2), pygame.SRCALPHA)
        alpha = int(26 + 14 * pulso)
        pygame.draw.circle(capa, (150, 150, 150, alpha), (radio, radio), radio)
        superficie.blit(capa, (self.rect.centerx - radio, self.rect.centery - radio))


# --------------------------------------------------------------------------
# Generación por nivel
# --------------------------------------------------------------------------
def generar_entidades(nivel, plataformas, punto_a_evitar, radio_evitar=90):
    """Crea las entidades grises para un nivel dado.

    No aparecen antes del nivel 3 (para que el jugador se familiarice
    primero con el salto y las trampas) y su cantidad crece poco a poco con
    el nivel, en paralelo a como el mundo va perdiendo color.

    Args:
        nivel: Número del nivel actual.
        plataformas: Lista de ``Plataforma`` ya generadas para ese nivel.
        punto_a_evitar: Punto (como ``POS_SPAWN``) cerca del cual no deben
            aparecer entidades, para no recibir al jugador con un enemigo
            encima nada más empezar.
        radio_evitar: Distancia mínima a ``punto_a_evitar``.

    Returns:
        Una lista de ``EntidadGris``, vacía si el nivel es demasiado bajo.
    """
    if nivel < 3:
        return []

    cantidad = min(1 + (nivel - 3) // 3, 4)

    candidatas = [
        plataforma
        for plataforma in plataformas
        if not plataforma.es_trampa
        and plataforma.rect.width >= 40
        and pygame.Vector2(plataforma.rect.center).distance_to(punto_a_evitar) > radio_evitar
    ]
    random.shuffle(candidatas)

    entidades = []
    for plataforma in candidatas[:cantidad]:
        x = plataforma.rect.centerx - 16
        y = plataforma.rect.top - 58
        entidades.append(EntidadGris(x, y))
    return entidades