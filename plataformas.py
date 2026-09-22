"""Plataformas normales y plataformas trampa del juego."""

import colorsys
import math
import random

import pygame


def color_desde_hue(hue, saturacion=0.65, valor=0.95):
    """Convierte un matiz HSV en un color RGB vivo."""
    r, g, b = colorsys.hsv_to_rgb(hue % 1.0, saturacion, valor)
    return int(r * 255), int(g * 255), int(b * 255)


def _mezclar(color_a, color_b, factor):
    """Interpola linealmente entre dos colores RGB (factor entre 0 y 1)."""
    factor = max(0.0, min(1.0, factor))
    return tuple(int(a + (b - a) * factor) for a, b in zip(color_a, color_b))


class Plataforma:
    """Plataforma sólida, opcionalmente disfrazada de trampa vibrante.

    El diseño busca una estética pictórica: capas de color superpuestas,
    pinceladas sueltas y pequeños acentos que dan la sensación de una pieza
    pintada a mano en lugar de un bloque geométrico plano.

    Además de las plataformas trampa, algunas plataformas normales cobran
    vida por su cuenta:

    - **Movimiento**: una fracción de las plataformas normales se desliza
      lentamente en horizontal o en vertical (ver ``patron_movimiento``),
      con una guía punteada sutil que insinúa su recorrido. El movimiento
      actualiza ``self.rect`` de verdad, así que la colisión existente en
      el resto del juego lo sigue automáticamente sin cambios. Cada
      fotograma queda disponible en ``desplazamiento_reciente`` (un
      ``pygame.Vector2``) por si el código del jugador quiere "montarlo"
      sumando ese valor a su posición mientras está de pie encima.
    - **Reacción al aterrizaje**: llamando a ``notificar_aterrizaje()``
      desde el código de colisiones del jugador (cuando aterriza desde
      arriba sobre esta plataforma) se dispara un remezón elástico tipo
      "squash & stretch" y una pequeña salpicadura de partículas de
      pintura. Es puramente visual: no toca ``self.rect``, así que no
      afecta la física.
    """

    COLOR_PELIGRO = (235, 60, 55)
    COLOR_HUECO = (22, 13, 35)
    COLOR_HUECO_PROFUNDO = (6, 4, 10)

    # Probabilidad de que una plataforma normal (no trampa) se vuelva móvil
    # por su cuenta, para que un nivel no se sienta hecho de bloques muertos.
    PROBABILIDAD_MOVIMIENTO = 0.35
    GRAVEDAD_PARTICULAS = 260.0

    def __init__(
        self,
        x,
        y,
        w,
        h,
        hue,
        es_trampa=False,
        patron_movimiento=None,
        amplitud_movimiento=None,
        velocidad_movimiento=None,
    ):
        self.rect = pygame.Rect(x, y, w, h)
        self.hue = hue
        self.es_trampa = es_trampa
        self.fase = random.uniform(0, math.tau)
        self.trampa_activada = False
        self.progreso_trampa = 0.0

        # ---------------- movimiento ----------------
        # Si no se especifica un patrón, una fracción de las plataformas
        # normales se vuelve móvil por su cuenta (las trampas nunca se
        # mueven solas, para no complicar su lectura visual).
        if patron_movimiento is None and not es_trampa:
            if random.random() < self.PROBABILIDAD_MOVIMIENTO:
                patron_movimiento = random.choice(("horizontal", "vertical"))
        self.patron_movimiento = patron_movimiento
        self.amplitud_movimiento = (
            amplitud_movimiento if amplitud_movimiento is not None else random.uniform(35, 70)
        )
        self.velocidad_movimiento = (
            velocidad_movimiento if velocidad_movimiento is not None else random.uniform(0.5, 0.9)
        )
        self._origen = pygame.Vector2(self.rect.x, self.rect.y)
        self._fase_movimiento = random.uniform(0, math.tau)
        self._reloj_movimiento = 0.0
        self.desplazamiento_reciente = pygame.Vector2(0, 0)

        # ---------------- squash/wobble de aterrizaje ----------------
        self._squash = 0.0
        self._squash_velocidad = 0.0
        self._particulas = []

        # Detalles generados una sola vez para que la textura sea estable
        # cuadro a cuadro (en vez de parpadear con valores aleatorios nuevos
        # en cada dibujado).
        self._generar_detalles()

    # ------------------------------------------------------------------
    # Preparación de detalles decorativos (una sola vez por plataforma)
    # ------------------------------------------------------------------
    def _generar_detalles(self):
        """Precalcula pinceladas, salpicaduras y acentos propios de esta
        plataforma para reutilizarlos en cada fotograma."""
        cantidad_manchas = random.randint(4, 7)
        self.manchas = [
            (
                random.uniform(0.08, 0.9),   # posición x relativa
                random.uniform(0.15, 0.85),  # posición y relativa
                random.uniform(0.05, 0.13),  # radio relativo al ancho
                random.uniform(-0.08, 0.08), # variación de matiz
                random.randint(60, 130),     # alpha
                random.choice([True, False]),  # más clara u oscura
            )
            for _ in range(cantidad_manchas)
        ]

        # Puntos de una pincelada curva decorativa (trazo suelto).
        self.trazo = [
            (random.uniform(0.1, 0.3), random.uniform(0.2, 0.8)),
            (random.uniform(0.35, 0.55), random.uniform(0.1, 0.4)),
            (random.uniform(0.6, 0.9), random.uniform(0.3, 0.75)),
        ]

        # Salpicaduras finas ("splatter") cerca de una esquina aleatoria.
        esquina = random.choice([(0.06, 0.15), (0.9, 0.2), (0.15, 0.8), (0.85, 0.75)])
        self.salpicaduras = [
            (
                esquina[0] + random.uniform(-0.06, 0.06),
                esquina[1] + random.uniform(-0.08, 0.08),
                random.uniform(1.4, 3.2),
            )
            for _ in range(5)
        ]

        # Grietas radiales que aparecerán solo cuando la trampa se active.
        if self.es_trampa:
            self.grietas = [
                math.tau * i / 7 + random.uniform(-0.18, 0.18) for i in range(7)
            ]
            self.goteo = [
                (random.uniform(0.15, 0.85), random.uniform(0.6, 1.5), random.uniform(0, math.tau))
                for _ in range(4)
            ]
        else:
            self.grietas = []
            self.goteo = []

        # Rendimiento: las manchas/trazo/salpicaduras no dependen de
        # `tiempo` ni cambian tras crearse, pero antes se redibujaban en
        # una Surface nueva en CADA fotograma para CADA plataforma (hasta
        # 14 en pantalla). Se precalcula una sola vez aquí, usando el
        # matiz base (sin la pequeña oscilación de `tiempo`), y luego solo
        # se hace un blit barato en cada fotograma.
        self._capa_textura = None

    def _construir_capa_textura(self):
        color_acento = color_desde_hue((self.hue + 0.18) % 1.0, 0.7, 0.9)
        color_acento2 = color_desde_hue((self.hue - 0.14) % 1.0, 0.55, 0.85)
        color_luz = color_desde_hue(self.hue, 0.5, 1.0)
        capa = pygame.Surface(self.rect.size, pygame.SRCALPHA)

        for fx, fy, fr, delta_hue, alpha, clara in self.manchas:
            radio = max(2, int(fr * self.rect.width))
            centro = (int(fx * self.rect.width), int(fy * self.rect.height))
            color = color_luz if clara else color_acento
            pygame.draw.circle(capa, (*color, alpha), centro, radio)

        if len(self.trazo) >= 2:
            puntos_trazo = [
                (p[0] * self.rect.width, p[1] * self.rect.height) for p in self.trazo
            ]
            try:
                pygame.draw.aalines(capa, (*color_acento2, 160), False, puntos_trazo, 1)
            except TypeError:
                pygame.draw.lines(capa, (*color_acento2, 160), False, puntos_trazo, 2)

        for fx, fy, radio in self.salpicaduras:
            centro = (int(fx * self.rect.width), int(fy * self.rect.height))
            pygame.draw.circle(capa, (*color_luz, 150), centro, max(1, int(radio)))

        self._capa_textura = capa

    def activar_trampa(self):
        """Abre la trampa y comienza a hundir al personaje."""
        if self.es_trampa:
            self.trampa_activada = True

    def notificar_aterrizaje(self, intensidad=1.0):
        """Debe llamarse desde el código de colisiones del jugador cuando
        aterriza sobre esta plataforma desde arriba (por ejemplo, al
        detectar contacto con velocidad vertical positiva). Dispara un
        remezón elástico tipo "squash & stretch" y una salpicadura de
        partículas de pintura a modo de impacto.

        ``intensidad`` puede usarse para que caídas más fuertes generen
        un remezón más grande (por ejemplo, pasando la velocidad de caída
        normalizada). Esto es puramente cosmético: no modifica
        ``self.rect``, así que no afecta la física del juego.
        """
        intensidad = max(0.2, min(2.2, intensidad))
        self._squash_velocidad -= 16.0 * intensidad
        self._generar_particulas_impacto(intensidad)

    def _generar_particulas_impacto(self, intensidad):
        color_a = color_desde_hue((self.hue + 0.18) % 1.0, 0.75, 0.95)
        color_b = color_desde_hue(self.hue, 0.6, 1.0)
        cantidad = int(5 + 4 * intensidad)
        for _ in range(cantidad):
            angulo = random.uniform(math.pi * 0.15, math.pi * 0.85)
            velocidad = random.uniform(40, 110) * intensidad
            vida = random.uniform(0.35, 0.7)
            self._particulas.append(
                {
                    "x": self.rect.centerx + random.uniform(-self.rect.width * 0.3, self.rect.width * 0.3),
                    "y": self.rect.top,
                    "vx": math.cos(angulo) * velocidad * random.choice((-1, 1)),
                    "vy": -math.sin(angulo) * velocidad,
                    "vida": vida,
                    "vida_total": vida,
                    "color": random.choice((color_a, color_b)),
                    "radio": random.uniform(1.5, 3.5),
                }
            )

    def _actualizar_particulas(self, dt):
        if not self._particulas:
            return
        vivas = []
        for p in self._particulas:
            p["vida"] -= dt
            if p["vida"] <= 0:
                continue
            p["vx"] *= 0.98
            p["vy"] += self.GRAVEDAD_PARTICULAS * dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            vivas.append(p)
        self._particulas = vivas

    def actualizar(self):
        """Avanza, cuadro a cuadro, todas las animaciones de la plataforma:
        el progreso de la trampa, el deslizamiento de las plataformas
        móviles, el resorte de aterrizaje (squash/wobble) y las partículas
        de impacto."""
        dt = 1 / 60

        if self.trampa_activada:
            self.progreso_trampa = min(1.0, self.progreso_trampa + 0.045)

        if self.patron_movimiento:
            self._reloj_movimiento += dt
            angulo = self._reloj_movimiento * self.velocidad_movimiento + self._fase_movimiento
            offset = math.sin(angulo) * self.amplitud_movimiento
            anterior = pygame.Vector2(self.rect.x, self.rect.y)
            if self.patron_movimiento == "horizontal":
                self.rect.x = round(self._origen.x + offset)
            else:
                self.rect.y = round(self._origen.y + offset)
            self.desplazamiento_reciente = pygame.Vector2(self.rect.x, self.rect.y) - anterior
        else:
            self.desplazamiento_reciente = pygame.Vector2(0, 0)

        # Resorte crítico-amortiguado simple: hace que el squash vuelva a
        # cero con un ligero rebote elástico, como pintura fresca.
        rigidez, amortiguacion = 120.0, 12.0
        aceleracion = -rigidez * self._squash - amortiguacion * self._squash_velocidad
        self._squash_velocidad += aceleracion * dt
        self._squash += self._squash_velocidad * dt
        if abs(self._squash) < 0.002 and abs(self._squash_velocidad) < 0.01:
            self._squash = 0.0
            self._squash_velocidad = 0.0

        self._actualizar_particulas(dt)

    # ------------------------------------------------------------------
    # Dibujado
    # ------------------------------------------------------------------
    def dibujar(self, superficie, tiempo, nivel):
        """Dibuja la plataforma con una forma abstracta, más pictórica y
        expresiva, inspirada en composiciones de arte contemporáneo."""
        hue = (self.hue + math.sin(tiempo * 0.6 + self.fase) * 0.05 + nivel * 0.03) % 1.0
        color_base = color_desde_hue(hue, 0.68, 0.96)
        color_sombra = color_desde_hue(hue, 0.75, 0.52)
        color_media = color_desde_hue(hue, 0.7, 0.75)
        color_luz = color_desde_hue(hue, 0.5, 1.0)
        color_acento = color_desde_hue((hue + 0.18) % 1.0, 0.7, 0.9)
        color_acento2 = color_desde_hue((hue - 0.14) % 1.0, 0.55, 0.85)

        vibracion = 0
        if self.es_trampa and not self.trampa_activada:
            vibracion = int(math.sin(tiempo * 26 + self.fase) * 3)

        rect_base = self.rect.move(vibracion, 0)
        rect = self._rect_con_squash(rect_base)

        if self.patron_movimiento:
            self._dibujar_rastro_movimiento(superficie, rect)

        color_halo = self.COLOR_PELIGRO if (self.es_trampa and self.trampa_activada) else color_base
        self._dibujar_halo(superficie, rect, color_halo, tiempo)
        self._dibujar_sombra_contacto(superficie, rect)

        # Forma base abstracta: bloque irregular con perfiles orgánicos.
        puntos = self._puntos_plataforma(rect)
        pygame.draw.polygon(superficie, (0, 0, 0), puntos, 4)
        pygame.draw.polygon(superficie, color_sombra, puntos)
        pygame.draw.polygon(superficie, color_media, [(p[0] + 3, p[1] + 2) for p in puntos])
        pygame.draw.polygon(superficie, color_base, [(p[0] + 6, p[1] + 4) for p in puntos])
        # Segunda línea de contorno más fina, a modo de veta de pintura seca.
        pygame.draw.polygon(superficie, color_sombra, puntos, 1)

        # Capa superior luminosa, como una franja de pintura de alta energía.
        puntos_luz = [(p[0] + 8, p[1] + 5) for p in puntos[:4]]
        puntos_luz[0] = (puntos_luz[0][0] + 12, puntos_luz[0][1] + 4)
        puntos_luz[1] = (puntos_luz[1][0] - 16, puntos_luz[1][1] + 3)
        pygame.draw.polygon(superficie, color_luz, puntos_luz)
        pygame.draw.polygon(superficie, (0, 0, 0), puntos_luz, 2)

        # Textura pictórica: manchas, trazo curvo y salpicaduras (precalculadas).
        self._dibujar_textura_pictorica(superficie, rect)

        # Elementos abstractos dentro de la forma: curvas y bloques cromáticos.
        self._dibujar_acento_abstracto(superficie, rect, color_acento, color_sombra, color_luz)

        if self.es_trampa:
            self._dibujar_trampa(superficie, rect, tiempo, color_base)

        # Partículas de impacto por encima de todo, en coordenadas de mundo.
        self._dibujar_particulas(superficie)

    def _rect_con_squash(self, rect):
        """Aplica el resorte de aterrizaje (squash/wobble) como una
        transformación puramente visual: comprime/estira el rectángulo de
        dibujo anclado a su base, con un leve bamboleo lateral. No toca
        ``self.rect``, así que la física de colisión no se ve afectada."""
        if self._squash == 0.0 and self._squash_velocidad == 0.0:
            return rect
        escala_y = max(0.55, 1.0 + self._squash)
        escala_x = max(0.75, 1.0 - self._squash * 0.55)
        ancho = max(4, int(rect.width * escala_x))
        alto = max(4, int(rect.height * escala_y))
        rect_visual = pygame.Rect(0, 0, ancho, alto)
        rect_visual.midbottom = rect.midbottom
        rect_visual.x += int(self._squash_velocidad * 0.12)
        return rect_visual

    def _dibujar_rastro_movimiento(self, superficie, rect):
        """Guía punteada sutil detrás de una plataforma móvil, para que el
        jugador pueda anticipar su recorrido en vez de sorprenderse."""
        color = color_desde_hue(self.hue, 0.35, 0.95)
        amplitud = max(4, int(self.amplitud_movimiento))
        paso = 9
        if self.patron_movimiento == "horizontal":
            ancho, alto = amplitud * 2 + 10, 8
            capa = pygame.Surface((ancho, alto), pygame.SRCALPHA)
            y = alto // 2
            for x in range(4, ancho - 4, paso):
                pygame.draw.circle(capa, (*color, 85), (x, y), 2)
            superficie.blit(capa, (rect.centerx - ancho // 2, rect.centery - alto // 2))
        else:
            ancho, alto = 8, amplitud * 2 + 10
            capa = pygame.Surface((ancho, alto), pygame.SRCALPHA)
            x = ancho // 2
            for y in range(4, alto - 4, paso):
                pygame.draw.circle(capa, (*color, 85), (x, y), 2)
            superficie.blit(capa, (rect.centerx - ancho // 2, rect.centery - alto // 2))

    def _dibujar_particulas(self, superficie):
        for p in self._particulas:
            proporcion = max(0.0, p["vida"] / p["vida_total"])
            alpha = int(255 * proporcion)
            if alpha <= 0:
                continue
            radio = max(1.0, p["radio"] * proporcion)
            tam = int(radio * 2 + 2)
            capa = pygame.Surface((tam, tam), pygame.SRCALPHA)
            pygame.draw.circle(capa, (*p["color"], alpha), (tam / 2, tam / 2), radio)
            superficie.blit(capa, (p["x"] - tam / 2, p["y"] - tam / 2))

    def _puntos_plataforma(self, rect):
        """Genera un perfil irregular que parece una pieza orgánica, casi
        escultórica, en lugar de un bloque rígido."""
        margen_x = rect.width * 0.08
        margen_y = rect.height * 0.25
        return [
            (rect.left + margen_x, rect.top + 7),
            (rect.right - margen_x * 0.9, rect.top + 2),
            (rect.right - 6, rect.top + 10),
            (rect.right - 4, rect.bottom - 6),
            (rect.left + 8, rect.bottom - 2),
            (rect.left + 2, rect.top + 16),
        ]

    def _dibujar_textura_pictorica(self, superficie, rect):
        """Pinta la textura pictórica precalculada (ver ``_construir_capa_textura``).

        Normalmente solo hace un blit barato (nada se reconstruye por
        fotograma). Si el rectángulo de dibujo cambió de tamaño por el
        squash de aterrizaje, la textura se reescala sobre la marcha
        (solo ocurre durante el breve remezón, no en reposo).
        """
        if self._capa_textura is None:
            self._construir_capa_textura()
        if rect.size == self._capa_textura.get_size():
            superficie.blit(self._capa_textura, rect.topleft)
        else:
            textura = pygame.transform.smoothscale(self._capa_textura, rect.size)
            superficie.blit(textura, rect.topleft)

    def _dibujar_acento_abstracto(self, superficie, rect, color_acento, color_sombra, color_luz):
        """Añade manchas y líneas abstractas que simulan pintura gestual sobre
        la plataforma."""
        r1 = pygame.Rect(rect.left + 20, rect.top + 9, rect.width * 0.23, max(4, rect.height * 0.38))
        pygame.draw.rect(superficie, color_sombra, r1, border_radius=8)
        pygame.draw.rect(superficie, (0, 0, 0), r1, 2, border_radius=8)

        r2 = pygame.Rect(rect.left + rect.width * 0.54, rect.top + 4, rect.width * 0.18, max(6, rect.height * 0.52))
        pygame.draw.rect(superficie, color_luz, r2, border_radius=8)
        pygame.draw.rect(superficie, (0, 0, 0), r2, 2, border_radius=8)

        linea_1 = pygame.Rect(rect.left + 16, rect.centery - 3, rect.width * 0.74, 3)
        pygame.draw.rect(superficie, (*color_acento, 180), linea_1, border_radius=3)
        pygame.draw.rect(superficie, (0, 0, 0), linea_1, 1, border_radius=3)

        tri = [
            (rect.right - 26, rect.top + 12),
            (rect.right - 6, rect.top + 20),
            (rect.right - 20, rect.bottom - 10),
        ]
        pygame.draw.polygon(superficie, color_sombra, tri)
        pygame.draw.polygon(superficie, (0, 0, 0), tri, 2)

        # Pequeño acento circular extra, como un botón de color puro.
        centro_acento = (rect.left + int(rect.width * 0.08), rect.top + int(rect.height * 0.55))
        radio_acento = max(3, int(rect.height * 0.22))
        pygame.draw.circle(superficie, color_luz, centro_acento, radio_acento)
        pygame.draw.circle(superficie, (0, 0, 0), centro_acento, radio_acento, 1)

    def _dibujar_halo(self, superficie, rect, color, tiempo):
        """Aura translúcida detrás de la plataforma, en dos capas para dar
        profundidad; se tiñe de rojo y pulsa cuando la trampa ya está
        activa."""
        radio = rect.height * 1.4
        capa = pygame.Surface((radio * 2, radio * 2), pygame.SRCALPHA)
        pygame.draw.circle(capa, (*color, 30), (radio, radio), radio)
        pygame.draw.circle(capa, (*color, 55), (radio, radio), radio * 0.62)
        superficie.blit(capa, (rect.centerx - radio, rect.top - radio * 0.6))

        if self.es_trampa and self.trampa_activada:
            pulso = 0.5 + 0.5 * math.sin(tiempo * 8)
            radio_anillo = rect.height * (1.1 + 0.4 * pulso)
            capa_anillo = pygame.Surface((radio_anillo * 2, radio_anillo * 2), pygame.SRCALPHA)
            pygame.draw.circle(
                capa_anillo,
                (*self.COLOR_PELIGRO, int(90 * (1 - pulso))),
                (radio_anillo, radio_anillo),
                radio_anillo,
                3,
            )
            superficie.blit(
                capa_anillo, (rect.centerx - radio_anillo, rect.centery - radio_anillo)
            )

    def _dibujar_sombra_contacto(self, superficie, rect):
        """Sombra elíptica y suave proyectada justo debajo de la plataforma,
        que ancla visualmente la pieza al resto de la escena."""
        alto = max(4, int(rect.height * 0.35))
        ancho = int(rect.width * 0.92)
        if ancho <= 0:
            return
        sombra = pygame.Surface((ancho, alto), pygame.SRCALPHA)
        pygame.draw.ellipse(sombra, (10, 6, 18, 70), sombra.get_rect())
        superficie.blit(sombra, (rect.centerx - ancho // 2, rect.bottom - alto // 3))

    def _dibujar_trampa(self, superficie, rect, tiempo, color_base):
        """Antes de activarse: rayas de peligro que laten, un par de ojos
        vigilantes y una boca apenas entreabierta con dientes, como
        advertencia. Después de activarse: el agujero crece y se oscurece
        progresivamente (progreso_trampa), aparecen grietas en la superficie
        y gotas viscosas caen del borde, mientras los dientes rodean todo el
        borde."""
        abertura = rect.inflate(-12, -5)

        if not self.trampa_activada:
            pulso = 0.5 + 0.5 * math.sin(tiempo * 6 + self.fase)
            color_raya = _mezclar(color_base, self.COLOR_PELIGRO, 0.3 + 0.3 * pulso)
            self._dibujar_rayas_peligro(superficie, rect, color_raya)

            boca_cerrada = abertura.inflate(-abertura.width * 0.5, -abertura.height * 0.3)
            pygame.draw.ellipse(superficie, self.COLOR_HUECO, boca_cerrada)
            pygame.draw.ellipse(superficie, (0, 0, 0), boca_cerrada, 2)
            self._dibujar_dientes(superficie, boca_cerrada, color_base, largo=5)
            self._dibujar_ojos(superficie, rect, tiempo, pulso)
        else:
            progreso = self.progreso_trampa
            hueco = abertura.inflate(
                -abertura.width * (1 - progreso) * 0.6,
                -abertura.height * (1 - progreso) * 0.3,
            )
            color_hueco = _mezclar(self.COLOR_HUECO, self.COLOR_HUECO_PROFUNDO, progreso)
            self._dibujar_grietas(superficie, rect, hueco, progreso)
            pygame.draw.ellipse(superficie, color_hueco, hueco)
            pygame.draw.ellipse(
                superficie, self.COLOR_PELIGRO, hueco, max(1, int(2 * (1 - progreso * 0.5)))
            )
            self._dibujar_dientes(superficie, hueco, color_base, largo=4 + 5 * progreso)
            self._dibujar_goteo(superficie, hueco, tiempo, progreso)

    def _dibujar_rayas_peligro(self, superficie, rect, color_raya):
        """Rayas diagonales tipo cinta de peligro, recortadas a la forma
        redondeada de la plataforma."""
        capa = pygame.Surface(rect.size, pygame.SRCALPHA)
        paso = 10
        for offset in range(-rect.height, rect.width, paso):
            pygame.draw.line(
                capa,
                (*color_raya, 140),
                (offset, rect.height),
                (offset + rect.height, 0),
                4,
            )
        mascara = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(mascara, (255, 255, 255, 255), mascara.get_rect(), border_radius=10)
        capa.blit(mascara, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        superficie.blit(capa, rect.topleft)

    def _dibujar_ojos(self, superficie, rect, tiempo, pulso):
        """Un par de ojos vigilantes justo sobre la boca cerrada, que
        parpadean lentamente; refuerzan la sensación de que la trampa está
        "despierta" antes de morder."""
        parpadeo = math.sin(tiempo * 1.3 + self.fase)
        alto_ojo = 3 if parpadeo > 0.85 else 5
        separacion = rect.width * 0.16
        centro_y = rect.top + rect.height * 0.28
        for lado in (-1, 1):
            centro = (rect.centerx + lado * separacion, centro_y)
            pygame.draw.ellipse(
                superficie,
                (250, 240, 235),
                pygame.Rect(0, 0, 9, alto_ojo).move(centro[0] - 4, centro[1] - alto_ojo / 2),
            )
            color_pupila = _mezclar((40, 20, 20), self.COLOR_PELIGRO, 0.3 + 0.4 * pulso)
            pygame.draw.circle(superficie, color_pupila, (int(centro[0]), int(centro[1])), 2)

    def _dibujar_grietas(self, superficie, rect, hueco, progreso):
        """Líneas de fractura que se extienden desde el borde del agujero
        hacia el resto de la plataforma a medida que la trampa avanza."""
        if not self.grietas:
            return
        largo = max(rect.width, rect.height) * 0.55 * progreso
        for angulo in self.grietas:
            origen = (
                hueco.centerx + math.cos(angulo) * (hueco.width / 2),
                hueco.centery + math.sin(angulo) * (hueco.height / 2),
            )
            quiebre = (
                origen[0] + math.cos(angulo + 0.3) * largo * 0.5,
                origen[1] + math.sin(angulo + 0.3) * largo * 0.5,
            )
            fin = (
                hueco.centerx + math.cos(angulo) * (hueco.width / 2 + largo),
                hueco.centery + math.sin(angulo) * (hueco.height / 2 + largo),
            )
            pygame.draw.lines(
                superficie, (25, 12, 12), False, [origen, quiebre, fin], 2
            )

    def _dibujar_goteo(self, superficie, hueco, tiempo, progreso):
        """Gotas viscosas que cuelgan del borde inferior del agujero y se
        alargan a medida que crece la trampa."""
        for fx, largo_base, fase in self.goteo:
            x = hueco.left + fx * hueco.width
            balanceo = math.sin(tiempo * 3 + fase) * 2
            largo = (6 + largo_base * 10) * progreso
            y0 = hueco.centery + hueco.height * 0.25
            y1 = y0 + largo
            pygame.draw.line(
                superficie, self.COLOR_HUECO_PROFUNDO, (x, y0), (x + balanceo, y1), 3
            )
            pygame.draw.circle(
                superficie, self.COLOR_HUECO_PROFUNDO, (int(x + balanceo), int(y1)), 3
            )

    def _dibujar_dientes(self, superficie, abertura, color_base, largo=5, cantidad=12):
        """Dientes triangulares distribuidos en torno a todo el perímetro
        de la abertura, con una base sombreada y una punta iluminada para
        dar sensación de volumen."""
        radio_x = abertura.width / 2
        radio_y = abertura.height / 2
        if radio_x <= 0 or radio_y <= 0:
            return
        color_sombra_diente = _mezclar(color_base, (0, 0, 0), 0.45)
        color_luz_diente = _mezclar(color_base, (255, 255, 255), 0.35)
        for i in range(cantidad):
            angulo = math.tau * i / cantidad
            coseno, seno = math.cos(angulo), math.sin(angulo)
            base_x = abertura.centerx + coseno * radio_x
            base_y = abertura.centery + seno * radio_y
            punta = (
                abertura.centerx + coseno * (radio_x + largo),
                abertura.centery + seno * (radio_y + largo),
            )
            medio = (
                abertura.centerx + coseno * (radio_x + largo * 0.5),
                abertura.centery + seno * (radio_y + largo * 0.5),
            )
            perp = pygame.Vector2(-seno, coseno) * 2.6
            p1 = (base_x + perp.x, base_y + perp.y)
            p2 = (base_x - perp.x, base_y - perp.y)
            pygame.draw.polygon(superficie, color_sombra_diente, [p1, p2, punta])
            perp_chica = pygame.Vector2(-seno, coseno) * 1.1
            pygame.draw.polygon(
                superficie,
                color_luz_diente,
                [
                    (medio[0] + perp_chica.x, medio[1] + perp_chica.y),
                    (medio[0] - perp_chica.x, medio[1] - perp_chica.y),
                    punta,
                ],
            )