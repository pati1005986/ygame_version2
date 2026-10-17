"""Seguimiento del combo de trucos (saltos en el aire y dashes)."""

DURACION_COMBO_MS = 2000


class Combo:
    def __init__(self):
        self.reiniciar()

    def reiniciar(self):
        self.actual = 0
        self.mejor_nivel = 0
        self.expira = 0

    def reiniciar_mejor_nivel(self):
        """Reinicia el récord del nivel sin cortar la racha activa."""
        self.mejor_nivel = 0

    def registrar(self, ahora_ms):
        """Suma un truco; si el combo ya había expirado, empieza de cero."""
        if ahora_ms > self.expira:
            self.actual = 0
        self.actual += 1
        self.mejor_nivel = max(self.mejor_nivel, self.actual)
        self.expira = ahora_ms + DURACION_COMBO_MS

    def actualizar(self, ahora_ms):
        if self.actual and ahora_ms > self.expira:
            self.actual = 0

    def visible(self, tiempo_s):
        """Valor del combo a mostrar en el HUD (0 si ya expiró)."""
        return self.actual if tiempo_s * 1000 <= self.expira else 0