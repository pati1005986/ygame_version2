import math
import random
from array import array

import pygame


class PersonajeHumanoide:
    """Personaje controlable con animación pixel-art y sonidos sintéticos.

    Args:
        x: Posición horizontal inicial del rectángulo de colisión.
        y: Posición vertical inicial del rectángulo de colisión.
        color: Color RGB base del personaje. Sus sombras se derivan de él.
        volumen_efectos: Volumen 0-1 de los efectos de sonido.
        dash_habilitado: Activa el dash aéreo/terrestre (desactivado por
            defecto para no alterar el diseño de niveles existente).

    Integración recomendada en el bucle de eventos::

        KEYDOWN espacio / W / UP   -> jugador.solicitar_salto()
        KEYUP   espacio / W / UP   -> jugador.soltar_salto()    # salto variable
        KEYDOWN shift (opcional)   -> jugador.solicitar_dash()

    Si nunca se llama a ``soltar_salto()`` el salto siempre es completo,
    igual que en la versión anterior. Todo el resto de la API pública
    (``mover``, ``dibujar``, ``saltar``, ``iniciar_engullido``...) se
    mantiene igual.
    """

    # ------------------------------------------------------------------
    # Márgenes de "salto justo" (en cuadros, asumiendo 60 FPS):
    # - Coyote time: permite saltar un instante después de dejar el borde.
    # - Buffer de salto: la pulsación adelantada se guarda y se ejecuta
    #   apenas se puede, en vez de perderse.
    # ------------------------------------------------------------------
    COYOTE_FRAMES = 6        # ~0.1 s
    BUFFER_SALTO_FRAMES = 8  # ~0.13 s

    # ------------------------------------------------------------------
    # Ajustes de "feel". Todo es afinable desde aquí.
    # ------------------------------------------------------------------
    # Movimiento horizontal con inercia (px/frame²). La velocidad máxima
    # sigue siendo ``self.velocidad``.
    ACEL_SUELO = 1.15
    FRICCION_SUELO = 0.95
    ACEL_AIRE = 0.65
    FRICCION_AIRE = 0.25
    FACTOR_GIRO = 1.8        # al invertir el sentido se frena más rápido
    VEL_AGACHADO = 0.55      # fracción de la velocidad máxima al ir agachado

    # Física vertical. Poner FACTOR_CAIDA = 1.0 y FACTOR_SALTO_CORTO = 1.0
    # devuelve la física original.
    FACTOR_CAIDA = 1.2           # cae un poco más rápido de lo que sube
    FACTOR_SALTO_CORTO = 2.4     # gravedad extra si se suelta el salto subiendo
    VEL_CAIDA_MAX = 16.0         # velocidad terminal
    AJUSTE_ESQUINA = 10          # px de "perdón" al golpear una esquina con la cabeza

    # Dash (opt-in)
    DASH_FRAMES = 9
    DASH_VELOCIDAD = 15.0
    DASH_ENFRIAMIENTO = 24
    RASTRO_FRAMES = 8

    def __init__(self, x, y, color, volumen_efectos=1.0, dash_habilitado=False):
        # Tamaño aumentado ~25% respecto a la versión original (32x56 -> 40x70)
        self.rect = pygame.Rect(x, y, 40, 70)
        self.altura_normal = self.rect.height
        self.altura_agachado = 44
        self.color = color
        self.vel_x = 0.0
        self.vel_y = 0
        self.velocidad = 6
        self.gravedad = 0.6
        self.fuerza_salto = -13
        self.en_suelo = False
        self.plataforma_actual = None  # última plataforma sobre la que aterrizó

        # Restos subpíxel: pygame.Rect solo guarda enteros, así que sin esto
        # las velocidades fraccionarias (inercia, gravedad) se truncarían.
        self._resto_x = 0.0
        self._resto_y = 0.0

        # --- Coyote time y buffer de salto (ver constantes de clase) ---
        self.coyote_restante = 0
        self.buffer_salto_restante = 0
        self._salto_ejecutado_este_frame = False
        # Salto variable: mientras se mantiene la tecla el salto es completo;
        # al soltarla subiendo, la gravedad extra lo corta.
        self._salto_sostenido = False
        self._tecla_salto_soltada = False

        self.direccion = 1
        self.agachado = False
        self.agachado_animacion = 0.0

        # --- Muerte por trampa ---
        self.muriendo = False
        self.tiempo_muerte = 0.0
        self.plataforma_devora = None

        # --- Animación de caminata ---
        self.tiempo_animacion = 0.0
        self.velocidad_animacion = 0.20
        self.balanceo_actual = 0.0
        self.bob_actual = 0.0
        self.bob_cabeza_actual = 0.0
        self.inclinacion_actual = 0.0
        self.suavizado = 0.22
        self.tiempo_idle = 0.0
        self.amplitud_paso = 0.0   # 0 quieto -> 1 corriendo a tope
        self.pose_aire = 0.0       # 0 en suelo -> 1 en el aire (suavizado)

        # Squash & stretch al saltar/aterrizar
        self.escala_y = 1.0
        self.escala_y_objetivo = 1.0
        self.aterrizaje_ts = None
        self._compresion_aterrizaje = 0.76

        # --- Expresión según el nivel (ver actualizar_nivel) ---
        self.paranoico = False
        self.desesperado = False

        # --- Expresividad: parpadeo y mirada ociosa ---
        self.parpadeando = False
        self.proximo_parpadeo = pygame.time.get_ticks() + random.randint(1200, 3000)
        self.fin_parpadeo = 0
        self._mirada_invertida = False
        self._proxima_mirada = pygame.time.get_ticks() + random.randint(1500, 3500)

        # --- Partículas de polvo (pasos, derrapes y aterrizajes) ---
        self.particulas = []
        self._contador_derrape = 0

        # --- Bufanda: en este diseño se elimina el adorno visual ---
        self.bufanda = [[0.0, 0.0] for _ in range(5)]
        self._fase_bufanda = 0.0

        # --- Sombra proyectada: necesita conocer las plataformas ---
        self._plataformas = ()

        self.ultimo_paso = 0
        self.volumen_efectos = float(volumen_efectos)
        self.sonido_salto = self._crear_sonido(380, 0.14, 1.0, 720)
        self.sonido_paso = self._crear_sonido(140, 0.05, 1.0, 90, ruido=0.7)
        self.sonido_aterrizaje = self._crear_sonido(150, 0.10, 1.0, 55, ruido=0.35)

        # --- Doble salto ---
        self.saltos_maximos = 2
        self.saltos_restantes = self.saltos_maximos
        self.girando = False
        self.angulo_giro = 0.0
        self.velocidad_giro = 28
        self.sonido_doble_salto = self._crear_sonido(620, 0.16, 1.0, 1100)

        # --- Dash (opt-in) ---
        self.dash_habilitado = dash_habilitado
        self.dashes_maximos = 1
        self.dashes_disponibles = self.dashes_maximos
        self.dash_restante = 0
        self.dash_enfriamiento = 0
        self.dash_direccion = 1
        self.rastro = []  # [silueta, ancla, vida]
        self.sonido_dash = self._crear_sonido(900, 0.12, 1.0, 260, ruido=0.45)

        self.ajustar_volumen_efectos(self.volumen_efectos)

        # Tamaño de "pixel" para el look pixel art (bloques, no formas suaves)
        self.pixel = 4
        self._lienzo = None

    # ------------------------------------------------------------------
    # Sonido
    # ------------------------------------------------------------------
    @staticmethod
    def _crear_sonido(frecuencia, duracion, volumen, frecuencia_final=None, ruido=0.0):
        """Crea un tono corto en memoria (con barrido de frecuencia y ruido
        opcionales) para no depender de archivos externos.

        Respeta el formato real del mezclador: si está en estéreo duplica
        las muestras por canal (antes sonaba al doble de agudo y la mitad
        de largo).
        """
        config = pygame.mixer.get_init()
        if not config:
            return None
        frecuencia_muestreo, formato, canales = config
        if formato != -16:  # solo se genera audio de 16 bits con signo
            return None

        if frecuencia_final is None:
            frecuencia_final = frecuencia
        cantidad = max(1, int(frecuencia_muestreo * duracion))
        ataque = max(1, int(frecuencia_muestreo * 0.004))  # evita el "clic" inicial
        muestras = array("h")
        fase = 0.0
        for indice in range(cantidad):
            t = indice / cantidad
            envolvente = (1 - t) * min(1.0, indice / ataque)
            freq = frecuencia + (frecuencia_final - frecuencia) * t
            fase += 2 * math.pi * freq / frecuencia_muestreo
            onda = math.sin(fase) * (1 - ruido) + random.uniform(-1, 1) * ruido
            muestra = int(32767 * volumen * envolvente * onda)
            for _ in range(canales):
                muestras.append(muestra)
        return pygame.mixer.Sound(buffer=muestras.tobytes())

    def ajustar_volumen_efectos(self, volumen):
        """Ajusta los sonidos del personaje al nivel seleccionado en opciones."""
        self.volumen_efectos = max(0.0, min(1.0, float(volumen)))
        sonidos = (
            (self.sonido_salto, 0.07),
            (self.sonido_paso, 0.06),
            (self.sonido_aterrizaje, 0.10),
            (self.sonido_doble_salto, 0.07),
            (self.sonido_dash, 0.08),
        )
        for sonido, volumen_base in sonidos:
            if sonido is not None:
                sonido.set_volume(self.volumen_efectos * volumen_base)

    def actualizar_nivel(self, nivel):
        """Informa al personaje en qué nivel del juego está.

        A partir del nivel 10 el personaje adopta una expresión paranoica
        (ojos desorbitados y mirada nerviosa); a partir del 21, un estado
        desesperado (agotado, ojeras, sudor y temblor) que tiene prioridad
        visual. Llamar cada vez que cambie el nivel actual.
        """
        self.paranoico = nivel > 9
        self.desesperado = nivel >= 21

    # ------------------------------------------------------------------
    # Utilidades de color y dibujo
    # ------------------------------------------------------------------
    def _tono(self, factor):
        r, g, b = self.color[:3]
        return (
            max(0, min(255, int(r * factor))),
            max(0, min(255, int(g * factor))),
            max(0, min(255, int(b * factor))),
        )

    def _celda(self, valor):
        """Redondea a la grilla de píxeles."""
        return round(valor / self.pixel) * self.pixel

    def _bloque(self, superficie, x, y, ancho, alto, color):
        """Bloque alineado a la grilla (sin bordes redondeados ni AA)."""
        p = self.pixel
        rx = round(x / p) * p
        ry = round(y / p) * p
        ranch = max(p, round(ancho / p) * p)
        ralto = max(p, round(alto / p) * p)
        pygame.draw.rect(superficie, color, (rx, ry, ranch, ralto))

    def _bloque_contorneado(self, superficie, x, y, ancho, alto, color, color_contorno):
        """Como ``_bloque`` pero con borde oscuro grueso ("pocket cartoon")."""
        g = self.pixel
        self._bloque(superficie, x - g // 2, y - g // 2, ancho + g, alto + g, color_contorno)
        self._bloque(superficie, x, y, ancho, alto, color)

    @staticmethod
    def _lerp(actual, objetivo, factor):
        return actual + (objetivo - actual) * factor

    @staticmethod
    def _acercar(valor, objetivo, paso):
        """Mueve ``valor`` hacia ``objetivo`` como mucho ``paso`` unidades."""
        if valor < objetivo:
            return min(valor + paso, objetivo)
        return max(valor - paso, objetivo)

    @staticmethod
    def _hitbox(plataforma):
        return plataforma.rect_colision() if hasattr(plataforma, "rect_colision") else plataforma.rect

    @staticmethod
    def _alguna_pulsada(teclas, claves):
        if isinstance(claves, int):
            claves = (claves,)
        return any(teclas[c] for c in claves)

    # ------------------------------------------------------------------
    # Partículas
    # ------------------------------------------------------------------
    def _emitir_particulas(self, cantidad, x, y, dispersion=10, sesgo_x=0.0):
        for _ in range(cantidad):
            angulo = random.uniform(math.pi * 0.15, math.pi * 0.85)
            velocidad = random.uniform(1.2, 3.0)
            self.particulas.append(
                {
                    "x": x + random.uniform(-dispersion, dispersion),
                    "y": y,
                    "vx": math.cos(angulo) * velocidad + sesgo_x,
                    "vy": -math.sin(angulo) * velocidad,
                    "vida": 18,
                    "vida_max": 18,
                    "tam": random.uniform(2.5, 4.5),
                }
            )

    def _actualizar_particulas(self):
        vivas = []
        for particula in self.particulas:
            particula["x"] += particula["vx"]
            particula["y"] += particula["vy"]
            particula["vy"] += 0.15
            particula["vida"] -= 1
            if particula["vida"] > 0:
                vivas.append(particula)
        self.particulas = vivas

    def _dibujar_particulas(self, superficie, color_claro, color_oscuro):
        for particula in self.particulas:
            factor = particula["vida"] / particula["vida_max"]
            tam = max(1, int(particula["tam"] * factor))
            rect = pygame.Rect(0, 0, tam, tam)
            rect.center = (int(particula["x"]), int(particula["y"]))
            # Al nacer es más claro y se oscurece al apagarse.
            pygame.draw.rect(superficie, color_claro if factor > 0.5 else color_oscuro, rect)

    def _superficie_bajo_los_pies(self):
        """Y de la plataforma más alta que hay justo debajo del personaje
        (o None). Sirve para proyectar la sombra y leer la altura."""
        mejor = None
        for plataforma in self._plataformas:
            hb = self._hitbox(plataforma)
            if hb.left <= self.rect.centerx < hb.right and hb.top >= self.rect.bottom - 4:
                if mejor is None or hb.top < mejor:
                    mejor = hb.top
        return mejor

    def _dibujar_sombra(self, superficie, centro_x, pie_y):
        """Sombra de contacto proyectada sobre la plataforma de abajo: se
        encoge y se aclara cuanto más alto se esté, lo que ayuda a calcular
        dónde se va a aterrizar."""
        if self.en_suelo or self.muriendo:
            suelo_y = pie_y
            factor = 1.0
        else:
            suelo_y = self._superficie_bajo_los_pies()
            if suelo_y is None:
                return
            distancia = max(0, suelo_y - self.rect.bottom)
            if distancia > 420:
                return
            factor = max(0.35, 1 - distancia / 320)
        ancho = max(self.pixel, int(34 * factor))
        alto = max(2, int(7 * factor))
        sombra = pygame.Surface((ancho, alto), pygame.SRCALPHA)
        pygame.draw.ellipse(sombra, (0, 0, 0, int(60 + 80 * factor)), sombra.get_rect())
        superficie.blit(sombra, sombra.get_rect(center=(centro_x, suelo_y + 2)).topleft)

    # ------------------------------------------------------------------
    # Bufanda: eliminado del diseño visual.
    # ------------------------------------------------------------------
    def _actualizar_bufanda(self, dx_real, dy_real):
        self._fase_bufanda = 0.0
        self.bufanda = [[0.0, 0.0] for _ in range(len(self.bufanda))]

    # ------------------------------------------------------------------
    # Lógica principal
    # ------------------------------------------------------------------
    def mover(self, plataformas, controles=None):
        """Lee el teclado, aplica física y resuelve colisiones.

        ``plataformas`` debe contener objetos con atributo ``rect`` (y
        opcionalmente ``rect_colision()``). ``controles`` admite las
        claves ``left``, ``right``, ``down`` y, opcionalmente, ``jump``
        (una tecla o varias) para el salto variable sin tocar el bucle
        de eventos.
        """
        self._plataformas = plataformas
        if self.muriendo:
            self._actualizar_particulas()
            return

        centro_previo = self.rect.center
        estaba_en_suelo_frame_anterior = self.en_suelo
        self._salto_ejecutado_este_frame = False

        if self.coyote_restante > 0:
            self.coyote_restante -= 1
            if self.coyote_restante == 0:
                # Se agotó el margen sin saltar: caminar fuera de un borde
                # ya cuenta como haber gastado el salto "de suelo". Sin esto
                # se podía encadenar dos saltos aéreos tras caerse de un borde.
                self.saltos_restantes = min(self.saltos_restantes, self.saltos_maximos - 1)
        if self.buffer_salto_restante > 0:
            self.buffer_salto_restante -= 1
        if self.dash_enfriamiento > 0:
            self.dash_enfriamiento -= 1

        teclas = pygame.key.get_pressed()
        controles = controles or {
            "left": pygame.K_a,
            "right": pygame.K_d,
            "down": pygame.K_s,
        }
        if "jump" in controles and not self._alguna_pulsada(teclas, controles["jump"]):
            self._tecla_salto_soltada = True
            self._salto_sostenido = False

        # --- Agacharse ---
        quiere_agacharse = teclas[controles["down"]] or teclas[pygame.K_DOWN]
        if quiere_agacharse and not self.agachado:
            self._cambiar_altura(self.altura_agachado)
            self.agachado = True
        elif not quiere_agacharse and self.agachado and self._puede_estar_de_pie(plataformas):
            self._cambiar_altura(self.altura_normal)
            self.agachado = False

        objetivo_agachado = 1.0 if self.agachado else 0.0
        self.agachado_animacion = self._lerp(self.agachado_animacion, objetivo_agachado, 0.28)

        # --- Movimiento horizontal con inercia ---
        izquierda = teclas[controles["left"]] or teclas[pygame.K_LEFT]
        derecha = teclas[controles["right"]] or teclas[pygame.K_RIGHT]
        dir_input = 1 if derecha else (-1 if izquierda else 0)

        en_dash = self.dash_restante > 0
        if dir_input != 0 and not en_dash:
            self.direccion = dir_input

        if en_dash:
            self.vel_x = self.dash_direccion * self.DASH_VELOCIDAD
            self.vel_y = 0
            self.dash_restante -= 1
            if self.dash_restante == 0:
                # Sale del dash conservando algo de impulso.
                self.vel_x = self.dash_direccion * self.velocidad * 1.3
                self.dash_enfriamiento = self.DASH_ENFRIAMIENTO
        else:
            vel_max = self.velocidad * (self.VEL_AGACHADO if self.agachado else 1.0)
            if self.en_suelo:
                aceleracion, friccion = self.ACEL_SUELO, self.FRICCION_SUELO
            else:
                aceleracion, friccion = self.ACEL_AIRE, self.FRICCION_AIRE
            if dir_input != 0:
                if self.vel_x * dir_input < 0:
                    aceleracion *= self.FACTOR_GIRO
                self.vel_x = self._acercar(self.vel_x, dir_input * vel_max, aceleracion)
            else:
                self.vel_x = self._acercar(self.vel_x, 0.0, friccion)

        # Si hay un salto "guardado" y ya hay forma válida de saltar, se
        # ejecuta ahora en vez de perderse por llegar un instante pronto.
        if self.buffer_salto_restante > 0:
            if self.en_suelo or self.coyote_restante > 0 or self.saltos_restantes > 0:
                self.saltar()
                # Si la tecla ya se soltó mientras esperaba, es un toque corto.
                self._salto_sostenido = not self._tecla_salto_soltada
                self.buffer_salto_restante = 0

        # Arrastre por plataformas móviles
        if self.en_suelo and self.plataforma_actual is not None:
            desplazamiento = getattr(self.plataforma_actual, "desplazamiento_reciente", pygame.Vector2(0, 0))
            if desplazamiento.length_squared() > 0:
                self.rect.x += desplazamiento.x
                self.rect.y += desplazamiento.y

        # --- Gravedad: más ligera subiendo, más firme bajando ---
        if not en_dash:
            gravedad = self.gravedad
            if self.vel_y > 0:
                gravedad *= self.FACTOR_CAIDA
            elif self.vel_y < 0 and not self._salto_sostenido:
                gravedad *= self.FACTOR_SALTO_CORTO
            self.vel_y = min(self.vel_y + gravedad, self.VEL_CAIDA_MAX)

        # --- Eje X ---
        self._resto_x += self.vel_x
        paso_x = int(self._resto_x)
        self._resto_x -= paso_x
        self.rect.x += paso_x
        for plataforma in plataformas:
            hitbox = self._hitbox(plataforma)
            if self.rect.colliderect(hitbox):
                if self.en_suelo and self.plataforma_actual is plataforma:
                    continue
                if paso_x > 0:
                    self.rect.right = hitbox.left
                    self.vel_x = 0.0
                    self._resto_x = 0.0
                elif paso_x < 0:
                    self.rect.left = hitbox.right
                    self.vel_x = 0.0
                    self._resto_x = 0.0

        # --- Eje Y ---
        self._resto_y += self.vel_y
        paso_y = int(self._resto_y)
        self._resto_y -= paso_y
        self.rect.y += paso_y
        estaba_en_aire = not self.en_suelo
        self.en_suelo = False
        self.plataforma_actual = None
        impacto = 0.0
        for plataforma in plataformas:
            hitbox = self._hitbox(plataforma)
            if self.rect.colliderect(hitbox):
                if self.vel_y > 0:
                    if self.en_suelo and self.plataforma_actual is plataforma:
                        continue
                    impacto = max(impacto, self.vel_y)
                    self.rect.bottom = hitbox.top
                    self.vel_y = 0
                    self.en_suelo = True
                    # Se guarda la plataforma pisada: tras resolver la
                    # colisión rect.bottom queda pegado a rect.top y un
                    # colliderect posterior ya no detectaría superposición.
                    self.plataforma_actual = plataforma
                elif self.vel_y < 0:
                    # Esquina: si solo roza el borde con la cabeza, se
                    # empuja de lado y se conserva el salto.
                    if not self._esquivar_esquina(hitbox, plataformas):
                        self.rect.top = hitbox.bottom
                        self.vel_y = 0

        # Sonda de suelo: con velocidades fraccionarias el personaje puede
        # quedar a 1 px de la plataforma sin llegar a solaparla, lo que
        # hacía parpadear ``en_suelo``. Si hay suelo a 1 px, se pega a él.
        if not self.en_suelo and self.vel_y >= 0:
            sonda = self.rect.move(0, 1)
            for plataforma in plataformas:
                hitbox = self._hitbox(plataforma)
                if sonda.colliderect(hitbox):
                    impacto = max(impacto, self.vel_y)
                    self.rect.bottom = hitbox.top
                    self.vel_y = 0
                    self.en_suelo = True
                    self.plataforma_actual = plataforma
                    break
        if self.en_suelo:
            self._resto_y = 0.0
            self._salto_sostenido = False

        aterrizando_ahora = self.en_suelo and estaba_en_aire
        ahora = pygame.time.get_ticks()

        # Se perdió el suelo caminando hacia un borde: margen de coyote.
        if (
            estaba_en_suelo_frame_anterior
            and not self.en_suelo
            and not self._salto_ejecutado_este_frame
            and not en_dash
        ):
            self.coyote_restante = self.COYOTE_FRAMES

        if self.en_suelo and self.dash_restante == 0:
            self.dashes_disponibles = self.dashes_maximos

        if aterrizando_ahora:
            self.saltos_restantes = self.saltos_maximos
            self.girando = False
            self.angulo_giro = 0.0

        if self.girando:
            self.angulo_giro += self.velocidad_giro
            if self.angulo_giro >= 360:
                self.angulo_giro = 0.0
                self.girando = False

        # --- Animación suavizada ---
        caminando = abs(self.vel_x) > 0.4 and self.en_suelo
        intensidad = min(1.0, abs(self.vel_x) / self.velocidad)
        if caminando:
            self.tiempo_animacion += self.velocidad_animacion * max(0.6, intensidad)

        self.amplitud_paso = self._lerp(self.amplitud_paso, intensidad if caminando else 0.0, 0.25)
        self.pose_aire = self._lerp(self.pose_aire, 0.0 if self.en_suelo else 1.0, 0.30)

        objetivo_balanceo = math.sin(self.tiempo_animacion) * 8 * self.amplitud_paso if caminando else 0.0
        self.balanceo_actual = self._lerp(self.balanceo_actual, objetivo_balanceo, self.suavizado)

        objetivo_bob = abs(math.sin(self.tiempo_animacion)) * 3 * self.amplitud_paso if caminando else 0.0
        self.bob_actual = self._lerp(self.bob_actual, objetivo_bob, self.suavizado)
        self.bob_cabeza_actual = self._lerp(self.bob_cabeza_actual, self.bob_actual, 0.14)

        # Inclinación según la velocidad real: se echa hacia delante al
        # acelerar y hacia atrás al derrapar.
        if en_dash:
            objetivo_inclinacion = 9.0 * self.dash_direccion
        elif caminando or not self.en_suelo:
            objetivo_inclinacion = max(-1.3, min(1.3, self.vel_x / self.velocidad)) * 3.5
        else:
            objetivo_inclinacion = 0.0
        self.inclinacion_actual = self._lerp(self.inclinacion_actual, objetivo_inclinacion, 0.15)

        self.tiempo_idle = self.tiempo_idle + 0.05 if (not caminando and self.en_suelo) else 0.0

        # --- Rebote elástico al aterrizar, proporcional al impacto ---
        if aterrizando_ahora:
            fuerza = max(0.0, min(1.0, (impacto - 4) / 12))
            self._compresion_aterrizaje = 0.88 - 0.14 * fuerza
            self.aterrizaje_ts = ahora
            self._emitir_particulas(
                5 + int(fuerza * 8), self.rect.centerx, self.rect.bottom, dispersion=self.rect.width * 0.5
            )
            if self.sonido_aterrizaje:
                self.sonido_aterrizaje.play()

        if self.aterrizaje_ts is not None:
            transcurrido = ahora - self.aterrizaje_ts
            if transcurrido < 80:
                self.escala_y_objetivo = self._compresion_aterrizaje
            elif transcurrido < 170:
                self.escala_y_objetivo = 1.08
            elif transcurrido < 260:
                self.escala_y_objetivo = 0.97
            else:
                self.escala_y_objetivo = 1.0
                self.aterrizaje_ts = None
        elif not self.en_suelo:
            self.escala_y_objetivo = 1.08 if self.vel_y < 0 else 1.04
        else:
            self.escala_y_objetivo = 1.0 + math.sin(self.tiempo_idle) * 0.015
        self.escala_y = self._lerp(self.escala_y, self.escala_y_objetivo, 0.35)

        if not caminando:
            self.tiempo_animacion = 0.0

        # --- Pasos (más frecuentes cuanto más rápido) y derrape ---
        intervalo_paso = 260 / max(0.6, intensidad)
        if caminando and ahora - self.ultimo_paso > intervalo_paso:
            if self.sonido_paso:
                self.sonido_paso.play()
            self._emitir_particulas(
                3, self.rect.centerx - self.direccion * 10, self.rect.bottom, dispersion=6
            )
            self.ultimo_paso = ahora

        derrapando = self.en_suelo and (
            (dir_input != 0 and self.vel_x * dir_input < -2.5) or (dir_input == 0 and abs(self.vel_x) > 4.5)
        )
        if derrapando:
            self._contador_derrape += 1
            if self._contador_derrape % 3 == 0:
                sesgo = 1.4 if self.vel_x > 0 else -1.4
                self._emitir_particulas(
                    2, self.rect.centerx - (self.direccion * 6), self.rect.bottom, dispersion=5, sesgo_x=sesgo
                )
        else:
            self._contador_derrape = 0

        # --- Parpadeo y mirada ociosa ---
        if not self.parpadeando and ahora >= self.proximo_parpadeo:
            self.parpadeando = True
            self.fin_parpadeo = ahora + 90
        elif self.parpadeando and ahora >= self.fin_parpadeo:
            self.parpadeando = False
            self.proximo_parpadeo = ahora + random.randint(1800, 4200)

        if caminando or not self.en_suelo:
            self._mirada_invertida = False
        elif ahora >= self._proxima_mirada:
            # Quieto: de vez en cuando mira "hacia atrás", como curioseando.
            self._mirada_invertida = random.random() < 0.4
            self._proxima_mirada = ahora + random.randint(1200, 3200)

        # --- Rastro del dash y partículas ---
        for rastro in self.rastro:
            rastro[2] -= 1
        self.rastro = [r for r in self.rastro if r[2] > 0]

        self._actualizar_bufanda(self.rect.centerx - centro_previo[0], self.rect.centery - centro_previo[1])
        self._actualizar_particulas()

    def _esquivar_esquina(self, hitbox, plataformas):
        """Corrige un golpe de cabeza por el borde de un bloque empujando
        al personaje de lado si el solape es pequeño. Devuelve True si lo
        consiguió (y entonces el salto no se interrumpe)."""
        solape_izq = self.rect.right - hitbox.left
        solape_der = hitbox.right - self.rect.left
        if 0 < solape_izq <= self.AJUSTE_ESQUINA and solape_izq <= solape_der:
            desplazamiento = -solape_izq
        elif 0 < solape_der <= self.AJUSTE_ESQUINA:
            desplazamiento = solape_der
        else:
            return False
        candidato = self.rect.move(desplazamiento, 0)
        if any(candidato.colliderect(self._hitbox(p)) for p in plataformas):
            return False
        self.rect.x = candidato.x
        return True

    def _cambiar_altura(self, altura):
        """Cambia la caja vertical conservando la posición de los pies."""
        pie_y = self.rect.bottom
        self.rect.height = altura
        self.rect.bottom = pie_y

    def _puede_estar_de_pie(self, plataformas):
        """Comprueba que no haya una plataforma bloqueando la cabeza."""
        rect_de_pie = self.rect.copy()
        rect_de_pie.height = self.altura_normal
        rect_de_pie.bottom = self.rect.bottom
        return not any(rect_de_pie.colliderect(self._hitbox(plataforma)) for plataforma in plataformas)

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def saltar(self):
        """Inicia un salto desde el suelo (o dentro del coyote time) o un
        doble salto con giro si ya está en el aire y le queda uno."""
        if self.en_suelo or self.coyote_restante > 0:
            self.escala_y = 0.82  # compresión instantánea al despegar
            self.vel_y = self.fuerza_salto
            self.saltos_restantes = self.saltos_maximos - 1
            self.coyote_restante = 0
            self._salto_ejecutado_este_frame = True
            self._salto_sostenido = True
            self._resto_y = 0.0
            self._emitir_particulas(4, self.rect.centerx, self.rect.bottom, dispersion=8)
            if self.sonido_salto:
                self.sonido_salto.play()
        elif self.saltos_restantes > 0:
            self.saltos_restantes -= 1
            self.vel_y = self.fuerza_salto * 0.88  # un poco más débil que el primero
            self.escala_y = 1.15
            self.girando = True
            self.angulo_giro = 0.0
            self._salto_ejecutado_este_frame = True
            self._salto_sostenido = True
            self._resto_y = 0.0
            self._emitir_particulas(
                10, self.rect.centerx, self.rect.bottom, dispersion=self.rect.width * 0.6
            )
            if self.sonido_doble_salto:
                self.sonido_doble_salto.play()

    def solicitar_salto(self):
        """Llamar al pulsar la tecla de salto. Guarda la intención durante
        ``BUFFER_SALTO_FRAMES`` cuadros: si en ese margen hay suelo, coyote
        time o doble salto disponible, ``mover()`` lo ejecuta."""
        self.buffer_salto_restante = self.BUFFER_SALTO_FRAMES
        self._tecla_salto_soltada = False

    def soltar_salto(self):
        """Llamar al soltar la tecla de salto (KEYUP). Si el personaje aún
        está subiendo, el salto se acorta: toque = salto bajo, mantener =
        salto completo."""
        self._tecla_salto_soltada = True
        self._salto_sostenido = False

    def solicitar_dash(self):
        """Impulso horizontal rápido en la dirección a la que mira. Solo
        funciona si ``dash_habilitado`` es True; se recarga al tocar suelo."""
        if (
            not self.dash_habilitado
            or self.muriendo
            or self.dash_restante > 0
            or self.dash_enfriamiento > 0
            or self.dashes_disponibles <= 0
        ):
            return
        self.dashes_disponibles -= 1
        self.dash_restante = self.DASH_FRAMES
        self.dash_direccion = self.direccion
        self.vel_y = 0
        self._resto_y = 0.0
        self.girando = False
        self.angulo_giro = 0.0
        self._emitir_particulas(
            6, self.rect.centerx - self.direccion * 12, self.rect.bottom - 4,
            dispersion=6, sesgo_x=-self.direccion * 2.0,
        )
        if self.sonido_dash:
            self.sonido_dash.play()

    def iniciar_engullido(self, plataforma):
        """Activa la animación de muerte por trampa."""
        if self.muriendo:
            return
        self.muriendo = True
        self.plataforma_devora = plataforma
        self.tiempo_muerte = 0.0
        self.vel_x = 0.0
        self.vel_y = 0
        self.en_suelo = False
        self.plataforma_actual = None
        self.girando = False
        self.angulo_giro = 0.0
        self.dash_restante = 0

    def actualizar_engullido(self):
        """Avanza la animación de desaparición dentro de la plataforma."""
        if not self.muriendo:
            return
        self.tiempo_muerte += 1 / 60
        self.rect.y += 2.4
        self.escala_y_objetivo = max(0.08, 1.0 - self.tiempo_muerte * 1.45)
        self.escala_y = self._lerp(self.escala_y, self.escala_y_objetivo, 0.2)

        if self.plataforma_devora is not None:
            objetivo_x = self.plataforma_devora.rect.centerx
            self.rect.x = self._lerp(self.rect.x, objetivo_x, 0.12)

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------
    def dibujar(self, superficie):
        """Dibuja el personaje con bloques, sin imágenes externas.

        El cuerpo se dibuja en un lienzo local que luego se planta en las
        coordenadas del mundo; así puede rotarse entero en el doble salto.
        La sombra, las partículas y el rastro del dash se pintan directo
        sobre ``superficie`` para no girar con el personaje.
        """
        centro_x_mundo = self.rect.centerx
        pie_y_mundo = self.rect.bottom
        p = self.pixel

        # Paleta monocromática: todo deriva de self.color
        brillo = self._tono(1.75)
        claro = self._tono(1.45)
        base = self._tono(1.0)
        medio = self._tono(0.8)
        oscuro = self._tono(0.62)
        muy_oscuro = self._tono(0.35)
        contorno = self._tono(0.16)
        blanco_ojo = (245, 245, 245)

        balanceo = int(self.balanceo_actual)
        bob = int(self.bob_actual)
        bob_cabeza = int(self.bob_cabeza_actual)
        inclinacion = int(round(self.inclinacion_actual))
        estirar = self.escala_y
        aire = self.pose_aire
        subiendo = self.vel_y < 0
        en_dash = self.dash_restante > 0

        if self.muriendo:
            estirar = max(0.08, 1.0 - self.tiempo_muerte * 1.45)
            pie_y_mundo += int(self.tiempo_muerte * 32)

        self._dibujar_sombra(superficie, centro_x_mundo, pie_y_mundo)
        self._dibujar_particulas(superficie, self._tono(1.0), oscuro)

        # --- Lienzo local (reutilizado entre fotogramas) ---
        ANCHO_LIENZO = 140
        ALTO_LIENZO = 180
        centro_x = ANCHO_LIENZO // 2
        pie_y = 150
        if self._lienzo is None:
            self._lienzo = pygame.Surface((ANCHO_LIENZO, ALTO_LIENZO), pygame.SRCALPHA)
        lienzo = self._lienzo
        lienzo.fill((0, 0, 0, 0))

        agachado = self.agachado_animacion
        alto_torso_normal = round(26 * estirar / p) * p
        alto_pierna_normal = round(24 / estirar / p) * p if estirar else 24
        alto_torso = round(self._lerp(alto_torso_normal, 18, agachado) / p) * p
        alto_pierna = round(self._lerp(alto_pierna_normal, 12, agachado) / p) * p

        base_y = pie_y - bob

        # --- Piernas: en el suelo una se levanta en cada zancada; en el
        # aire se recogen al subir y se abren al caer. ---
        paso = math.sin(self.tiempo_animacion)
        elevar_izq = max(0.0, paso) * self.amplitud_paso * 8
        elevar_der = max(0.0, -paso) * self.amplitud_paso * 8
        desfase_pierna = balanceo // 2
        if aire > 0.05:
            elevar_izq = elevar_der = aire * (7 if subiendo else 2)
            desfase_pierna = int(aire * (2 if subiendo else 5))

        pierna_y = base_y - alto_pierna
        # La puntera del pie apunta hacia donde mira.
        punta_izq = -1 if self.direccion > 0 else -3
        for lado, elevar in ((-1, elevar_izq), (1, elevar_der)):
            alto_i = max(p, round((alto_pierna - elevar) / p) * p)
            pierna_x = centro_x - 12 - desfase_pierna if lado < 0 else centro_x + 3 + desfase_pierna
            self._bloque_contorneado(lienzo, pierna_x, pierna_y, 9, alto_i, oscuro, contorno)
            self._bloque_contorneado(
                lienzo, pierna_x + punta_izq, pierna_y + alto_i - p, 13, p, muy_oscuro, contorno
            )

        # --- Torso ---
        torso_x = centro_x + inclinacion
        torso_y = base_y - alto_pierna - alto_torso

        self._bloque_contorneado(lienzo, torso_x - 14, torso_y, 28, alto_torso, base, contorno)
        borde_sombra_x = torso_x + 10 if self.direccion > 0 else torso_x - 14
        self._bloque(lienzo, borde_sombra_x, torso_y, 4, alto_torso, oscuro)
        # Cinturón más limpio y sobrio
        self._bloque(lienzo, torso_x - 14, torso_y + alto_torso - p, 28, p, muy_oscuro)
        self._bloque(lienzo, torso_x - 2 + self.direccion * 2, torso_y + alto_torso - p, p, p, claro)
        # --- Brazos: se balancean al correr, suben en el aire y se echan
        # hacia atrás en el dash. ---
        brazo_alto = round(self._lerp(20, 14, agachado) / p) * p
        levantar = int(aire * (6 if subiendo else 10))
        brazo_izq_y = torso_y + 2 - balanceo + int(agachado * 6) - levantar
        brazo_der_y = torso_y + 2 + balanceo + int(agachado * 6) - levantar
        brazo_desplazamiento = int(agachado * 5) * self.direccion
        if en_dash:
            brazo_desplazamiento -= self.dash_direccion * 6
        self._bloque_contorneado(lienzo, torso_x - 23 + brazo_desplazamiento, brazo_izq_y, 9, brazo_alto, claro, contorno)
        self._bloque_contorneado(lienzo, torso_x + 14 + brazo_desplazamiento, brazo_der_y, 9, brazo_alto, claro, contorno)
        self._bloque(lienzo, torso_x - 23 + brazo_desplazamiento, brazo_izq_y + brazo_alto - p, 9, p, oscuro)
        self._bloque(lienzo, torso_x + 14 + brazo_desplazamiento, brazo_der_y + brazo_alto - p, 9, p, oscuro)

        # --- Cabeza (con retraso respecto al torso: follow-through) ---
        lado_cabeza = round(self._lerp(26, 22, agachado) / p) * p
        cabeza_x = torso_x
        cabeza_y = torso_y - lado_cabeza - (bob_cabeza - bob)
        self._bloque_contorneado(
            lienzo, cabeza_x - lado_cabeza // 2, cabeza_y, lado_cabeza, lado_cabeza, claro, contorno
        )
        # Acabado más limpio: sin la sombra extra de mejilla para que el rostro
        # se vea más simple y sobrio.
        brillo_x = cabeza_x - lado_cabeza // 2 + (p if self.direccion > 0 else lado_cabeza - 3 * p)
        self._bloque(lienzo, brillo_x, cabeza_y + p, p * 2, p, brillo)

        self._dibujar_pelo(lienzo, cabeza_x, cabeza_y, contorno)
        self._dibujar_cara(lienzo, cabeza_x, cabeza_y, lado_cabeza, contorno, blanco_ojo)

        # --- Giro del doble salto ---
        if self.girando:
            angulo = self.angulo_giro if self.direccion >= 0 else -self.angulo_giro
            lienzo = pygame.transform.rotate(lienzo, angulo)

        ancla_mundo = (centro_x_mundo, pie_y_mundo - (150 - ALTO_LIENZO // 2))

        # --- Rastro del dash: siluetas que se desvanecen detrás ---
        if en_dash and not self.muriendo:
            silueta = pygame.mask.from_surface(lienzo).to_surface(
                setcolor=claro + (255,), unsetcolor=(0, 0, 0, 0)
            )
            self.rastro.append([silueta, ancla_mundo, self.RASTRO_FRAMES])
        for silueta, ancla, vida in self.rastro:
            silueta.set_alpha(int(120 * vida / self.RASTRO_FRAMES))
            superficie.blit(silueta, silueta.get_rect(center=ancla))

        if self.desesperado:
            # Temblor leve: al límite de sus fuerzas.
            amplitud_temblor = self.pixel * 0.5
            ancla_mundo = (
                ancla_mundo[0] + random.uniform(-amplitud_temblor, amplitud_temblor),
                ancla_mundo[1] + random.uniform(-amplitud_temblor, amplitud_temblor),
            )
        superficie.blit(lienzo, lienzo.get_rect(center=ancla_mundo))

    def _dibujar_pelo(self, superficie, centro_x, cabeza_y, color):
        """Mechones de pelo que reaccionan al movimiento: se echan hacia
        atrás al correr, se alzan al caer y se aplastan al subir."""
        p = self.pixel
        viento = max(-1.0, min(1.0, -self.vel_x / self.velocidad))
        if self.vel_y > 4:
            extra = p
        elif self.vel_y < -4:
            extra = -p
        else:
            extra = 0
        for offset, alto in ((-8, p), (0, p * 2), (8, p)):
            niveles = max(1, (alto + extra) // p)
            for nivel in range(niveles):
                # Cuanto más arriba, más se dobla con el viento.
                desplaza = round(viento * nivel * 3)
                self._bloque(
                    superficie,
                    centro_x + offset - p // 2 + desplaza,
                    cabeza_y - (nivel + 1) * p,
                    p, p, color,
                )

    def _dibujar_cara(self, superficie, centro_x, cabeza_y, lado_cabeza, color_trazo, color_ojo):
        """Ojos y boca expresivos según el estado. Las pupilas se colocan
        explícitamente sobre la grilla y dentro del ojo: miran hacia donde
        avanza, hacia arriba al subir y hacia abajo al caer; en reposo, de
        vez en cuando miran hacia atrás."""
        p = self.pixel
        en_aire = not self.en_suelo
        separacion_ojo = lado_cabeza * 0.34
        ojo_y = cabeza_y + lado_cabeza * 0.40
        tam_ojo = p * 3 if en_aire else p * 2

        # Mirada: -1 izquierda / 0 centro / 1 derecha (y -1 arriba / 1 abajo)
        mirada = -self.direccion if self._mirada_invertida else self.direccion
        if en_aire:
            mirada_y = -1 if self.vel_y < -2 else (1 if self.vel_y > 2 else 0)
        else:
            mirada_y = 1

        if self.desesperado:
            # Ojos entornados con ojeras marcadas; sin ánimo para nada más.
            tam_ojo = p
        elif self.paranoico:
            # Ojos desorbitados con la mirada temblando de lado a lado.
            tam_ojo = p * 3
            ciclo = (pygame.time.get_ticks() // 90) % 4
            mirada = (-1, 0, 1, 0)[ciclo]
            mirada_y = 0

        huecos = (tam_ojo - p) // p  # posiciones posibles de la pupila - 1
        pupila_dx = round((mirada + 1) / 2 * huecos) * p
        pupila_dy = round((mirada_y + 1) / 2 * huecos) * p

        if self.parpadeando and not en_aire and not self.paranoico and not self.desesperado:
            for lado in (-1, 1):
                x = centro_x + lado * separacion_ojo
                self._bloque(superficie, x - p, ojo_y + p, p * 2, p, color_trazo)
        else:
            for lado in (-1, 1):
                x = centro_x + lado * separacion_ojo
                ex = self._celda(x - tam_ojo // 2)
                ey = self._celda(ojo_y)
                self._bloque(superficie, ex, ey, tam_ojo, tam_ojo, color_ojo)
                self._bloque(superficie, ex + pupila_dx, ey + pupila_dy, p, p, color_trazo)
                if self.desesperado:
                    self._bloque(superficie, x - tam_ojo, ojo_y + tam_ojo + p, tam_ojo * 2, p, color_trazo)

        if self.desesperado:
            # Gota de sudor cayendo por la sien (ciclo de ~0.9 s).
            lado_sien = 1 if self.direccion >= 0 else -1
            ciclo_sudor = pygame.time.get_ticks() % 900
            if ciclo_sudor < 600:
                progreso = ciclo_sudor / 600
                gota_x = centro_x + lado_cabeza * 0.58 * lado_sien
                gota_y = cabeza_y + lado_cabeza * (0.08 + 0.7 * progreso)
                tam_gota = p if progreso < 0.85 else max(1, p - 1)
                self._bloque_contorneado(
                    superficie, gota_x - tam_gota // 2, gota_y, tam_gota, tam_gota, color_ojo, color_trazo
                )

        # Boca (todos los bloques son múltiplos del píxel base)
        boca_y = cabeza_y + lado_cabeza * 0.81
        if self.desesperado:
            ancho_boca = p * 4
            self._bloque(superficie, centro_x - ancho_boca // 2, boca_y - p, ancho_boca, p * 2, color_trazo)
        elif self.paranoico:
            ancho_boca = p * 3
            self._bloque(superficie, centro_x - ancho_boca // 2, boca_y, ancho_boca, p, color_trazo)
        elif self.dash_restante > 0:
            # Esfuerzo: boca apretada y ancha
            ancho_boca = p * 4
            self._bloque(superficie, centro_x - ancho_boca // 2, boca_y, ancho_boca, p, color_trazo)
        elif en_aire:
            self._bloque(superficie, centro_x - p // 2, boca_y, p, p, color_trazo)
        else:
            ancho_boca = p * 3
            self._bloque(superficie, centro_x - ancho_boca // 2, boca_y, ancho_boca, p, color_trazo)
            self._bloque(superficie, centro_x - ancho_boca // 2, boca_y - p, p, p, color_trazo)
            self._bloque(superficie, centro_x + ancho_boca // 2 - p, boca_y - p, p, p, color_trazo)