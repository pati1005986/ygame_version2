"""Entidad enemiga del juego: una presencia gris, ajena a la paleta de color
del resto del mundo.

Todo se construye a partir de un único gris puro (r == g == b), así que
ningún matiz se le puede filtrar: sea cual sea la animación, sigue siendo
gris. Es un contraste deliberado con el resto del juego y encaja con la
desaturación progresiva de los niveles (``saturacion_nivel`` en juego.py).

Mejoras de esta versión
-----------------------
IA (máquina de estados):
    PATRULLA -> SOSPECHA -> PERSECUCION -> BUSQUEDA -> ESPERA -> PATRULLA
  * Línea de visión real: las plataformas le tapan la vista.
  * Oído: nota al jugador muy cerca aunque esté a su espalda o tapado.
  * La sospecha es una barra 0-1 que sube/baja (no un interruptor).
  * Al perder al jugador va a su última posición conocida y *busca*
    mirando a ambos lados antes de rendirse (antes oscilaba en el sitio).
  * En patrulla se detiene a mirar en los bordes y a veces al azar.
  * Al perseguir también salta huecos entre plataformas.
  * ``propagar_alerta(entidades)``: si una persigue, avisa a las cercanas.

Movimiento:
  * Aceleración y frenado (peso) en vez de velocidad instantánea.
  * Posición con resto subpíxel (ya no camina distinto a izq. y der.).
  * Ciclo de paso real: piernas que se levantan, brazos que se balancean,
    cabeza que rebota e inclina el cuerpo hacia donde corre.

Diseño y mirada:
  * Dos cuencas oscuras con pupilas pálidas que siguen al jugador.
  * Ceño fruncido al perseguir, "?" al sospechar/buscar, "!" al detectar.
  * Cresta punk que se eriza con la sospecha, brazos adelantados al correr.
  * Grano de puntillismo en el cuerpo y *glitch* horizontal al perseguir.
"""

import math
import random

import pygame

PATRULLA = "patrulla"
ESPERA = "espera"
SOSPECHA = "sospecha"
PERSECUCION = "persecucion"
BUSQUEDA = "busqueda"


class EntidadGris:
    """Enemigo gris con percepción, memoria y estados de ánimo legibles.

    Args:
        x, y: Posición inicial del rectángulo de colisión.
        velocidad_patrulla, velocidad_persecucion, rango_deteccion:
            Parámetros de dificultad (vienen de ``dificultad.py``).
    """

    COLOR_BASE = (132, 132, 132)
    BLANCO = (238, 238, 238)

    def __init__(
        self,
        x,
        y,
        velocidad_patrulla=1.8,
        velocidad_persecucion=3.0,
        rango_deteccion=220,
    ):
        self.rect = pygame.Rect(x, y, 32, 58)
        self.vel_x = 0.0
        self.vel_y = 0
        self._resto_x = 0.0
        self.velocidad_patrulla = velocidad_patrulla
        self.velocidad_persecucion = velocidad_persecucion
        self.rango_deteccion = rango_deteccion
        self.en_suelo = False
        self.plataforma_actual = None
        self.direccion = random.choice((-1, 1))
        self.pixel = 4
        self.fase = random.uniform(0, math.tau)
        self.activa = True
        self.reloj = 0
        self._semilla = random.randrange(1_000_000)

        # --- IA ---
        self.estado = PATRULLA
        self.sospecha = 0.0  # 0-1: al llegar a 1 empieza la persecución
        self.cuadros_estado = 0
        self.direccion_siguiente = self.direccion
        self.detectando_ahora = False
        self.tiempo_reaccion = 14  # cuadros viendo al jugador para pasar a 1.0
        self.memoria_x = None
        self.memoria_y = None
        self.cuadros_memoria = 0
        self.tiempo_memoria = 100
        self.tolerancia_cono = 26
        self.radio_oido = 70
        self.cuadros_exclamacion = 0

        # --- mirada (valores suavizados de -1 a 1) ---
        self.mirada_x = float(self.direccion)
        self.mirada_y = 0.0

        # --- alerta por cercanía (para viñeta/temblor en juego.py) ---
        self.intensidad_alerta = 0.0
        self.distancia_alerta_maxima = 45

        # --- salto ---
        self.fuerza_salto = -11.5
        self.temporizador_salto = 0
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

        # --- animación ---
        self.fase_paso = 0.0

    # ------------------------------------------------------------------
    # Compatibilidad con el código existente
    # ------------------------------------------------------------------
    @property
    def alerta(self):
        return self.estado in (PERSECUCION, BUSQUEDA)

    def nivel_alerta(self):
        """0.0-1.0 según cercanía al jugador (para viñeta, temblor, sonido)."""
        return self.intensidad_alerta

    def esta_persiguiendo(self):
        return self.alerta

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    @staticmethod
    def _hitbox(plataforma):
        if hasattr(plataforma, "rect_colision"):
            return plataforma.rect_colision()
        return plataforma.rect

    def _tono(self, factor):
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

    def _glifo(self, superficie, celdas, ox, oy, color, contorno):
        """Dibuja un símbolo de píxeles: primero todos los contornos y luego
        los rellenos, para que un bloque no tape el contorno del vecino."""
        p = self.pixel
        for c, f in celdas:
            self._bloque(superficie, ox + c * p - 2, oy + f * p - 2, p + 4, p + 4, contorno)
        for c, f in celdas:
            self._bloque(superficie, ox + c * p, oy + f * p, p, p, color)

    # ------------------------------------------------------------------
    # Percepción
    # ------------------------------------------------------------------
    def _linea_de_vision(self, objetivo_rect, plataformas):
        """False si alguna plataforma sólida corta la línea ojos -> jugador."""
        ox, oy = self.rect.centerx, self.rect.top + 14
        tx, ty = objetivo_rect.center
        for plataforma in plataformas:
            if getattr(plataforma, "es_trampa", False):
                continue
            if self._hitbox(plataforma).clipline(ox, oy, tx, ty):
                return False
        return True

    def _percibir(self, objetivo_rect, plataformas):
        dx = objetivo_rect.centerx - self.rect.centerx
        dy = objetivo_rect.centery - self.rect.centery
        distancia = math.hypot(dx, dy)

        en_rango = abs(dx) < self.rango_deteccion and abs(dy) < 80
        # Mientras persigue ya está atenta: no le da la espalda al jugador.
        de_frente = dx * self.direccion >= -self.tolerancia_cono or self.estado == PERSECUCION
        ve = en_rango and de_frente and self._linea_de_vision(objetivo_rect, plataformas)
        oye = (not ve) and distancia < self.radio_oido
        return ve, oye, distancia

    def _destino(self, objetivo_rect, ve):
        if ve and objetivo_rect is not None:
            return objetivo_rect.centerx, objetivo_rect.centery
        if self.memoria_x is not None:
            return self.memoria_x, self.memoria_y
        return None

    def recibir_aviso(self, x, y):
        """Otra entidad le avisa de dónde vio al jugador."""
        if self.estado in (PATRULLA, ESPERA, SOSPECHA):
            self.memoria_x, self.memoria_y = x, y
            self.cuadros_memoria = self.tiempo_memoria
            self.sospecha = 1.0
            self._cambiar(PERSECUCION)

    # ------------------------------------------------------------------
    # Cognición: transiciones de estado
    # ------------------------------------------------------------------
    def _cambiar(self, nuevo, siguiente=None):
        anterior = self.estado
        self.estado = nuevo
        if nuevo == ESPERA:
            self.cuadros_estado = random.randint(40, 70)
            self.direccion_siguiente = -self.direccion if siguiente is None else siguiente
        elif nuevo == BUSQUEDA:
            self.cuadros_estado = 81
            self.sospecha = 0.5
        elif nuevo == PERSECUCION and anterior != PERSECUCION:
            if anterior != BUSQUEDA:
                self.cuadros_exclamacion = 30
            self.cuadros_memoria = self.tiempo_memoria
        elif nuevo == PATRULLA:
            self.sospecha = 0.0

    def _pensar(self, ve, oye, objetivo_rect, dx_real):
        paso = 1.0 / self.tiempo_reaccion
        if ve:
            self.memoria_x, self.memoria_y = objetivo_rect.center
            self.cuadros_memoria = self.tiempo_memoria
            self.sospecha = min(1.0, self.sospecha + paso)
        elif oye:
            self.memoria_x, self.memoria_y = objetivo_rect.center
            self.cuadros_memoria = max(self.cuadros_memoria, self.tiempo_memoria // 2)
            self.sospecha = min(1.0, self.sospecha + paso * 0.5)
            if self.estado in (PATRULLA, ESPERA):
                self.direccion = 1 if dx_real > 0 else -1  # se gira hacia el ruido
        elif self.estado not in (PERSECUCION, BUSQUEDA):
            self.sospecha = max(0.0, self.sospecha - paso * 0.5)

        e = self.estado
        if e in (PATRULLA, ESPERA, SOSPECHA) and self.sospecha >= 1.0:
            self._cambiar(PERSECUCION)
        elif e in (PATRULLA, ESPERA) and self.sospecha > 0.25 and (ve or oye):
            self._cambiar(SOSPECHA)
        elif e == SOSPECHA and self.sospecha <= 0.05:
            self._cambiar(PATRULLA)
        elif e == PERSECUCION and not ve:
            self.cuadros_memoria -= 1
            llego = (
                self.memoria_x is not None
                and abs(self.memoria_x - self.rect.centerx) < 10
            )
            if llego or self.cuadros_memoria <= 0:
                self._cambiar(BUSQUEDA)
        elif e == BUSQUEDA:
            if self.sospecha >= 1.0:
                self._cambiar(PERSECUCION)

    # ------------------------------------------------------------------
    # Salto
    # ------------------------------------------------------------------
    def _buscar_salto_de_borde(self, plataformas):
        """Dirección a la que saltar si el suelo se acaba y hay otra
        plataforma alcanzable; si no, ``None``."""
        if self.plataforma_actual is None:
            return None

        borde_actual = self.plataforma_actual.rect
        cerca_del_borde = (
            self.direccion > 0 and self.rect.right >= borde_actual.right - 4
        ) or (self.direccion < 0 and self.rect.left <= borde_actual.left + 4)
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
        for despl in (-10, 0, 10):
            self._particulas_polvo.append(
                {
                    "x": self.rect.centerx + despl,
                    "y": self.rect.bottom,
                    "vx": despl * 0.15,
                    "vy": -1.2,
                    "vida": 14,
                    "vida_max": 14,
                }
            )

    def _actualizar_particulas(self):
        vivas = []
        for p in self._particulas_polvo:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vy"] += 0.15
            p["vida"] -= 1
            if p["vida"] > 0:
                vivas.append(p)
        self._particulas_polvo = vivas

    # ------------------------------------------------------------------
    # Mirada
    # ------------------------------------------------------------------
    def _actualizar_mirada(self, destino):
        e = self.estado
        if e in (PERSECUCION, SOSPECHA) and destino is not None:
            dx = destino[0] - self.rect.centerx
            dy = destino[1] - self.rect.centery
            obj_x = max(-1.0, min(1.0, dx / 50))
            obj_y = max(-1.0, min(1.0, dy / 50))
        elif e in (ESPERA, BUSQUEDA):
            obj_x = math.sin(self.reloj * 0.09 + self.fase)  # escanea
            obj_y = 0.0
        else:
            obj_x, obj_y = float(self.direccion), 0.0
        self.mirada_x += (obj_x - self.mirada_x) * 0.25
        self.mirada_y += (obj_y - self.mirada_y) * 0.25

    # ------------------------------------------------------------------
    # Movimiento
    # ------------------------------------------------------------------
    def mover(self, plataformas, objetivo_rect=None):
        """Percibe, decide y se mueve. Misma firma que la versión anterior."""
        if not self.activa:
            return

        self.reloj += 1
        if self.temporizador_salto > 0:
            self.temporizador_salto -= 1
        if self.cuadros_exclamacion > 0:
            self.cuadros_exclamacion -= 1

        # 1. percepción
        ve = oye = False
        distancia = float("inf")
        dx_real = 0
        if objetivo_rect is not None:
            dx_real = objetivo_rect.centerx - self.rect.centerx
            ve, oye, distancia = self._percibir(objetivo_rect, plataformas)
        self.detectando_ahora = ve

        # 2. cognición
        if objetivo_rect is not None:
            self._pensar(ve, oye, objetivo_rect, dx_real)
            rango_aviso = max(self.rango_deteccion, self.distancia_alerta_maxima + 1)
            crudo = (rango_aviso - distancia) / (rango_aviso - self.distancia_alerta_maxima)
            self.intensidad_alerta = max(0.0, min(1.0, crudo))
        else:
            self.intensidad_alerta = 0.0

        destino = self._destino(objetivo_rect, ve)
        self._actualizar_mirada(destino)

        # 3. qué quiere hacer este cuadro
        moviendo = False
        velocidad = self.velocidad_patrulla
        dy = 0
        e = self.estado

        if e == PATRULLA:
            moviendo = True
            if self.en_suelo and self.cuadros_anticipacion == 0 and random.random() < 0.0015:
                self._cambiar(ESPERA, siguiente=random.choice((-1, 1)))
                moviendo = False
        elif e == PERSECUCION:
            velocidad = self.velocidad_persecucion
            if destino is not None:
                dx = destino[0] - self.rect.centerx
                dy = destino[1] - self.rect.centery
                if abs(dx) > 6:  # zona muerta: evita el temblor bajo el jugador
                    self.direccion = 1 if dx > 0 else -1
                    moviendo = True
        elif e == SOSPECHA:
            if destino is not None:
                self.direccion = 1 if destino[0] > self.rect.centerx else -1
        elif e == ESPERA:
            self.cuadros_estado -= 1
            if self.cuadros_estado == 30:  # a medio camino mira hacia el otro lado
                self.direccion = self.direccion_siguiente
            if self.cuadros_estado <= 0:
                self._cambiar(PATRULLA)
        elif e == BUSQUEDA:
            self.cuadros_estado -= 1
            if self.cuadros_estado % 27 == 0:
                self.direccion *= -1  # mira a un lado y al otro
            if self.cuadros_estado <= 0:
                self._cambiar(ESPERA)

        # 4. salto (anticipación -> impulso)
        if self.cuadros_anticipacion > 0:
            self.cuadros_anticipacion -= 1
            moviendo = False
            self.vel_x = 0.0
            if self.cuadros_anticipacion == 0 and self.en_suelo:
                self.vel_y = self.fuerza_salto
                self.en_suelo = False
                self.direccion = self.saltando_hacia
                self.temporizador_salto = self.enfriamiento_salto
                velocidad_salto = (
                    self.velocidad_persecucion if self.estado == PERSECUCION
                    else self.velocidad_patrulla
                )
                self.vel_x = self.direccion * velocidad_salto
        elif self.en_suelo and self.temporizador_salto <= 0:
            if e == PERSECUCION:
                if (
                    -self.altura_max_salto_persecucion <= dy <= -self.altura_min_salto_persecucion
                    and destino is not None
                    and abs(destino[0] - self.rect.centerx) < 140
                ):
                    self._iniciar_anticipacion_salto(self.direccion)
                elif dy <= 60:  # si el jugador está mucho más abajo, la deja caer
                    candidato = self._buscar_salto_de_borde(plataformas)
                    if candidato is not None:
                        self._iniciar_anticipacion_salto(candidato)
            elif e == PATRULLA:
                candidato = self._buscar_salto_de_borde(plataformas)
                if candidato is not None:
                    self._iniciar_anticipacion_salto(candidato)

        # 5. velocidad con inercia
        objetivo_vx = velocidad * self.direccion if moviendo else 0.0
        if self.en_suelo:
            acel = 0.55 if objetivo_vx * self.vel_x < 0 else 0.3
            if objetivo_vx == 0:
                acel = 0.45
            self.vel_x += max(-acel, min(acel, objetivo_vx - self.vel_x))
        elif moviendo:
            self.vel_x = objetivo_vx

        if self.en_suelo and abs(self.vel_x) > 0.05:
            self.fase_paso += abs(self.vel_x) * 0.17

        # 6. física
        self.vel_y += 0.6
        dy_mov = self.vel_y

        self._resto_x += self.vel_x
        paso = int(self._resto_x)
        self._resto_x -= paso
        self.rect.x += paso
        for plataforma in plataformas:
            hitbox = self._hitbox(plataforma)
            if self.rect.colliderect(hitbox):
                if self.en_suelo and self.plataforma_actual is plataforma:
                    continue
                if paso > 0:
                    self.rect.right = hitbox.left
                elif paso < 0:
                    self.rect.left = hitbox.right
                self.vel_x = 0.0
                self._resto_x = 0.0
                if self.estado != PERSECUCION:
                    self.direccion *= -1

        estaba_en_suelo = self.en_suelo
        self.rect.y += dy_mov
        self.en_suelo = False
        self.plataforma_actual = None
        for plataforma in plataformas:
            hitbox = self._hitbox(plataforma)
            if self.rect.colliderect(hitbox):
                if dy_mov > 0:
                    self.rect.bottom = hitbox.top
                    self.vel_y = 0
                    self.en_suelo = True
                    self.plataforma_actual = plataforma
                elif dy_mov < 0:
                    self.rect.top = hitbox.bottom
                    self.vel_y = 0

        if self.en_suelo and not estaba_en_suelo:
            self.cuadros_aterrizaje = self.aterrizaje_total
            self._crear_polvo_aterrizaje()
        elif self.cuadros_aterrizaje > 0:
            self.cuadros_aterrizaje -= 1

        self._actualizar_particulas()

        # 7. borde de la plataforma: en vez de girar de golpe, se detiene a mirar
        if (
            self.en_suelo
            and self.estado == PATRULLA
            and self.cuadros_anticipacion == 0
            and self.plataforma_actual is not None
        ):
            borde = self.plataforma_actual.rect
            if (self.rect.right >= borde.right and self.direccion > 0) or (
                self.rect.left <= borde.left and self.direccion < 0
            ):
                self._cambiar(ESPERA)

    # ------------------------------------------------------------------
    # Dibujado
    # ------------------------------------------------------------------
    def dibujar(self, superficie, tiempo):
        cx = self.rect.centerx
        pie_y = self.rect.bottom

        claro = self._tono(1.45)
        base = self._tono(1.0)
        medio = self._tono(0.8)
        oscuro = self._tono(0.55)
        contorno = self._tono(0.18)
        sombra_oscura = self._tono(0.08)

        self._dibujar_sombra(superficie, cx, pie_y)
        self._dibujar_halo(superficie, tiempo)
        self._dibujar_particulas(superficie)

        en_el_aire = not self.en_suelo
        anticipando = self.cuadros_anticipacion > 0
        aterrizando = self.cuadros_aterrizaje > 0 and not en_el_aire
        persiguiendo = self.estado == PERSECUCION
        corriendo = self.en_suelo and abs(self.vel_x) > 0.4

        compresion = 0
        if anticipando:
            compresion = 4
        elif aterrizando:
            compresion = int(6 * self.cuadros_aterrizaje / self.aterrizaje_total)
        estiramiento = 4 if (en_el_aire and self.vel_y < -1) else 0

        alto_cuerpo = self.rect.height - 18 - compresion + estiramiento
        cuerpo_y = pie_y - alto_cuerpo

        s = math.sin(self.fase_paso) if corriendo else 0.0
        rebote = int(round(abs(s) * 2)) if corriendo else 0
        inclinacion = int(round(max(-3.0, min(3.0, self.vel_x))))
        respiracion = int(round(math.sin(tiempo * 2 + self.fase))) if not corriendo else 0

        # --- brazo trasero ---
        balanceo = int(round(3 * s))
        brazo_y_atras = cuerpo_y + 8 - balanceo - (6 if en_el_aire else 0)
        x_atras = cx - 20 if self.direccion > 0 else cx + 14
        self._bloque_contorneado(superficie, x_atras, brazo_y_atras, 6, 20, oscuro, contorno)

        # --- torso ---
        self._bloque_contorneado(
            superficie, cx - 15 + inclinacion // 2, cuerpo_y + 4, 30, alto_cuerpo - 8, base, contorno
        )
        self._bloque(superficie, cx - 9 + inclinacion // 2, cuerpo_y + 12, 18, 4, medio)
        lado_sombra_x = cx + 10 if self.direccion > 0 else cx - 15
        self._bloque(superficie, lado_sombra_x, cuerpo_y + 2, 4, alto_cuerpo - 6, oscuro)
        self._dibujar_grano(superficie, tiempo, cx, cuerpo_y, alto_cuerpo, sombra_oscura)

        # --- piernas ---
        self._dibujar_piernas(
            superficie, cx, cuerpo_y, s, corriendo, medio, oscuro, contorno, en_el_aire, anticipando
        )

        # --- brazo delantero (adelantado al perseguir) ---
        if persiguiendo and not en_el_aire:
            ax = cx + 8 if self.direccion > 0 else cx - 20
            self._bloque_contorneado(superficie, ax, cuerpo_y + 10, 14, 6, oscuro, contorno)
        else:
            x_frente = cx + 14 if self.direccion > 0 else cx - 20
            brazo_y = cuerpo_y + 8 + balanceo - (6 if en_el_aire else 0)
            self._bloque_contorneado(superficie, x_frente, brazo_y, 6, 20, oscuro, contorno)

        # --- cabeza ---
        lado = 22
        cabeza_x = cx - lado // 2 + inclinacion
        cabeza_y = cuerpo_y - lado - 4 - rebote + respiracion
        self._dibujar_cresta(superficie, cabeza_x, cabeza_y, lado, medio, contorno, tiempo)
        self._bloque_contorneado(superficie, cabeza_x, cabeza_y, lado, lado, claro, contorno)
        self._dibujar_ojos(superficie, cabeza_x + lado // 2, cabeza_y, sombra_oscura, contorno)

        # --- señales ---
        self._dibujar_senal(superficie, cabeza_x + lado // 2, cabeza_y, tiempo, contorno)

        # --- glitch ---
        if persiguiendo or self.intensidad_alerta > 0.75:
            self._dibujar_glitch(superficie, tiempo, cx, cabeza_y, pie_y)

    def _dibujar_cresta(self, superficie, x, y, lado, color, contorno, tiempo):
        """Cresta punk: se eriza con la sospecha y se agita al correr."""
        extra = int(8 * self.sospecha)
        temblor = int(round(math.sin(tiempo * 14 + self.fase))) if self.sospecha > 0.5 else 0
        cx = x + lado // 2
        for dx, alto in ((-8, 6), (-4, 10), (0, 14), (4, 10), (8, 6)):
            h = alto + (extra if dx == 0 else extra // 2)
            self._bloque_contorneado(superficie, cx + dx - 2 + temblor, y - h + 2, 4, h, color, contorno)

    def _dibujar_ojos(self, superficie, cx, cabeza_y, hueco, contorno):
        """Dos cuencas oscuras; las pupilas pálidas siguen al objetivo."""
        ey = cabeza_y + 8
        estado = self.estado
        for lado in (-1, 1):
            sx = cx - 10 if lado < 0 else cx + 2
            self._bloque(superficie, sx, ey, 8, 8, hueco)
            px = sx + 2 + int(round(self.mirada_x * 2))
            py = ey + 2 + int(round(self.mirada_y * 2))
            if estado == PERSECUCION:
                self._bloque(superficie, px, py - 2, 4, 8, self.BLANCO)  # pupila encendida
            elif estado in (SOSPECHA, BUSQUEDA):
                self._bloque(superficie, px - 2, py, 8, 4, self.BLANCO)  # ojos muy abiertos
            else:
                self._bloque(superficie, px, py, 4, 4, self._tono(1.2))
        if estado == PERSECUCION:  # ceño fruncido
            for lado in (-1, 1):
                ox = cx - 12 if lado < 0 else cx + 8
                ix = cx - 8 if lado < 0 else cx + 4
                self._bloque(superficie, ox, ey - 8, 4, 4, contorno)
                self._bloque(superficie, ix, ey - 4, 4, 4, contorno)

    def _dibujar_senal(self, superficie, cx, cabeza_y, tiempo, contorno):
        y = cabeza_y - 36 + int(round(2 * math.sin(tiempo * 8)))
        if self.cuadros_exclamacion > 0:
            celdas = [(0, 0), (0, 1), (0, 2), (0, 4)]
            self._glifo(superficie, celdas, cx - 2, y, self.BLANCO, contorno)
        elif self.estado in (SOSPECHA, BUSQUEDA):
            celdas = [(0, 0), (1, 0), (2, 0), (2, 1), (1, 2), (2, 2), (1, 3), (1, 5)]
            self._glifo(superficie, celdas, cx - 6, y, self._tono(1.2), contorno)

    def _dibujar_grano(self, superficie, tiempo, cx, cuerpo_y, alto_cuerpo, color):
        """Puntillismo oscuro que 'hierve' unas 8 veces por segundo."""
        rng = random.Random(self._semilla + int(tiempo * 8))
        for _ in range(7):
            gx = cx - 13 + rng.randrange(0, 26)
            gy = cuerpo_y + 6 + rng.randrange(0, max(1, alto_cuerpo - 12))
            pygame.draw.rect(superficie, color, (gx, gy, 2, 2))

    def _dibujar_glitch(self, superficie, tiempo, cx, cabeza_y, pie_y):
        """Desplaza una franja horizontal de la escena, como interferencia."""
        rng = random.Random(self._semilla * 7 + int(tiempo * 10))
        if rng.random() > 0.3:
            return
        y = rng.randrange(int(cabeza_y), int(pie_y) - 6)
        zona = pygame.Rect(cx - 28, y, 56, rng.choice((4, 8)))
        zona = zona.clip(superficie.get_rect())
        if zona.width < 4 or zona.height < 2:
            return
        franja = superficie.subsurface(zona).copy()
        superficie.blit(franja, (zona.x + rng.choice((-8, -4, 4, 8)), zona.y))

    def _dibujar_piernas(self, superficie, cx, cuerpo_y, s, corriendo, medio, oscuro, contorno, en_el_aire, anticipando):
        ancho = 8
        y_pierna = cuerpo_y + 18

        if en_el_aire:
            for x in (cx - 8, cx):
                self._bloque_contorneado(superficie, x, y_pierna, ancho, 14, medio, contorno)
            return

        alta_izq = alta_der = 22
        if anticipando:
            x_izq, x_der = cx - 14, cx + 6
        elif corriendo:
            desfase = int(round(3 * s))
            x_izq = cx - 11 + desfase
            x_der = cx + 3 - desfase
            alta_izq = 22 - int(round(3 * max(0.0, s)))  # levanta el pie al avanzar
            alta_der = 22 - int(round(3 * max(0.0, -s)))
        else:
            x_izq, x_der = cx - 11, cx + 3

        self._bloque_contorneado(superficie, x_izq, y_pierna, ancho, alta_izq, medio, contorno)
        self._bloque_contorneado(superficie, x_der, y_pierna, ancho, alta_der, medio, contorno)
        self._bloque(superficie, x_izq + 1, y_pierna + alta_izq - 10, 6, 4, oscuro)
        self._bloque(superficie, x_der + 1, y_pierna + alta_der - 10, 6, 4, oscuro)

    def _dibujar_sombra(self, superficie, cx, pie_y):
        ancho = 28 if self.en_suelo else 18
        sombra = pygame.Surface((ancho, 6), pygame.SRCALPHA)
        sombra.fill((0, 0, 0, 110 if self.en_suelo else 70))
        superficie.blit(sombra, sombra.get_rect(center=(cx, pie_y + 2)).topleft)

    def _dibujar_halo(self, superficie, tiempo):
        radio = int(self.rect.height * (0.85 + 0.25 * self.intensidad_alerta))
        velocidad_pulso = 1.4 + 3.2 * self.intensidad_alerta
        pulso = 0.5 + 0.5 * math.sin(tiempo * velocidad_pulso + self.fase)
        capa = pygame.Surface((radio * 2, radio * 2), pygame.SRCALPHA)
        alpha = int(26 + 14 * pulso + 110 * self.intensidad_alerta * pulso)
        pygame.draw.circle(capa, (150, 150, 150, min(255, alpha)), (radio, radio), radio)
        superficie.blit(capa, (self.rect.centerx - radio, self.rect.centery - radio))

    def _dibujar_particulas(self, superficie):
        for p in self._particulas_polvo:
            alpha = int(160 * (p["vida"] / p["vida_max"]))
            capa = pygame.Surface((6, 6), pygame.SRCALPHA)
            pygame.draw.circle(capa, (190, 190, 190, alpha), (3, 3), 3)
            superficie.blit(capa, (p["x"] - 3, p["y"] - 3))


# --------------------------------------------------------------------------
# Coordinación entre entidades
# --------------------------------------------------------------------------
def propagar_alerta(entidades, radio=240):
    """Llamar una vez por cuadro desde juego.py, después de ``mover``.

    Si una entidad está persiguiendo al jugador, las que estén cerca y
    tranquilas reciben la última posición conocida y se unen a la caza.
    """
    for emisora in entidades:
        if emisora.estado != PERSECUCION or emisora.memoria_x is None:
            continue
        for receptora in entidades:
            if receptora is emisora:
                continue
            cerca = math.hypot(
                receptora.rect.centerx - emisora.rect.centerx,
                receptora.rect.centery - emisora.rect.centery,
            ) < radio
            if cerca:
                receptora.recibir_aviso(emisora.memoria_x, emisora.memoria_y)


# --------------------------------------------------------------------------
# Generación por nivel (sin cambios)
# --------------------------------------------------------------------------
def generar_entidades(
    nivel,
    plataformas,
    punto_a_evitar,
    radio_evitar=90,
    velocidad_patrulla=1.8,
    velocidad_persecucion=3.0,
    rango_deteccion=220,
    ancho_pantalla=800,
    alto_pantalla=600,
):
    """Crea las entidades grises para un nivel dado (desde el nivel 3)."""
    if nivel < 3:
        return []

    cantidad = min(1 + (nivel - 3) // 3, 4)

    ancho_entidad = 32
    alto_entidad = 58
    candidatas = [
        plataforma
        for plataforma in plataformas
        if not plataforma.es_trampa
        and plataforma.rect.width >= 40
        and pygame.Vector2(plataforma.rect.center).distance_to(punto_a_evitar) > radio_evitar
        and plataforma.rect.right >= ancho_entidad
        and plataforma.rect.left <= ancho_pantalla - ancho_entidad
        and plataforma.rect.top >= alto_entidad
    ]
    random.shuffle(candidatas)

    entidades = []
    for plataforma in candidatas[:cantidad]:
        x_min = max(0, plataforma.rect.left)
        x_max = min(ancho_pantalla - ancho_entidad, plataforma.rect.right - ancho_entidad)
        x = max(x_min, min(plataforma.rect.centerx - ancho_entidad // 2, x_max))
        y = plataforma.rect.top - alto_entidad
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