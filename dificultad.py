"""Curva de dificultad centralizada.

Antes, cada sistema decidía por su cuenta cómo escalar con el nivel:
``ajustar_dificultad_jugador`` (en ``juego.py``) subía la velocidad y la
gravedad del jugador, pero la probabilidad de que una plataforma se
moviera (``Plataforma.PROBABILIDAD_MOVIMIENTO``) y la velocidad de los
enemigos (``EntidadGris.velocidad_patrulla`` / ``velocidad_persecucion``)
se quedaban fijas para siempre. El resultado con el tiempo: el jugador se
vuelve más rápido nivel a nivel, pero los enemigos no lo acompañan, así
que dejan de sentirse amenazantes exactamente cuando el juego "cree" que
se está poniendo más difícil.

``parametros_dificultad(nivel)`` es el único lugar donde vive esa curva.
Todo lo demás (``generar_nivel`` y ``ajustar_dificultad_jugador`` en
``juego.py``, ``generar_entidades`` en ``enemigo.py``) le pide los
valores a esta función en vez de tener su propia fórmula suelta. Para
ajustar el ritmo del juego, este es el archivo que hay que tocar.

Cada valor tiene un techo (``min(..., tope)``) para que la dificultad se
estabilice en partidas muy largas en vez de crecer sin límite.
"""


def parametros_dificultad(nivel):
    """Devuelve los parámetros de dificultad para ``nivel``.

    ``nivel`` 1 siempre da los valores base (progreso 0); a partir de ahí
    todo escala linealmente hasta su tope.
    """
    progreso = max(0, nivel - 1)
    return {
        # Jugador (ver ajustar_dificultad_jugador en juego.py). Estos dos
        # valores ya existían; se centralizan aquí sin cambiar el ritmo.
        "velocidad_jugador": min(6.0 + progreso * 0.12, 8.5),
        "gravedad_jugador": min(0.6 + progreso * 0.018, 0.9),
        # Plataformas móviles (ver Plataforma en plataformas.py). Antes
        # era un 35% fijo en todos los niveles; ahora empieza más suave y
        # termina más exigente.
        "probabilidad_plataforma_movil": min(0.20 + progreso * 0.015, 0.55),
        # Enemigos (ver EntidadGris y generar_entidades en enemigo.py).
        # Crecen a un ritmo comparable al del jugador para que perseguir
        # siga siendo una amenaza real en niveles altos, en vez de
        # quedarse atrás mientras el jugador se vuelve más rápido.
        "velocidad_enemigo_patrulla": min(1.8 + progreso * 0.05, 3.2),
        "velocidad_enemigo_persecucion": min(3.0 + progreso * 0.08, 5.0),
        "rango_deteccion_enemigo": min(220 + progreso * 4, 320),
    }