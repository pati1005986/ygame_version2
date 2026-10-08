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

    Hasta el nivel 30 la curva sube linealmente hasta sus tope. A partir de
    ahí, el juego vuelve a la línea base del nivel 1 y luego se hace más
    fácil progresivamente para relajar la experiencia en niveles muy altos.
    """
    if nivel <= 30:
        progreso = max(0, nivel - 1)
        factor = 1.0
    else:
        # Desde el nivel 30 se reinicia a la dificultad del nivel 1; a partir
        # de ahí baja suavemente para que quede todo mucho más cómodo.
        progreso = 0
        factor = max(0.45, 1.0 - (nivel - 30) * 0.08)

    jugador_base = 6.0 + progreso * 0.12
    gravedad_base = 0.6 + progreso * 0.018
    prob_movil_base = 0.20 + progreso * 0.015
    patrulla_base = 1.8 + progreso * 0.05
    persecucion_base = 3.0 + progreso * 0.08
    rango_base = 220 + progreso * 4

    return {
        # Jugador: a partir del 30 vuelve a la línea base y luego se relaja.
        "velocidad_jugador": min(jugador_base * factor, 8.5),
        "gravedad_jugador": min(gravedad_base * factor, 0.9),
        # Plataformas y enemigos vuelven a ser mucho más suaves desde el 30.
        "probabilidad_plataforma_movil": min(prob_movil_base * factor, 0.55),
        "velocidad_enemigo_patrulla": min(patrulla_base * factor, 3.2),
        "velocidad_enemigo_persecucion": min(persecucion_base * factor, 5.0),
        "rango_deteccion_enemigo": min(rango_base * factor, 320),
    }