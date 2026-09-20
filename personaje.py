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
    """

    def __init__(self, x, y, color):
        # Tamaño aumentado ~25% respecto a la versión original (32x56 -> 40x70)
        self.rect = pygame.Rect(x, y, 40, 70)
        self.altura_normal = self.rect.height
        self.altura_agachado = 44
        self.color = color
        self.vel_y = 0
        self.velocidad = 6
        self.fuerza_salto = -13
        self.en_suelo = False
        self.plataforma_actual = None  # última plataforma sobre la que aterrizó
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
        # Valores "actuales" que se interpolan suavemente hacia el objetivo,
        # para evitar saltos bruscos al empezar/parar de caminar.
        self.balanceo_actual = 0.0
        self.bob_actual = 0.0
        self.bob_cabeza_actual = 0.0  # sigue a bob_actual con retraso (follow-through)
        self.inclinacion_actual = 0.0  # lean del torso hacia la dirección de avance
        self.suavizado = 0.22  # factor de interpolación (0-1) por frame
        self.tiempo_idle = 0.0  # fase de la respiración cuando está quieto

        # Squash & stretch al saltar/aterrizar. El aterrizaje usa un
        # pequeño temporizador para poder hacer un rebote de tres fases
        # (compresión -> sobregiro -> reposo) en vez de un solo aplastamiento.
        self.escala_y = 1.0
        self.escala_y_objetivo = 1.0
        self.aterrizaje_ts = None

        # --- Expresividad: parpadeo con temporización aleatoria ---
        self.parpadeando = False
        self.proximo_parpadeo = pygame.time.get_ticks() + random.randint(1200, 3000)
        self.fin_parpadeo = 0

        # --- Partículas de polvo (pasos y aterrizajes) ---
        self.particulas = []

        self.ultimo_paso = 0
        self.sonido_salto = self._crear_sonido(620, 0.16, 0.18)
        self.sonido_paso = self._crear_sonido(125, 0.06, 0.10)
        self.sonido_aterrizaje = self._crear_sonido(95, 0.09, 0.14)

        # --- Doble salto ---
        self.saltos_maximos = 2
        self.saltos_restantes = self.saltos_maximos
        self.girando = False  # True mientras dura el giro del doble salto
        self.angulo_giro = 0.0
        self.velocidad_giro = 28  # grados por fotograma (~0.21s la vuelta completa a 60 FPS)
        self.sonido_doble_salto = self._crear_sonido(880, 0.14, 0.16)

        # Tamaño de "pixel" para el look pixel art (bloques, no formas suaves)
        self.pixel = 4

    @staticmethod
    def _crear_sonido(frecuencia, duracion, volumen):
        """Crea un tono corto en memoria para evitar depender de archivos externos."""
        if not pygame.mixer.get_init():
            return None

        frecuencia_muestreo = 44100
        cantidad_muestras = int(frecuencia_muestreo * duracion)
        muestras = array("h")
        for indice in range(cantidad_muestras):
            envolvente = 1 - indice / cantidad_muestras
            muestra = int(
                32767
                * volumen
                * envolvente
                * math.sin(2 * math.pi * frecuencia * indice / frecuencia_muestreo)
            )
            muestras.append(muestra)
        return pygame.mixer.Sound(buffer=muestras.tobytes())

    # ------------------------------------------------------------------
    # Utilidades de color monocromático: todo el personaje se dibuja a
    # partir de un único color base, variando solo su brillo.
    # ------------------------------------------------------------------
    def _tono(self, factor):
        r, g, b = self.color[:3]
        return (
            max(0, min(255, int(r * factor))),
            max(0, min(255, int(g * factor))),
            max(0, min(255, int(b * factor))),
        )

    def _bloque(self, superficie, x, y, ancho, alto, color):
        """Dibuja un bloque alineado a la grilla de píxeles (sin bordes
        redondeados ni antialiasing) para mantener el look pixel art."""
        p = self.pixel
        rx = round(x / p) * p
        ry = round(y / p) * p
        ranch = max(p, round(ancho / p) * p)
        ralto = max(p, round(alto / p) * p)
        pygame.draw.rect(superficie, color, (rx, ry, ranch, ralto))

    def _bloque_contorneado(self, superficie, x, y, ancho, alto, color, color_contorno):
        """Como ``_bloque``, pero con un borde oscuro grueso alrededor,
        para el look de línea marcada ("pocket cartoon") a juego con la
        cara de las transiciones de nivel."""
        g = self.pixel
        self._bloque(superficie, x - g // 2, y - g // 2, ancho + g, alto + g, color_contorno)
        self._bloque(superficie, x, y, ancho, alto, color)

    @staticmethod
    def _lerp(actual, objetivo, factor):
        return actual + (objetivo - actual) * factor

    # ------------------------------------------------------------------
    # Partículas de polvo: un pequeño estallido de bloques que se dispersan
    # y se encogen, usado al aterrizar y al dar cada paso.
    # ------------------------------------------------------------------
    def _emitir_particulas(self, cantidad, x, y, dispersion=10):
        for _ in range(cantidad):
            angulo = random.uniform(math.pi * 0.15, math.pi * 0.85)
            velocidad = random.uniform(1.2, 3.0)
            self.particulas.append(
                {
                    "x": x + random.uniform(-dispersion, dispersion),
                    "y": y,
                    "vx": math.cos(angulo) * velocidad,
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

    def _dibujar_particulas(self, superficie, color):
        for particula in self.particulas:
            factor = particula["vida"] / particula["vida_max"]
            tam = max(1, int(particula["tam"] * factor))
            rect = pygame.Rect(0, 0, tam, tam)
            rect.center = (int(particula["x"]), int(particula["y"]))
            pygame.draw.rect(superficie, color, rect)

    def _dibujar_sombra(self, superficie, centro_x, pie_y):
        """Sombra de contacto: se encoge y se aclara un poco en el aire
        para reforzar la sensación de altura del salto."""
        en_aire = not self.en_suelo
        factor = 0.55 if en_aire else 1.0
        ancho_sombra = max(self.pixel, int(30 * factor))
        alto_sombra = max(2, int(6 * factor))
        sombra = pygame.Surface((ancho_sombra, alto_sombra), pygame.SRCALPHA)
        sombra.fill((0, 0, 0, 90 if en_aire else 130))
        rect = sombra.get_rect(center=(centro_x, pie_y + 2))
        superficie.blit(sombra, rect.topleft)

    def mover(self, plataformas, controles=None):
        """Lee el teclado, aplica gravedad y resuelve colisiones.

        ``plataformas`` debe contener objetos con un atributo ``rect`` de
        tipo ``pygame.Rect``. La animación, el parpadeo, las partículas y
        los pasos se actualizan aquí para que sigan el movimiento real
        del personaje.
        """
        teclas = pygame.key.get_pressed()
        controles = controles or {
            "left": pygame.K_a,
            "right": pygame.K_d,
            "down": pygame.K_s,
        }
        quiere_agacharse = teclas[controles["down"]] or teclas[pygame.K_DOWN]
        if quiere_agacharse and not self.agachado:
            self._cambiar_altura(self.altura_agachado)
            self.agachado = True
        elif not quiere_agacharse and self.agachado and self._puede_estar_de_pie(plataformas):
            self._cambiar_altura(self.altura_normal)
            self.agachado = False

        objetivo_agachado = 1.0 if self.agachado else 0.0
        self.agachado_animacion = self._lerp(self.agachado_animacion, objetivo_agachado, 0.28)

        dx = 0
        if teclas[controles["left"]] or teclas[pygame.K_LEFT]:
            dx = -self.velocidad
        if teclas[controles["right"]] or teclas[pygame.K_RIGHT]:
            dx = self.velocidad

        caminando_input = dx != 0
        if caminando_input:
            self.direccion = 1 if dx > 0 else -1
            self.tiempo_animacion += self.velocidad_animacion

        self.vel_y += 0.6
        dy = self.vel_y

        self.rect.x += dx
        for plataforma in plataformas:
            if self.rect.colliderect(plataforma.rect):
                if dx > 0:
                    self.rect.right = plataforma.rect.left
                elif dx < 0:
                    self.rect.left = plataforma.rect.right

        self.rect.y += dy
        estaba_en_aire = not self.en_suelo
        self.en_suelo = False
        self.plataforma_actual = None
        for plataforma in plataformas:
            if self.rect.colliderect(plataforma.rect):
                if dy > 0:
                    self.rect.bottom = plataforma.rect.top
                    self.vel_y = 0
                    self.en_suelo = True
                    # Guardamos la plataforma pisada: una vez resuelta la
                    # colisión, rect.bottom queda pegado a rect.top y un
                    # colliderect posterior ya no detecta superposición,
                    # así que el estado "trampa pisada" se debe leer de aquí.
                    self.plataforma_actual = plataforma
                elif dy < 0:
                    self.rect.top = plataforma.rect.bottom
                    self.vel_y = 0

        aterrizando_ahora = self.en_suelo and estaba_en_aire
        ahora = pygame.time.get_ticks()

        if aterrizando_ahora:
            # Al tocar suelo se recarga el doble salto y, si venía girando,
            # se corta el giro en seco para no aterrizar a medio girar.
            self.saltos_restantes = self.saltos_maximos
            self.girando = False
            self.angulo_giro = 0.0

        if self.girando:
            self.angulo_giro += self.velocidad_giro
            if self.angulo_giro >= 360:
                self.angulo_giro = 0.0
                self.girando = False

        # --- Animación suavizada por interpolación (evita cortes bruscos) ---
        caminando = caminando_input and self.en_suelo
        objetivo_balanceo = math.sin(self.tiempo_animacion) * 8 if caminando else 0.0
        self.balanceo_actual = self._lerp(self.balanceo_actual, objetivo_balanceo, self.suavizado)

        objetivo_bob = abs(math.sin(self.tiempo_animacion)) * 3 if caminando else 0.0
        self.bob_actual = self._lerp(self.bob_actual, objetivo_bob, self.suavizado)
        # La cabeza sigue al torso con un pequeño retraso: principio de
        # animación clásico ("follow-through") que le da más vida al gesto.
        self.bob_cabeza_actual = self._lerp(self.bob_cabeza_actual, self.bob_actual, 0.14)

        # Inclinación del torso hacia la dirección de avance al caminar.
        objetivo_inclinacion = 3.5 * self.direccion if caminando else 0.0
        self.inclinacion_actual = self._lerp(self.inclinacion_actual, objetivo_inclinacion, 0.15)

        # Respiración sutil cuando está quieto y apoyado en el suelo.
        self.tiempo_idle = self.tiempo_idle + 0.05 if (not caminando and self.en_suelo) else 0.0

        # --- Rebote elástico al aterrizar (compresión -> sobregiro -> reposo) ---
        if aterrizando_ahora:
            self.aterrizaje_ts = ahora
            self._emitir_particulas(8, self.rect.centerx, self.rect.bottom, dispersion=self.rect.width * 0.5)
            if self.sonido_aterrizaje:
                self.sonido_aterrizaje.play()

        if self.aterrizaje_ts is not None:
            transcurrido = ahora - self.aterrizaje_ts
            if transcurrido < 80:
                self.escala_y_objetivo = 0.76
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

        if caminando and ahora - self.ultimo_paso > 260:
            if self.sonido_paso:
                self.sonido_paso.play()
            self._emitir_particulas(
                3, self.rect.centerx - self.direccion * 10, self.rect.bottom, dispersion=6
            )
            self.ultimo_paso = ahora

        # --- Parpadeo con temporización aleatoria ---
        if not self.parpadeando and ahora >= self.proximo_parpadeo:
            self.parpadeando = True
            self.fin_parpadeo = ahora + 90
        elif self.parpadeando and ahora >= self.fin_parpadeo:
            self.parpadeando = False
            self.proximo_parpadeo = ahora + random.randint(1800, 4200)

        self._actualizar_particulas()

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
        return not any(rect_de_pie.colliderect(plataforma.rect) for plataforma in plataformas)

    def saltar(self):
        """Inicia un salto si el personaje está apoyado en una plataforma,
        o un doble salto con giro si ya está en el aire y aún le queda uno
        disponible (se recarga al volver a tocar el suelo)."""
        if self.agachado:
            return

        if self.en_suelo:
            self.escala_y = 0.82  # ligera compresión instantánea al despegar
            self.vel_y = self.fuerza_salto
            self.saltos_restantes = self.saltos_maximos - 1
            if self.sonido_salto:
                self.sonido_salto.play()
        elif self.saltos_restantes > 0:
            self.saltos_restantes -= 1
            self.vel_y = self.fuerza_salto * 0.88  # un poco más débil que el primero
            self.escala_y = 1.15  # estiramiento (ya está en el aire, no hay compresión de despegue)
            self.girando = True
            self.angulo_giro = 0.0
            self._emitir_particulas(
                10, self.rect.centerx, self.rect.bottom, dispersion=self.rect.width * 0.6
            )
            if self.sonido_doble_salto:
                self.sonido_doble_salto.play()

    def iniciar_engullido(self, plataforma):
        """Activa la animación de muerte por trampa, como si la plataforma se
        lo tragara poco a poco."""
        if self.muriendo:
            return
        self.muriendo = True
        self.plataforma_devora = plataforma
        self.tiempo_muerte = 0.0
        self.vel_y = 0
        self.en_suelo = False
        self.plataforma_actual = None
        self.girando = False
        self.angulo_giro = 0.0

    def actualizar_engullido(self):
        """Avanza la animación de desaparición del personaje dentro de la
        plataforma sin permitir que siga moviéndose."""
        if not self.muriendo:
            return
        self.tiempo_muerte += 1 / 60
        self.rect.y += 2.4
        self.escala_y_objetivo = max(0.08, 1.0 - self.tiempo_muerte * 1.45)
        self.escala_y = self._lerp(self.escala_y, self.escala_y_objetivo, 0.2)

        if self.plataforma_devora is not None:
            objetivo_x = self.plataforma_devora.rect.centerx
            self.rect.x = self._lerp(self.rect.x, objetivo_x, 0.12)

    def dibujar(self, superficie):
        """Dibuja el personaje usando bloques, sin cargar imágenes externas.

        El cuerpo se dibuja primero en un lienzo local (``lienzo``) y luego
        se planta sobre ``superficie`` en las coordenadas del mundo. Esta
        indirección es la que permite rotarlo como un solo bloque durante
        el giro del doble salto sin tener que tocar cada pieza; la sombra
        y las partículas de polvo, en cambio, se pintan directamente sobre
        ``superficie`` para que se queden ancladas al suelo y no giren
        con el personaje.
        """
        centro_x_mundo = self.rect.centerx
        pie_y_mundo = self.rect.bottom
        p = self.pixel

        # Paleta monocromática: todo deriva de self.color
        claro = self._tono(1.45)
        base = self._tono(1.0)
        oscuro = self._tono(0.62)
        muy_oscuro = self._tono(0.35)
        contorno = self._tono(0.16)  # línea negra gruesa tipo "pocket cartoon"
        blanco_ojo = (245, 245, 245)

        balanceo = int(self.balanceo_actual)
        bob = int(self.bob_actual)
        bob_cabeza = int(self.bob_cabeza_actual)
        inclinacion = int(round(self.inclinacion_actual))
        estirar = self.escala_y

        if self.muriendo:
            estirar = max(0.08, 1.0 - self.tiempo_muerte * 1.45)
            pie_y_mundo += int(self.tiempo_muerte * 32)

        self._dibujar_sombra(superficie, centro_x_mundo, pie_y_mundo)
        self._dibujar_particulas(superficie, oscuro)

        # --- Lienzo local para el cuerpo (ver docstring) ---
        ANCHO_LIENZO = 140
        ALTO_LIENZO = 180
        centro_x = ANCHO_LIENZO // 2  # 70: el personaje siempre se dibuja centrado
        pie_y = 150  # deja sitio de sobra arriba para cabeza + pelo + estiramientos
        lienzo = pygame.Surface((ANCHO_LIENZO, ALTO_LIENZO), pygame.SRCALPHA)

        # Altura efectiva del cuerpo aplicando squash/stretch, manteniendo
        # los pies apoyados en pie_y.
        agachado = self.agachado_animacion
        alto_torso_normal = round(26 * estirar / p) * p
        alto_pierna_normal = round(24 / estirar / p) * p if estirar else 24
        alto_torso = round(self._lerp(alto_torso_normal, 18, agachado) / p) * p
        alto_pierna = round(self._lerp(alto_pierna_normal, 12, agachado) / p) * p

        base_y = pie_y - bob

        # --- Piernas (bloques oscuros, con contorno) ---
        pierna_izq_y = base_y - alto_pierna
        pierna_der_y = base_y - alto_pierna
        desfase_pierna = balanceo // 2
        self._bloque_contorneado(
            lienzo, centro_x - 12 - desfase_pierna, pierna_izq_y, 9, alto_pierna, oscuro, contorno
        )
        self._bloque_contorneado(
            lienzo, centro_x + 3 + desfase_pierna, pierna_der_y, 9, alto_pierna, oscuro, contorno
        )

        # Pies (un poco más anchos que las piernas, para que no parezcan
        # simples listones y den una base más sólida al personaje)
        self._bloque_contorneado(
            lienzo, centro_x - 15 - desfase_pierna, base_y - p, 13, p, muy_oscuro, contorno
        )
        self._bloque_contorneado(
            lienzo, centro_x + 2 + desfase_pierna, base_y - p, 13, p, muy_oscuro, contorno
        )

        # --- Torso (bloque principal, con una ligera inclinación hacia la
        # dirección de avance al caminar) ---
        torso_x = centro_x + inclinacion
        torso_y = base_y - alto_pierna - alto_torso
        self._bloque_contorneado(lienzo, torso_x - 14, torso_y, 28, alto_torso, base, contorno)
        borde_sombra_x = torso_x + 10 if self.direccion > 0 else torso_x - 14
        self._bloque(lienzo, borde_sombra_x, torso_y, 4, alto_torso, oscuro)

        # --- Brazos (con manos: un bloque extra más oscuro en la punta) ---
        brazo_alto = round(self._lerp(20, 14, agachado) / p) * p
        brazo_izq_y = torso_y + 2 - balanceo + int(agachado * 6)
        brazo_der_y = torso_y + 2 + balanceo + int(agachado * 6)
        brazo_desplazamiento = int(agachado * 5) * self.direccion
        self._bloque_contorneado(lienzo, torso_x - 23 + brazo_desplazamiento, brazo_izq_y, 9, brazo_alto, claro, contorno)
        self._bloque_contorneado(lienzo, torso_x + 14 + brazo_desplazamiento, brazo_der_y, 9, brazo_alto, claro, contorno)
        self._bloque(lienzo, torso_x - 23 + brazo_desplazamiento, brazo_izq_y + brazo_alto - p, 9, p, oscuro)
        self._bloque(lienzo, torso_x + 14 + brazo_desplazamiento, brazo_der_y + brazo_alto - p, 9, p, oscuro)

        # --- Cabeza (con un pequeño retraso respecto al torso para dar
        # sensación de "follow-through"). Es notablemente más grande que
        # en la primera versión: la proporción "cabezona" de caricatura
        # deja sitio de sobra para que los rasgos de la cara se lean bien
        # en la grilla de píxeles. ---
        lado_cabeza = round(self._lerp(26, 22, agachado) / p) * p
        cabeza_x = torso_x
        cabeza_y = torso_y - lado_cabeza - (bob_cabeza - bob)
        self._bloque_contorneado(
            lienzo, cabeza_x - lado_cabeza // 2, cabeza_y, lado_cabeza, lado_cabeza, claro, contorno
        )
        # Sombra de mejilla/mandíbula: solo en la mitad inferior de la
        # cabeza para no atravesar los ojos.
        self._bloque(
            lienzo,
            cabeza_x - lado_cabeza // 2 + (lado_cabeza // 2 if self.direccion > 0 else 2),
            cabeza_y + lado_cabeza * 0.5,
            8,
            lado_cabeza * 0.5,
            base,
        )

        self._dibujar_pelo(lienzo, cabeza_x, cabeza_y, contorno)
        self._dibujar_cara(lienzo, cabeza_x, cabeza_y, lado_cabeza, contorno, blanco_ojo)

        # --- Giro del doble salto: se rota el lienzo completo. La rotación
        # de pygame conserva el centro de la superficie, así que el ancla
        # de mundo (calculada más abajo) sigue siendo válida tanto si el
        # lienzo rotó como si no. ---
        if self.girando:
            angulo = self.angulo_giro if self.direccion >= 0 else -self.angulo_giro
            lienzo = pygame.transform.rotate(lienzo, angulo)

        ancla_mundo = (centro_x_mundo, pie_y_mundo - (150 - ALTO_LIENZO // 2))
        superficie.blit(lienzo, lienzo.get_rect(center=ancla_mundo))

    def _dibujar_pelo(self, superficie, centro_x, cabeza_y, color):
        """Un pequeño mechón de pelo alborotado, a juego con los tufts de
        la cara caricaturesca de las transiciones de nivel."""
        p = self.pixel
        for offset, alto in ((-8, p), (0, p * 2), (8, p)):
            self._bloque(superficie, centro_x + offset - p // 2, cabeza_y - alto, p, alto, color)

    def _dibujar_cara(self, superficie, centro_x, cabeza_y, lado_cabeza, color_trazo, color_ojo):
        """Ojos y boca expresivos: cambian de gesto según el estado
        (ojos bien abiertos y boca en "O" de sorpresa en el aire, ojos
        normales y sonrisa amplia en tierra). Los ojos parpadean con
        temporización aleatoria y miran hacia la dirección de avance.

        A esta resolución de píxel unas cejas fujaban con el contorno
        negro de la cabeza y se volvían ilegibles, así que la expresión
        recae por completo en el tamaño de los ojos y la forma de la boca.
        """
        p = self.pixel
        en_aire = not self.en_suelo
        separacion_ojo = lado_cabeza * 0.34
        ojo_y = cabeza_y + lado_cabeza * 0.40
        tam_ojo = p * 3 if en_aire else p * 2
        desplazamiento_mirada = (p // 2) * self.direccion

        if self.parpadeando and not en_aire:
            for lado in (-1, 1):
                x = centro_x + lado * separacion_ojo
                self._bloque(superficie, x - p, ojo_y + p, p * 2, p, color_trazo)
        else:
            for lado in (-1, 1):
                x = centro_x + lado * separacion_ojo
                self._bloque(superficie, x - tam_ojo // 2, ojo_y, tam_ojo, tam_ojo, color_ojo)
                self._bloque(
                    superficie,
                    x - p // 2 + desplazamiento_mirada,
                    ojo_y + tam_ojo // 2 - p // 2,
                    p,
                    p,
                    color_trazo,
                )

        # Boca: "O" de sorpresa en el aire, sonrisa amplia en el suelo.
        # Todos los bloques miden un múltiplo entero de "pixel": una boca
        # con bloques más finos que eso se redondea igualmente al tamaño
        # mínimo del bloque y pierde la forma de sonrisa.
        boca_y = cabeza_y + lado_cabeza * 0.81
        if en_aire:
            self._bloque(superficie, centro_x - p // 2, boca_y, p, p, color_trazo)
        else:
            ancho_boca = p * 3
            self._bloque(superficie, centro_x - ancho_boca // 2, boca_y, ancho_boca, p, color_trazo)
            self._bloque(superficie, centro_x - ancho_boca // 2, boca_y - p, p, p, color_trazo)
            self._bloque(superficie, centro_x + ancho_boca // 2 - p, boca_y - p, p, p, color_trazo)