from types import SimpleNamespace

import pygame

from plataformas import Plataforma
from personaje import PersonajeHumanoide
from transicion import TransicionCaricaturesca
from idioma import alternar_idioma, texto
from eventos import procesar_eventos
from opciones import (
    MenuOpciones,
    cargar_configuracion,
    guardar_configuracion,
    normalizar_configuracion,
)


def test_transicion_se_pone_triste_a_partir_del_nivel_10():
    nivel_9 = TransicionCaricaturesca(
        (255, 255, 255),
        (0, 0, 0),
        (100, 100),
        (200, 200),
        nivel=9,
    )
    nivel_10 = TransicionCaricaturesca(
        (255, 255, 255),
        (0, 0, 0),
        (100, 100),
        (200, 200),
        nivel=10,
    )
    nivel_18 = TransicionCaricaturesca(
        (255, 255, 255),
        (0, 0, 0),
        (100, 100),
        (200, 200),
        nivel=18,
    )
    assert nivel_9.nivel == 9
    assert nivel_9.tristeza == 0.0
    assert nivel_10.nivel == 10
    assert nivel_10.tristeza == 0.0
    assert nivel_18.nivel == 18
    assert nivel_18.tristeza == 1.0


def test_alternar_idioma_incluye_portugues_y_ruso():
    assert alternar_idioma("en") == "es"
    assert alternar_idioma("es") == "pt"
    assert alternar_idioma("pt") == "ru"
    assert alternar_idioma("ru") == "en"


def test_textos_de_nuevos_idiomas():
    assert texto("pt", "play") == "JOGAR"
    assert texto("ru", "options") == "ОПЦИИ"
    assert texto("pt", "language") == "IDIOMA"
    assert texto("ru", "language") == "ЯЗЫК"


def test_textos_de_opciones_nuevas():
    assert texto("en", "music") == "MUSIC"
    assert texto("es", "effects") == "EFECTOS"
    assert texto("es", "reset_defaults") == "RESTAURAR PREDETERMINADO"


def test_guardar_y_cargar_configuracion_persistente(tmp_path):
    ruta = tmp_path / "config_guardada.json"
    configuracion = {
        "resoluciones": MenuOpciones.RESOLUCIONES,
        "resolucion": 1,
        "pantalla_completa": True,
        "idioma": "pt",
        "volumen_musica": 0.35,
        "volumen_efectos": 0.65,
        "controles": {
            "left": pygame.K_q,
            "right": pygame.K_e,
            "jump": pygame.K_w,
            "down": pygame.K_x,
            "dash": pygame.K_LCTRL,
        },
    }

    guardar_configuracion(configuracion, ruta)
    cargada = cargar_configuracion(ruta)

    assert cargada["idioma"] == "pt"
    assert cargada["volumen_musica"] == 0.35
    assert cargada["volumen_efectos"] == 0.65
    assert cargada["controles"]["jump"] == pygame.K_w
    assert cargada["controles"]["dash"] == pygame.K_LCTRL
    assert cargada["resolucion"] == 1
    assert cargada["pantalla_completa"] is True


def test_control_dash_se_puede_reasignar_en_opciones():
    pygame.font.init()
    configuracion = normalizar_configuracion({})
    opciones = MenuOpciones(800, 600, configuracion)
    boton_dash = opciones.botones_controles["dash"]

    opciones.manejar_evento(
        pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=pygame.BUTTON_LEFT,
            pos=boton_dash.center,
        )
    )
    assert opciones.tecla_esperada == "dash"

    opciones.manejar_evento(
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_q)
    )

    assert configuracion["controles"]["dash"] == pygame.K_q
    assert opciones.tecla_esperada is None


def test_control_dash_reasignado_activa_dash():
    llamadas = []
    contexto = SimpleNamespace(
        estado="jugando",
        jugador=SimpleNamespace(solicitar_dash=lambda: llamadas.append(True)),
        jugando=True,
    )
    dependencias = SimpleNamespace(
        configuracion={
            "controles": {"jump": pygame.K_SPACE, "dash": pygame.K_q}
        },
        pausa=None,
    )

    procesar_eventos(
        [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LSHIFT)],
        contexto,
        dependencias,
    )
    assert llamadas == []

    procesar_eventos(
        [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_q)],
        contexto,
        dependencias,
    )
    assert llamadas == [True]


def test_jugador_se_mueve_con_plataforma_vertical():
    plataforma = Plataforma(
        30,
        250,
        140,
        18,
        0.2,
        patron_movimiento="vertical",
        amplitud_movimiento=12,
        velocidad_movimiento=0.0,
    )
    plataforma.rect.y = 250
    plataforma.desplazamiento_reciente = pygame.Vector2(0, 12)

    jugador = PersonajeHumanoide(60, 160, (255, 255, 255))
    jugador.rect.bottom = plataforma.rect.top
    jugador.en_suelo = True
    jugador.plataforma_actual = plataforma
    y_antes = jugador.rect.y

    jugador.mover(
        [plataforma],
        {"left": pygame.K_a, "right": pygame.K_d, "down": pygame.K_s},
    )

    assert jugador.rect.y > y_antes
    assert jugador.rect.bottom >= plataforma.rect.top - 1


def test_plataforma_trampa_tiene_hitbox_reducida():
    plataforma = Plataforma(20, 200, 160, 25, 0.2, es_trampa=True)

    hitbox = plataforma.rect_colision()

    assert hitbox.width < plataforma.rect.width
    assert hitbox.height < plataforma.rect.height
    assert hitbox.bottom <= plataforma.rect.bottom


def test_jugador_puede_saltar_agachado(monkeypatch):
    class TeclasFalsas:
        def __getitem__(self, tecla):
            return tecla == pygame.K_s

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: TeclasFalsas())
    jugador = PersonajeHumanoide(60, 160, (255, 255, 255))
    jugador.en_suelo = True
    jugador.solicitar_salto()

    jugador.mover(
        [],
        {"left": pygame.K_a, "right": pygame.K_d, "down": pygame.K_s},
    )

    assert jugador.agachado
    assert jugador.rect.height == jugador.altura_agachado
    assert jugador.vel_y < 0
