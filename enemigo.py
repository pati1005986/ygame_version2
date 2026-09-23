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

    Puede saltar en dos situaciones muy concretas -nunca al azar-: para
    cruzar un hueco entre plataformas mientras patrulla, o para alcanzar al
    jugador cuando lo persigue y lo detecta claramente por encima. Cada
    salto lleva un instante de anticipación (se agacha) y otro de aterrizaje
    (se aplasta y levanta una nube de polvo), para que se lea como un gesto
    deliberado y no como un tirón brusco.

    Args:
        x: Posición horizontal inicial del rectángulo de colisión.
        y: Posición vertical inicial del rectángulo de colisión.
    """

    COLOR_BASE = (132, 132, 132)

    def __init__(
        self,
        x,
        y,
        velocidad_patrulla=1.8,
        velocidad_persecucion=3.0,
        rango_deteccion=220,
    ):
        self.rect = pygame.Rect(x, y, 32, 58)
        self.vel_y = 0
        self.velocidad_patrulla = velocidad_patrulla
        self.velocidad_persecucion = velocidad_persecucion
        self.rango_deteccion = rango_deteccion
        self.en_suelo = False
        self.plataforma_actual = None
        self.direccion = random.choice((-1, 1))
        self.pixel = 4
        self.fase = random.uniform(0, math.tau)
        self.activa = True  # permite congelarla desde fuera si hace falta

        # --- salto ---
        self.fuerza_salto = -11.5
        self.temporizador_salto = 0  # cuadros restantes de enfriamiento
        self.enfriamiento_salto = 30
        self.distancia_max_salto_patrulla = 78
        self.altura_min_salto_persecucion = 42
        self.altura_max_salto_persecucion = 160
        self.cuadros_anticipacion = 0
        self.anticipacion_total = 7
        self.saltando_hacia = self.direccion
        self.cuadros_aterrizaje = 0
        self.aterrizaje_total = 9
        self._particulas_polvo = []

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
    # Salto: decisión y física
    # ------------------------------------------------------------------
    def _buscar_salto_de_borde(self, plataformas):
        """Si el suelo se acaba justo delante y hay otra plataforma
        alcanzable de un salto, devuelve la dirección a la que conviene
        saltar; si no, ``None`` (y entonces se sigue dando la vuelta como
        antes). Evita que la entidad se lance a huecos imposibles."""
        if self.plataforma_actual is None:
            return None

        borde_actual = self.plataforma_actual.rect
        cerca_del_borde = (
            self.direccion > 0 and self.rect.right >= borde_actual.right - 4
        ) or (
            self.direccion < 0 and self.rect.left <= borde_actual.left + 4
        )
        if not cerca_del_borde:
            return None

        for plataforma in plataformas:
            if plataforma is self.plataforma_actual or plataforma.es_trampa:
                continue
            if self.direccion > 0:
                hueco = plataforma.rect.left - borde_actual.right
            else:
                hueco = borde_actual.left - plataforma.rect.right
            if not (0 < hueco <= self.distancia_max_salto_patrulla):
                continue
            diferencia_altura = plataforma.rect.top - borde_actual.top
            if -70 <= diferencia_altura <= 34:
                return self.direccion
        return None

    def _iniciar_anticipacion_salto(self, direccion_destino):
        self.cuadros_anticipacion = self.anticipacion_total
        self.saltando_hacia = direccion_destino

    def _crear_polvo_aterrizaje(self):
        centro_x = self.rect.centerx
        pie_y = self.rect.bottom
        for despl in (-10, 0, 10):
            self._particulas_polvo.append(
                {
                    "x": centro_x + despl,
                    "y": pie_y,
                    "vx": despl * 0.15,
                    "vy": -1.2,
                    "vida": 14,
                    "vida_max": 14,
                }
            )

    def _actualizar_particulas(self):
        vivas = []
        for particula in self._particulas_polvo:
            particula["x"] += particula["vx"]
            particula["y"] += particula["vy"]
            particula["vy"] += 0.15
            particula["vida"] -= 1
            if particula["vida"] > 0:
                vivas.append(particula)
        self._particulas_polvo = vivas

    # ------------------------------------------------------------------
    # Movimiento
    # ------------------------------------------------------------------
    def mover(self, plataformas, objetivo_rect=None):
        """Aplica gravedad, resuelve colisiones con las plataformas y decide
        si patrulla, persigue al jugador o salta.

        ``objetivo_rect`` es opcional: si se pasa el rect del jugador y está
        lo bastante cerca (``rango_deteccion``) y a una altura parecida, la
        entidad avanza hacia él en vez de seguir su patrulla habitual. Al
        perseguir puede llegar a caminar fuera del borde de su plataforma
        (y caer) si el jugador está por debajo o lejos, lo que abre una vía
        de escape legítima para el jugador; solo salta cuando el jugador
        está claramente por encima y cerca.

        El salto en sí nunca es instantáneo: primero hay un breve instante
        de anticipación (se agacha, sin avanzar) y luego, al aterrizar, unos
        cuadros de aplastamiento con una nube de polvo. Esto evita el efecto
        de "tirón" que hace ver torpe a una IA saltando.
        """
        if not self.activa:
            return

        if self.temporizador_salto > 0:
            self.temporizador_salto -= 1

        persiguiendo = False
        dx = dy = 0
        if objetivo_rect is not None:
            dx = objetivo_rect.centerx - self.rect.centerx
            dy = objetivo_rect.centery - self.rect.centery
            if abs(dx) < self.rango_deteccion and abs(dy) < 80:
                persiguiendo = True
                self.direccion = 1 if dx > 0 else -1

        if self.cuadros_anticipacion > 0:
            # Tomando impulso: se detiene un instante en vez de saltar de
            # golpe, para que el gesto se note antes de que ocurra.
            self.cuadros_anticipacion -= 1
            dx_mov = 0
            if self.cuadros_anticipacion == 0 and self.en_suelo:
                self.vel_y = self.fuerza_salto
                self.en_suelo = False
                self.direccion = self.saltando_hacia
                self.temporizador_salto = self.enfriamiento_salto
        else:
            velocidad = self.velocidad_persecucion if persiguiendo else self.velocidad_patrulla
            dx_mov = velocidad * self.direccion

            puede_evaluar_salto = self.en_suelo and self.temporizador_salto <= 0
            if puede_evaluar_salto:
                if (
                    persiguiendo
                    and -self.altura_max_salto_persecucion <= dy <= -self.altura_min_salto_persecucion
                    and abs(dx) < 140
                ):
                    self._iniciar_anticipacion_salto(self.direccion)
                elif not persiguiendo:
                    candidato = self._buscar_salto_de_borde(plataformas)
                    if candidato is not None:
                        self._iniciar_anticipacion_salto(candidato)

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

        estaba_en_suelo = self.en_suelo
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

        if self.en_suelo and not estaba_en_suelo:
            self.cuadros_aterrizaje = self.aterrizaje_total
            self._crear_polvo_aterrizaje()
        elif self.cuadros_aterrizaje > 0:
            self.cuadros_aterrizaje -= 1

        self._actualizar_particulas()

        # En patrulla (sin perseguir ni saltar), da la vuelta al llegar al
        # borde de su propia plataforma para no caminar hacia el vacío por
        # accidente -salvo que ya se haya decidido saltar el hueco arriba.
        if (
            self.en_suelo
            and not persiguiendo
            and self.cuadros_anticipacion == 0
            and self.plataforma_actual is not None
        ):
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
        detalles de armadura, más una pose que cambia según si está
        patrullando, agachándose para saltar, en el aire o aterrizando."""
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
        self._dibujar_particulas(superficie)

        en_el_aire = not self.en_suelo
        anticipando = self.cuadros_anticipacion > 0
        aterrizando = self.cuadros_aterrizaje > 0 and not en_el_aire

        # Compresion/estiramiento vertical con bloques (nada de escalar
        # superficies, para no perder el aspecto pixelado): se agacha antes
        # de saltar, se estira un poco mientras sube y se aplasta al caer.
        compresion = 0
        if anticipando:
            compresion = 4
        elif aterrizando:
            progreso = self.cuadros_aterrizaje / self.aterrizaje_total
            compresion = int(6 * progreso)
        estiramiento = 4 if (en_el_aire and self.vel_y < -1) else 0

        alto_cuerpo = self.rect.height - 18 - compresion + estiramiento
        cuerpo_y = pie_y - alto_cuerpo

        self._bloque_contorneado(
            superficie, centro_x - 15, cuerpo_y + 4, 30, alto_cuerpo - 8, base, contorno
        )
        self._bloque_contorneado(superficie, centro_x - 20, cuerpo_y + 8, 6, 20, oscuro, contorno)
        self._bloque_contorneado(superficie, centro_x + 14, cuerpo_y + 8, 6, 20, oscuro, contorno)
        self._bloque(superficie, centro_x - 9, cuerpo_y + 12, 18, 4, medio)

        self._dibujar_piernas(
            superficie, centro_x, cuerpo_y, tiempo, medio, oscuro, contorno, en_el_aire, anticipando
        )

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
        self._bloque(superficie, centro_x - 8, cabeza_y - 5, 16, 4, medio)

        p = self.pixel
        y_ranura = cabeza_y + 9
        self._bloque(superficie, centro_x - 10, y_ranura, 7, p, sombra_oscura)
        self._bloque(superficie, centro_x + 3, y_ranura, 7, p, sombra_oscura)
        self._bloque(superficie, centro_x - 2, y_ranura - 1, 4, p + 2, contorno)

        lado_sombra_x = centro_x + 10 if self.direccion > 0 else centro_x - 15
        self._bloque(superficie, lado_sombra_x, cuerpo_y + 2, 4, alto_cuerpo - 6, oscuro)

    def _dibujar_piernas(self, superficie, centro_x, cuerpo_y, tiempo, medio, oscuro, contorno, en_el_aire, anticipando):
        ancho_pierna = 8
        y_pierna = cuerpo_y + 18
        alta_pierna = 22

        if en_el_aire:
            # Piernas recogidas hacia el cuerpo, como en pleno salto.
            alta_pierna = 14
            x_izq = centro_x - 8
            x_der = centro_x
            self._bloque_contorneado(superficie, x_izq, y_pierna, ancho_pierna, alta_pierna, medio, contorno)
            self._bloque_contorneado(superficie, x_der, y_pierna, ancho_pierna, alta_pierna, medio, contorno)
            return

        if anticipando:
            # Postura mas ancha y flexionada, tomando impulso.
            x_izq = centro_x - 14
            x_der = centro_x + 6
        else:
            # Balanceo sutil de las piernas al caminar, en vez de una
            # postura estatica.
            desfase = int(round(2 * math.sin(tiempo * 10 + self.fase)))
            x_izq = centro_x - 11 + desfase
            x_der = centro_x + 3 - desfase

        self._bloque_contorneado(superficie, x_izq, y_pierna, ancho_pierna, alta_pierna, medio, contorno)
        self._bloque_contorneado(superficie, x_der, y_pierna, ancho_pierna, alta_pierna, medio, contorno)
        self._bloque(superficie, x_izq + 1, y_pierna + 12, 6, 4, oscuro)
        self._bloque(superficie, x_der + 1, y_pierna + 12, 6, 4, oscuro)

    def _dibujar_sombra(self, superficie, centro_x, pie_y):
        """Sombra de contacto simple, igual de discreta que el resto de su
        diseño. Se encoge un poco mientras la entidad está en el aire, para
        reforzar la sensación de altura del salto."""
        ancho_sombra = 28 if self.en_suelo else 18
        sombra = pygame.Surface((ancho_sombra, 6), pygame.SRCALPHA)
        sombra.fill((0, 0, 0, 110 if self.en_suelo else 70))
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

    def _dibujar_particulas(self, superficie):
        """Nube de polvo discreta al aterrizar; se disuelve sola en unos
        cuadros y nunca se acumula porque ``_actualizar_particulas`` la
        limpia en ``mover``."""
        for particula in self._particulas_polvo:
            alpha = int(160 * (particula["vida"] / particula["vida_max"]))
            radio = 3
            capa = pygame.Surface((radio * 2, radio * 2), pygame.SRCALPHA)
            pygame.draw.circle(capa, (190, 190, 190, alpha), (radio, radio), radio)
            superficie.blit(capa, (particula["x"] - radio, particula["y"] - radio))


# --------------------------------------------------------------------------
# Generación por nivel
# --------------------------------------------------------------------------
def generar_entidades(
    nivel,
    plataformas,
    punto_a_evitar,
    radio_evitar=90,
    velocidad_patrulla=1.8,
    velocidad_persecucion=3.0,
    rango_deteccion=220,
):
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
        velocidad_patrulla, velocidad_persecucion, rango_deteccion: se
            pasan a cada ``EntidadGris`` creada. Pensados para venir de
            ``parametros_dificultad`` (ver ``dificultad.py``) y así crecer
            con el nivel en vez de quedarse fijos para siempre; si no se
            indican, se usan los valores originales.

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
        entidades.append(
            EntidadGris(
                x,
                y,
                velocidad_patrulla=velocidad_patrulla,
                velocidad_persecucion=velocidad_persecucion,
                rango_deteccion=rango_deteccion,
            )
        )
    return entidades