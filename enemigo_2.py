"""Copia del jugador, en negativo y desesperada, que lo persigue.

Es el mismo personaje (mismo esqueleto, gráficos y física), pero con la
paleta invertida y una expresión de puro terror, más exagerada que la
desesperación del jugador: ojos desorbitados e inclinados de angustia con
pupilas diminutas que vigilan a su alrededor, boca que tiembla o grita al
correr, pelo erizado, gotas de sudor frío y rayitas de temblor.
Corre encogido, tiembla de pies a cabeza y de vez en cuando el negativo
parpadea, como un fallo de imagen.
"""

import colorsys
import math
import random
from array import array

import pygame

from constantes import HEIGHT
from personaje import PersonajeHumanoide


_CACHE_SONIDOS_AMENAZANTES = {}


def _crear_sonidos_amenazantes():
    """Genera un zumbido grave y un rugido breve según el formato del mixer."""
    formato = pygame.mixer.get_init()
    if not formato or formato[1] != -16:
        return None, None
    if formato in _CACHE_SONIDOS_AMENAZANTES:
        return _CACHE_SONIDOS_AMENAZANTES[formato]

    frecuencia_muestreo, _, canales = formato
    zumbido = array("h")
    cantidad = frecuencia_muestreo * 2
    for indice in range(cantidad):
        tiempo = indice / frecuencia_muestreo
        modulacion = 0.72 + 0.13 * math.cos(math.tau * 0.5 * tiempo)
        onda = (
            0.58 * math.sin(math.tau * 54 * tiempo)
            + 0.27 * math.sin(math.tau * 57 * tiempo)
            + 0.15 * math.sin(math.tau * 108 * tiempo)
        )
        muestra = round(5000 * modulacion * onda)
        zumbido.extend([muestra] * canales)

    rugido = array("h")
    generador = random.Random(217)
    fase = 0.0
    ruido_filtrado = 0.0
    cantidad = round(frecuencia_muestreo * 0.9)
    for indice in range(cantidad):
        progreso = indice / cantidad
        envolvente = math.sin(math.pi * progreso) ** 0.8
        frecuencia = 92 - 48 * progreso
        fase += math.tau * frecuencia / frecuencia_muestreo
        ruido_filtrado = ruido_filtrado * 0.92 + generador.uniform(-1, 1) * 0.08
        onda = (
            0.65 * math.sin(fase)
            + 0.22 * math.sin(fase * 2.03)
            + 0.18 * ruido_filtrado
        )
        muestra = round(13500 * envolvente * onda)
        rugido.extend([muestra] * canales)

    sonidos = (
        pygame.mixer.Sound(buffer=zumbido.tobytes()),
        pygame.mixer.Sound(buffer=rugido.tobytes()),
    )
    _CACHE_SONIDOS_AMENAZANTES[formato] = sonidos
    return sonidos


class _EstadoTeclas:
    def __init__(self, pulsadas):
        self.pulsadas = pulsadas

    def __getitem__(self, tecla):
        return tecla in self.pulsadas


class _ClonNegativo(PersonajeHumanoide):
    """El personaje con la paleta en negativo y cara de terror.

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
        self._estela_ecos = []
        self._contador_estela = 0
        self._progreso_reaparicion = 1.0
        self._trepamiento_progreso = 1.0
        self._fase_trepamiento = 0.0

    # ------------------------------------------------------------------
    # Negativo: se invierte cada color de la paleta ya sombreada, así que
    # lo oscuro (contornos, ojos) pasa a claro y lo claro (cara) a oscuro.
    # ------------------------------------------------------------------
    def _tono(self, factor):
        base = super()._tono(factor)
        if self._negativo:
            return (255 - base[0], 255 - base[1], 255 - base[2])
        return base

    # ------------------------------------------------------------------
    # Rostro y pelo aterrados
    # ------------------------------------------------------------------
    # La cabeza mide 6x6 "píxeles" (24x24). Todo el rostro se coloca en esa
    # rejilla (columna 0-5, fila 0-5) para que encaje con el estilo del
    # jugador. Es el mismo personaje, pero con el miedo muy marcado.
    ESCLERA = (248, 246, 240)       # ojos siempre blancos, incluso en negativo
    COLOR_SUDOR = (175, 222, 255)

    def _dibujar_cara(self, superficie, centro_x, cabeza_y, lado_cabeza, color_trazo, color_ojo):
        p = self.pixel
        if round(lado_cabeza / p) != 6:
            # Cabeza de otro tamaño: se conserva la cara base del jugador
            # (con el blanco del ojo invertido, como antes).
            if self._negativo:
                color_ojo = (255 - color_ojo[0], 255 - color_ojo[1], 255 - color_ojo[2])
            super()._dibujar_cara(superficie, centro_x, cabeza_y, lado_cabeza, color_trazo, color_ojo)
            return

        izq = self._celda(centro_x - lado_cabeza // 2)
        arriba = self._celda(cabeza_y)
        ticks = pygame.time.get_ticks()
        paso = ticks // 70
        tinta = super()._tono(0.16)  # tinta oscura real: no se invierte

        def celda(col, fila, color, ancho=1, alto=1):
            pygame.draw.rect(
                superficie, color,
                (izq + col * p, arriba + fila * p, ancho * p, alto * p),
            )

        # --- Ojos desorbitados: 2x3 bloques (el jugador los lleva de 2x2) con
        # la esquina superior externa recortada, de modo que se inclinan
        # hacia dentro: la mirada de quien suplica. Blancos incluso en el
        # negativo para que se vean saltones sobre la cara oscura. ---
        ojo_izq = ((1, 1), (0, 2), (1, 2), (0, 3), (1, 3))
        ojo_der = ((4, 1), (4, 2), (5, 2), (4, 3), (5, 3))
        for col, fila in ojo_izq + ojo_der:
            celda(col, fila, self.ESCLERA)

        # --- Pupilas diminutas: miran hacia donde corre y, de vez en cuando,
        # echan un vistazo atrás, como quien sabe que algo lo sigue. ---
        sentido = self._sentido()
        if (ticks // 350) % 4 == 3:
            sentido = -sentido
        if self.en_suelo:
            mirada_y = 0
        else:
            mirada_y = -1 if self.vel_y < -2 else (1 if self.vel_y > 2 else 0)
        for col_base in (0, 4):
            col = col_base + (1 if sentido > 0 else 0)
            fila = 2 + mirada_y
            if fila == 1 and col in (0, 5):  # esquina recortada del ojo
                fila = 2
            celda(col, fila, tinta)

        # --- Boca: al correr grita (abre y cierra); quieto, le tiembla ---
        corriendo = abs(self.vel_x) > 1.5 or not self.en_suelo
        if corriendo:
            celda(1, 4, color_trazo, 4, 1)
            if (paso // 2) % 2 == 0:
                celda(2, 5, color_trazo, 2, 1)
        elif (ticks // 90) % 2 == 0:
            for col, fila in ((1, 4), (3, 4), (2, 5), (4, 5)):
                celda(col, fila, color_trazo)
        else:
            for col, fila in ((2, 4), (4, 4), (1, 5), (3, 5)):
                celda(col, fila, color_trazo)

        # --- Sudor frío: una gota por sien, desfasadas ---
        for lado, desfase in ((-1, 0), (1, 450)):
            ciclo = (ticks + desfase) % 900
            if ciclo >= 650:
                continue
            progreso = ciclo / 650
            gota_x = izq - p if lado < 0 else izq + 6 * p
            gota_y = arriba + int(progreso * 5) * p
            alto_gota = p * 2 if progreso < 0.7 else p
            pygame.draw.rect(superficie, tinta, (gota_x - 1, gota_y - 1, p + 2, alto_gota + 2))
            pygame.draw.rect(superficie, self.COLOR_SUDOR, (gota_x, gota_y, p, alto_gota))

        # --- Rayitas de temblor a los lados de la cabeza ---
        cuadro = ticks // 80
        for lado in (-1, 1):
            for k in (0, 1):
                if (cuadro + k + (lado > 0)) % 3 == 0:
                    continue
                vibra = (cuadro + k) % 2
                col = -3 - vibra if lado < 0 else 8 + vibra
                celda(col, 1 + 2 * k, color_trazo, 1, 2)

    def _dibujar_pelo(self, superficie, centro_x, cabeza_y, color):
        """Pelo erizado de punta: más alto y revuelto que el del jugador,
        con los mechones vibrando."""
        p = self.pixel
        izq = self._celda(centro_x - 12)
        arriba = self._celda(cabeza_y)
        fase = pygame.time.get_ticks() // 70
        viento = -1 if self.vel_x > 2 else (1 if self.vel_x < -2 else 0)
        # Altura de cada una de las 6 columnas; 0 deja hueco entre mechones.
        for col, alto_base in enumerate((3, 0, 4, 1, 3, 2)):
            if alto_base == 0:
                continue
            alto = alto_base + (1 if (fase + col * 2) % 5 == 0 else 0)
            for nivel in range(alto):
                # Al correr, las puntas se echan hacia atrás.
                desvio = viento if nivel >= 2 else 0
                pygame.draw.rect(
                    superficie, color,
                    (izq + (col + desvio) * p, arriba - (nivel + 1) * p, p, p),
                )

    # ------------------------------------------------------------------
    # Lógica visual por fotograma
    # ------------------------------------------------------------------
    def mover(self, plataformas, controles=None, estado_teclas=None):
        super().mover(plataformas, controles, estado_teclas)

        estela_viva = []
        for imagen, ancla, vida in self._estela_ecos:
            vida -= 1
            if vida > 0:
                estela_viva.append((imagen, ancla, vida))
        self._estela_ecos = estela_viva

        # Postura encogida de miedo: muy encorvado al correr y, aun quieto,
        # con las rodillas flexionadas.
        caminando = abs(self.vel_x) > 0.4 and self.en_suelo
        self._encorvado = self._lerp(self._encorvado, 0.4 if caminando else 0.2, 0.2)

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
            self.pose_aire,
            self.amplitud_paso,
            self.tiempo_animacion,
            self.balanceo_actual,
        )
        sentido = self._sentido()
        try:
            for imagen, ancla, vida in self._estela_ecos:
                imagen.set_alpha(105 * vida // 7)
                superficie.blit(imagen, imagen.get_rect(center=ancla))

            # Se echa hacia delante, con la cabeza adelantada.
            self.inclinacion_actual += sentido * self.amplitud_paso * 3.0
            self.cabeza_retraso += sentido * self.amplitud_paso * 4
            self.agachado_animacion = max(self.agachado_animacion, self._encorvado)
            if self._trepamiento_progreso < 1.0:
                brace = math.sin(self._fase_trepamiento)
                self.inclinacion_actual += sentido * (6 + 2 * brace)
                self.cabeza_retraso += sentido * 5
                self.pose_aire = max(
                    self.pose_aire, 0.72 + 0.12 * math.sin(self._fase_trepamiento * 2)
                )
                self.amplitud_paso = max(self.amplitud_paso, 0.55)
                self.tiempo_animacion = self._fase_trepamiento
            # Tiritona: los brazos (y algo las piernas) se sacuden en
            # contrafase unas 9 veces por segundo.
            temblor = 3 if self.amplitud_paso < 0.3 else 2
            self.balanceo_actual += temblor if (pygame.time.get_ticks() // 55) % 2 else -temblor
            self.rect.x += self._glitch_dx
            clip_original = superficie.get_clip()
            if self._progreso_reaparicion < 1.0:
                alto_visible = round(
                    self.rect.height * self._progreso_reaparicion
                )
                zona_visible = pygame.Rect(
                    self.rect.centerx - 70,
                    self.rect.bottom - alto_visible,
                    140,
                    max(1, alto_visible),
                )
                superficie.set_clip(clip_original.clip(zona_visible))
            try:
                super().dibujar(superficie)
            finally:
                superficie.set_clip(clip_original)
            if abs(self.vel_x) > 1.5 or abs(self.vel_y) > 3.0:
                self._contador_estela += 1
                if self._contador_estela >= 3 and self._lienzo is not None:
                    self._contador_estela = 0
                    silueta = pygame.mask.from_surface(self._lienzo).to_surface(
                        setcolor=(*self._tono(1.45), 255),
                        unsetcolor=(0, 0, 0, 0),
                    )
                    self._estela_ecos.append(
                        (silueta, (self.rect.centerx, self.rect.bottom - 60), 7)
                    )
                    if len(self._estela_ecos) > 4:
                        self._estela_ecos.pop(0)
            else:
                self._contador_estela = 0
        finally:
            (
                self.inclinacion_actual,
                self.cabeza_retraso,
                self.agachado_animacion,
                self.rect.x,
                self.pose_aire,
                self.amplitud_paso,
                self.tiempo_animacion,
                self.balanceo_actual,
            ) = guardado


class PerseguidorSepia:
    """Clon que persigue al jugador, deja ecos al moverse y reaparece al caer."""

    DURACION_REAPARICION = 24
    DURACION_AGARRE = 180
    DURACION_TREPAMIENTO = 42

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
        self.volumen_efectos = 0.0
        self._sonido_ambiente, self._sonido_rugido = _crear_sonidos_amenazantes()
        self._canal_ambiente = None
        self._canal_rugido = None
        self._proximo_rugido = pygame.time.get_ticks() + random.randint(2500, 5000)
        self.personaje.dash_habilitado = False
        self.activa = True
        self._manteniendo_salto = False
        self._destino_salto = None
        self._posicion_inicial = self.personaje.rect.topleft
        self._plataforma_inicial = None
        self._reaparicion_frames = 0
        self._capa_reaparicion = pygame.Surface((160, 180), pygame.SRCALPHA)
        self._jugador_agarrado = None
        self._frames_agarre = 0
        self._frames_trepamiento = 0
        self._desfase_inicio_x = 0
        self._desfase_inicio_pies = 0
        self._fase_trepamiento = 0.0
        self._agarre_modo_infinito = False
        self.agarre_expirado = False
        self.powerup_otorgado = False

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
        self.ajustar_volumen_efectos(
            getattr(jugador, "volumen_efectos", self.volumen_efectos)
        )
        factor_persecucion = (
            0.82 if getattr(jugador, "potenciador_infinito", False) else 1.0
        )
        clon.velocidad = jugador.velocidad * factor_persecucion
        clon.gravedad = jugador.gravedad
        clon.fuerza_salto = jugador.fuerza_salto
        clon.acel_suelo = jugador.acel_suelo * factor_persecucion
        clon.friccion_suelo = jugador.friccion_suelo
        clon.acel_aire = jugador.acel_aire * factor_persecucion
        clon.acel_aire_doble_salto = (
            jugador.acel_aire_doble_salto * factor_persecucion
        )
        clon.friccion_aire = jugador.friccion_aire
        clon.factor_giro = jugador.factor_giro

        # Mismo color que el jugador: el negativo se aplica al dibujar.
        color = getattr(jugador, "color", None)
        if color is not None and tuple(color[:3]) != tuple(clon.color[:3]):
            clon.color = tuple(color[:3])
            clon._halo_personaje = None
            clon._silueta_color = None

    def ajustar_volumen_efectos(self, volumen):
        """Respeta el control general de efectos de sonido."""
        self.volumen_efectos = max(0.0, min(1.0, float(volumen)))
        if self.volumen_efectos == 0:
            self.detener_audio()

    def detener_audio(self):
        """Detiene los sonidos propios al cambiar de nivel o acabar la partida."""
        for canal in (self._canal_ambiente, self._canal_rugido):
            if canal is not None:
                canal.stop()
        self._canal_ambiente = None
        self._canal_rugido = None

    def _actualizar_audio(self, objetivo):
        if self._sonido_ambiente is None or self.volumen_efectos <= 0:
            return

        distancia = math.hypot(
            self.rect.centerx - objetivo.centerx,
            self.rect.centery - objetivo.centery,
        )
        proximidad = max(0.0, 1.0 - distancia / 520)
        if proximidad <= 0:
            if self._canal_ambiente is not None:
                self._canal_ambiente.stop()
                self._canal_ambiente = None
            return

        if self._canal_ambiente is None or not self._canal_ambiente.get_busy():
            self._canal_ambiente = self._sonido_ambiente.play(loops=-1)
        intensidad = proximidad ** 1.5
        self._canal_ambiente.set_volume(0.32 * self.volumen_efectos * intensidad)

        ahora = pygame.time.get_ticks()
        if (
            distancia < 360
            and ahora >= self._proximo_rugido
            and self._sonido_rugido is not None
            and (self._canal_rugido is None or not self._canal_rugido.get_busy())
        ):
            self._sonido_rugido.set_volume(
                0.5 * self.volumen_efectos * intensidad
            )
            self._canal_rugido = self._sonido_rugido.play()
            self._proximo_rugido = ahora + random.randint(4500, 8000)

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
        self._actualizar_audio(objetivo)

        if self._jugador_agarrado is not None:
            jugador = self._jugador_agarrado
            clon = self.personaje
            clon.vel_x = 0.0
            clon.vel_y = 0
            clon.en_suelo = True
            if self._frames_trepamiento > 0:
                self._frames_trepamiento -= 1
                progreso = 1 - self._frames_trepamiento / self.DURACION_TREPAMIENTO
                suave = progreso * progreso * (3 - 2 * progreso)
                inicio_x = jugador.rect.centerx + self._desfase_inicio_x
                final_x = jugador.rect.centerx - jugador.direccion * 5
                inicio_pies = jugador.rect.bottom + self._desfase_inicio_pies
                final_pies = jugador.rect.top + 16
                vaiven = math.sin(self._fase_trepamiento) * 3 * (1 - suave)
                clon.rect.centerx = round(inicio_x + (final_x - inicio_x) * suave + vaiven)
                clon.rect.bottom = round(
                    inicio_pies + (final_pies - inicio_pies) * suave
                )
                clon._trepamiento_progreso = progreso
                self._fase_trepamiento += 0.32
                clon._fase_trepamiento = self._fase_trepamiento
            else:
                clon.rect.centerx = jugador.rect.centerx - jugador.direccion * 5
                clon.rect.bottom = jugador.rect.top + 16 + round(
                    math.sin(self._frames_agarre * 0.22) * 2
                )
            if self._frames_trepamiento == 0 and self._agarre_modo_infinito:
                jugador.activar_potenciador_infinito()
                self.powerup_otorgado = True
                self.soltar_jugador()
                self.activa = False
                return
            self._frames_agarre -= 1
            if self._frames_agarre <= 0:
                self.agarre_expirado = True
            return

        if self._reaparicion_frames > 0:
            self._reaparicion_frames -= 1
            clon = self.personaje
            clon._progreso_reaparicion = (
                1 - self._reaparicion_frames / self.DURACION_REAPARICION
            )
            teclas_vacias = _EstadoTeclas(set())
            clon.mover(plataformas, self.CONTROLES, estado_teclas=teclas_vacias)
            if self._reaparicion_frames == 0:
                clon._progreso_reaparicion = 1.0
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
            clon._emitir_particulas(
                7, clon.rect.centerx, clon.rect.bottom - 8, dispersion=10
            )
            clon.rect.topleft = self._posicion_inicial
            clon.reiniciar_movimiento()
            clon.plataforma_actual = self._plataforma_inicial
            clon.en_suelo = True
            clon._emitir_particulas(
                12, clon.rect.centerx, clon.rect.bottom - 20, dispersion=18
            )
            self._manteniendo_salto = False
            self._destino_salto = None
            self._reaparicion_frames = self.DURACION_REAPARICION
            clon._progreso_reaparicion = 0.0

    def nivel_alerta(self):
        return 1.0 if self._jugador_agarrado is not None else 0.0

    def agarrar_jugador(self, jugador, modo_infinito=False):
        if (
            not self.activa
            or self._reaparicion_frames > 0
            or jugador.dash_restante > 0
        ):
            return False
        if self._jugador_agarrado is jugador:
            return True
        if self._jugador_agarrado is not None:
            return False

        self._jugador_agarrado = jugador
        self._frames_agarre = self.DURACION_AGARRE
        self._frames_trepamiento = self.DURACION_TREPAMIENTO
        self._desfase_inicio_x = self.rect.centerx - jugador.rect.centerx
        self._desfase_inicio_pies = self.rect.bottom - jugador.rect.bottom
        self._fase_trepamiento = 0.0
        self._agarre_modo_infinito = modo_infinito
        self.agarre_expirado = False
        self.personaje._trepamiento_progreso = 0.0
        self.personaje._fase_trepamiento = 0.0
        jugador.pesado = not modo_infinito
        self.personaje.vel_x = 0.0
        self.personaje.vel_y = 0
        self._proximo_rugido = pygame.time.get_ticks()
        return True

    def soltar_jugador(self):
        if self._jugador_agarrado is not None:
            self._jugador_agarrado.pesado = False
        self._jugador_agarrado = None
        self._frames_agarre = 0
        self._frames_trepamiento = 0
        self.agarre_expirado = False
        self._agarre_modo_infinito = False
        self.personaje._trepamiento_progreso = 1.0
        self.detener_audio()

    def derrotar(self, direccion):
        if not self.activa:
            return False
        if self._jugador_agarrado is not None:
            return False
        self.activa = False
        self.detener_audio()
        return True

    def dibujar(self, superficie, tiempo):
        if self.activa:
            self.personaje.dibujar(superficie)
            if self._reaparicion_frames > 0:
                progreso = self.personaje._progreso_reaparicion
                capa = self._capa_reaparicion
                capa.fill((0, 0, 0, 0))
                centro = (80, 90)
                pulso = 0.5 + 0.5 * math.sin(tiempo * 22)
                intensidad = 0.55 + 0.45 * math.sin(math.pi * progreso)
                alfa = int(220 * intensidad * (1 - 0.3 * progreso))
                fase = tiempo * 5 + progreso * math.tau

                def color_espectral(desfase):
                    rgb = colorsys.hsv_to_rgb(
                        (tiempo * 0.3 + progreso * 0.7 + desfase) % 1,
                        0.88,
                        1.0,
                    )
                    return tuple(round(componente * 255) for componente in rgb)

                radio_base = 43 + round(8 * pulso)
                for indice in range(3):
                    color = color_espectral(indice / 3)
                    radio = radio_base + indice * 11
                    cuadro = pygame.Rect(
                        centro[0] - radio,
                        centro[1] - radio,
                        radio * 2,
                        radio * 2,
                    )
                    inicio = fase * (1.2 if indice % 2 == 0 else -0.9)
                    pygame.draw.arc(
                        capa,
                        (*color, alfa),
                        cuadro,
                        inicio,
                        inicio + math.pi * (1.0 + 0.25 * pulso),
                        2 + indice % 2,
                    )

                for brazo in range(3):
                    puntos = []
                    for paso in range(34):
                        fraccion = paso / 33
                        angulo = fase * (-1 if brazo % 2 else 1)
                        angulo += fraccion * math.tau * 1.4 + brazo * math.tau / 3
                        radio = 5 + fraccion * (49 + 5 * pulso)
                        puntos.append(
                            (
                                round(centro[0] + math.cos(angulo) * radio),
                                round(centro[1] + math.sin(angulo) * radio),
                            )
                        )
                    pygame.draw.lines(
                        capa,
                        (*color_espectral(brazo / 3 + 0.16), alfa),
                        False,
                        puntos,
                        2,
                    )

                for orbita in range(8):
                    angulo = fase * (1.5 if orbita % 2 else -1.2)
                    angulo += orbita * math.tau / 8
                    radio = 57 + 6 * math.sin(fase + orbita)
                    punto = (
                        round(centro[0] + math.cos(angulo) * radio),
                        round(centro[1] + math.sin(angulo) * radio),
                    )
                    color = color_espectral(orbita / 8)
                    tamano = 2 + orbita % 3
                    pygame.draw.rect(
                        capa,
                        (*color, alfa),
                        (punto[0] - tamano, punto[1] - tamano, tamano * 2, tamano * 2),
                    )

                if 0 < progreso < 1:
                    linea_y = centro[1] + 35 - round(
                        self.personaje.rect.height * progreso
                    )
                    color = color_espectral(progreso * 0.5)
                    pygame.draw.line(
                        capa, (*color, alfa), (26, linea_y), (134, linea_y), 2
                    )
                superficie.blit(
                    capa,
                    (self.rect.centerx - centro[0], self.rect.centery - centro[1]),
                )


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