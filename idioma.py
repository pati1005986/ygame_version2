TRADUCCIONES = {
    "en": {
        "play": "PLAY",
        "options": "OPTIONS",
        "exit": "EXIT",
        "resolution": "RESOLUTION",
        "language": "LANGUAGE",
        "english": "ENGLISH",
        "spanish": "SPANISH",
        "move_left": "MOVE LEFT",
        "move_right": "MOVE RIGHT",
        "jump": "JUMP",
        "crouch": "CROUCH",
        "press_key": "PRESS A KEY... ESC CANCELS",
        "back": "BACK",
        "apply": "APPLY",
        "retry": "RETRY",
        "level": "LEVEL",
        "window_title": "Procedural Platforms - Abstract Canvas",
    },
    "es": {
        "play": "JUGAR",
        "options": "OPCIONES",
        "exit": "SALIR",
        "resolution": "RESOLUCION",
        "language": "IDIOMA",
        "english": "INGLES",
        "spanish": "ESPANOL",
        "move_left": "MOVER IZQUIERDA",
        "move_right": "MOVER DERECHA",
        "jump": "SALTAR",
        "crouch": "AGACHARSE",
        "press_key": "PULSA UNA TECLA... ESC CANCELA",
        "back": "VOLVER",
        "apply": "APLICAR",
        "retry": "REINTENTAR",
        "level": "NIVEL",
        "window_title": "Plataformas Procedurales - Lienzo Abstracto",
    },
}


def texto(idioma, clave):
    return TRADUCCIONES.get(idioma, TRADUCCIONES["en"])[clave]


def alternar_idioma(idioma):
    return "es" if idioma == "en" else "en"
