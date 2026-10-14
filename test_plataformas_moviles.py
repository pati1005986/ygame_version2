import pygame

from enemigo import EntidadGris, ESPERA, generar_entidades
from plataformas import Plataforma


def test_enemigo_acompana_plataforma_vertical_y_se_mantiene_apoyado():
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
    enemigo = EntidadGris(80, plataforma.rect.top - 58)
    enemigo.estado = ESPERA
    enemigo.cuadros_estado = 100
    enemigo.en_suelo = True
    enemigo.plataforma_actual = plataforma

    plataforma.rect.y += 12
    plataforma.desplazamiento_reciente = pygame.Vector2(0, 12)
    enemigo.mover([plataforma])

    assert enemigo.rect.bottom == plataforma.rect.top
    assert enemigo.en_suelo
    assert enemigo.plataforma_actual is plataforma


def test_enemigo_generado_sobre_plataforma_inicia_apoyado():
    plataforma = Plataforma(
        100,
        300,
        100,
        20,
        0.2,
        patron_movimiento="vertical",
    )

    entidades = generar_entidades(
        3,
        [plataforma],
        pygame.Vector2(0, 0),
        radio_evitar=0,
    )

    assert len(entidades) == 1
    assert entidades[0].en_suelo
    assert entidades[0].plataforma_actual is plataforma
    assert entidades[0].rect.bottom == plataforma.rect.top
