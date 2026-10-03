"""
Animación en pygame (solo código, sin imágenes): el personaje sale de un trance.

Línea de tiempo (9 s en total):
    0.0 - 2.2 s  trance: ojos cerrados, cabeza caída, respiración lenta, ondas de fondo
    2.2 - 3.4 s  los párpados tiemblan (dos espasmos)
    3.4 - 5.4 s  abre los ojos poco a poco y levanta la cabeza
    5.5 s        parpadeo
    5.9 - 8.1 s  mira a la izquierda, a la derecha y al frente (ya despierto)

Para usarla como intro de tu juego:
    from despertar import play_wake_animation
    play_wake_animation(screen)          # devuelve True si terminó
"""
import math
import pygame

# ----------------------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------------------
BASE_W, BASE_H = 1200, 890          # sistema de coordenadas con el que se definió el dibujo
LOW_W, LOW_H = 320, 238             # resolución interna (look pixel-art)
S = LOW_W / BASE_W
DURATION = 9.0                      # segundos (mínimo pedido: 5)

BG = (234, 240, 216)
INK = (27, 27, 40)
SHADE = (150, 160, 180)
WHITE = (246, 248, 238, 255)
RING = (205, 213, 196)

HEAD_PIVOT = (450, 640)


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def lerp(a, b, u):
    return a + (b - a) * u


def smooth(u):
    u = clamp(u)
    return u * u * (3 - 2 * u)


def mix(c1, c2, u):
    return tuple(int(lerp(a, b, u)) for a, b in zip(c1, c2))


def keyframes(t, kfs):
    """Interpola suavemente entre pares (tiempo, valor)."""
    if t <= kfs[0][0]:
        return kfs[0][1]
    for (t0, v0), (t1, v1) in zip(kfs, kfs[1:]):
        if t <= t1:
            return lerp(v0, v1, smooth((t - t0) / (t1 - t0)))
    return kfs[-1][1]


def chaikin(pts, closed=False, it=2):
    """Suaviza una poligonal para que los trazos se vean curvos."""
    for _ in range(it):
        n = len(pts)
        new = [] if closed else [pts[0]]
        for i in range(n if closed else n - 1):
            a, b = pts[i], pts[(i + 1) % n]
            new.append((0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]))
            new.append((0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1]))
        if not closed:
            new.append(pts[-1])
        pts = new
    return pts


def quad(p0, c, p1, n=14):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, d = (1 - t) ** 2, 2 * (1 - t) * t, t * t
        out.append((a * p0[0] + b * c[0] + d * p1[0], a * p0[1] + b * c[1] + d * p1[1]))
    return out


def blob(cx, cy, rx, ry, n=18):
    return [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n))
            for i in range(n)]


def make_xf(angle_deg, dx, dy, pivot):
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    px, py = pivot

    def xf(p):
        x, y = p[0] - px, p[1] - py
        return (px + x * c - y * s + dx, py + x * s + y * c + dy)
    return xf


def to_low(pts, xf, off=(0, 0)):
    out = []
    for p in pts:
        x, y = xf(p)
        out.append(((x + off[0]) * S, (y + off[1]) * S))
    return out


def stroke(surf, pts, xf, w=2, color=INK, off=(0, 0)):
    pygame.draw.lines(surf, color, False, to_low(pts, xf, off), w)


def fill(surf, pts, xf, color):
    pygame.draw.polygon(surf, color, to_low(pts, xf))


# ----------------------------------------------------------------------------
# Geometría del personaje (coordenadas base 1200x890)
# ----------------------------------------------------------------------------
HEAD = chaikin([(385, 205), (440, 168), (520, 157), (585, 176), (650, 215), (700, 260),
                (730, 320), (738, 385), (725, 450), (700, 505), (650, 555), (590, 578),
                (520, 580), (450, 562), (385, 540), (340, 490), (318, 430), (312, 370),
                (300, 320), (330, 250)], closed=True)

BODY = chaikin([(40, 900), (70, 790), (120, 690), (200, 655), (300, 640), (370, 630),
                (430, 652), (490, 678), (540, 720), (580, 790), (600, 900)])
NECK = [(385, 540), (380, 600), (370, 632), (430, 652), (490, 678), (525, 590), (520, 555)]
NECK_L = [(385, 535), (380, 600), (370, 632)]
NECK_R = [(525, 590), (508, 640), (490, 678)]
COLLAR = [(370, 632), (430, 650), (490, 678)]
BODY_MARK = [(205, 830), (190, 855), (175, 878)]

EAR_R = chaikin([(738, 375), (768, 380), (776, 440), (765, 500), (722, 535)])
EAR_L = chaikin([(315, 380), (292, 378), (280, 420), (275, 455)])

HAIR_RAW = [
    [(310, 105), (380, 112), (440, 95), (480, 65), (550, 65), (600, 130)],
    [(295, 128), (360, 145), (440, 125), (520, 115)],
    [(270, 160), (320, 175), (370, 185)],
    [(245, 222), (300, 212)],
    [(240, 260), (205, 300), (190, 350), (200, 400)],
    [(280, 275), (255, 300), (245, 360)],
    [(600, 170), (650, 135), (710, 150), (740, 200), (770, 270), (795, 300)],
    [(650, 185), (710, 190), (750, 240), (790, 320), (830, 355)],
    [(680, 110), (740, 125), (790, 160), (820, 220), (838, 270)],
    [(795, 405), (800, 450), (795, 510)],
    [(822, 415), (825, 460), (820, 505)],
    [(295, 480), (280, 520), (280, 535)],
    [(335, 490), (322, 530), (325, 552)],
    [(270, 608), (320, 606), (350, 590), (360, 525)],
    [(555, 620), (600, 632), (632, 636)],
    [(500, 650), (540, 668), (612, 660)],
    [(660, 610), (700, 618), (735, 603)],
]
HAIR = [chaikin(h) for h in HAIR_RAW]

# manchas de sombra en la cara
BLOTS = [blob(478, 268, 44, 46), blob(605, 320, 38, 72), blob(525, 395, 40, 28),
         blob(487, 490, 22, 30), blob(348, 285, 20, 62)]
EAR_BLOT = blob(742, 455, 14, 52)

NOSE_A = [(525, 344), (566, 357)]
NOSE_B = chaikin([(498, 372), (530, 396), (565, 386), (572, 362)])
MOUTH_A = chaikin([(470, 436), (510, 433), (548, 470)])
MOUTH_B = chaikin([(455, 466), (490, 478), (518, 515)])

EYE_L = ((412, 272), (515, 306))
EYE_R = ((585, 318), (672, 360))


# ----------------------------------------------------------------------------
# Estado de la animación en el tiempo t
# ----------------------------------------------------------------------------
def blink_amount(t):
    if t < 5.5:
        return 0.0
    ph = (t - 5.5) % 3.2
    return math.sin(math.pi * ph / 0.3) if ph < 0.3 else 0.0


def state(t):
    # apertura de los ojos (0 cerrados, 1 abiertos)
    if t < 2.2:
        o = 0.0
    elif t < 3.4:
        o = 0.16 * abs(math.sin((t - 2.2) * math.pi / 0.6))   # dos espasmos
    elif t < 5.4:
        o = smooth((t - 3.4) / 2.0)
    else:
        o = 1.0
    o *= 1 - 0.95 * blink_amount(t)

    droop = 1 - smooth((t - 3.0) / 2.6)          # 1 = cabeza caída, 0 = erguida
    jolt = 5 * math.sin(math.pi * clamp((t - 3.2) / 0.5))
    sway = 1.3 * math.sin(0.9 * (t - 5.8)) if t > 5.8 else 0.0
    angle = droop * (10 + 3 * math.sin(1.3 * t)) - jolt + sway

    wander = 1 - smooth((t - 4.6) / 1.2)
    gx = keyframes(t, [(0, 0), (5.9, 0), (6.6, -14), (6.7, -14), (7.2, 13), (7.7, 13), (8.2, 0)])
    gx += wander * 10 * math.sin(t * 0.9)
    gy = wander * 6 * math.sin(t * 1.7)

    focus = smooth((t - 5.0) / 1.5)
    breath = math.sin(t * lerp(1.5, 2.4, 1 - droop))

    return dict(o=o, droop=droop, angle=angle, gaze=(gx, gy), focus=focus, breath=breath)


# ----------------------------------------------------------------------------
# Dibujo
# ----------------------------------------------------------------------------
def draw_eye(low, eye, o, gaze, focus, xf):
    p0, p1 = eye
    vx, vy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(vx, vy)
    nx, ny = -vy / L, vx / L                       # normal apuntando hacia abajo
    mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)

    up_sag = lerp(38, -70, o)                      # párpado superior
    low_sag = lerp(38, 22, o)                      # párpado inferior
    up = quad(p0, (mid[0] + nx * up_sag, mid[1] + ny * up_sag), p1)
    lo = quad(p0, (mid[0] + nx * low_sag, mid[1] + ny * low_sag), p1)

    if o > 0.03:
        poly = to_low(up, xf) + to_low(lo[::-1], xf)
        layer = pygame.Surface((LOW_W, LOW_H), pygame.SRCALPHA)
        mask = pygame.Surface((LOW_W, LOW_H), pygame.SRCALPHA)
        pygame.draw.polygon(layer, WHITE, poly)

        k = (up_sag + low_sag) / 4
        cx, cy = mid[0] + nx * k + gaze[0], mid[1] + ny * k + gaze[1]
        (px, py), = to_low([(cx, cy)], xf)
        r = lerp(20, 14, focus) * S
        pygame.draw.circle(layer, INK, (px, py), r)
        pygame.draw.circle(layer, WHITE, (px - 1.4, py - 1.4), max(1.0, r * 0.28))

        pygame.draw.polygon(mask, (255, 255, 255, 255), poly)
        layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)   # recorta al ojo
        low.blit(layer, (0, 0))

    stroke(low, up, xf, 2)
    if o > 0.15:
        stroke(low, lo, xf, 1)

    # ceja
    h = lerp(58, 82, o)
    bc = (mid[0] - nx * h, mid[1] - ny * h)
    ux, uy = vx / L, vy / L
    pa = (bc[0] - ux * 40, bc[1] - uy * 40)
    pb = (bc[0] + ux * 45, bc[1] + uy * 45)
    stroke(low, chaikin([pa, (bc[0] - nx * 6, bc[1] - ny * 6), pb]), xf, 2)


def render(low, t):
    st = state(t)
    droop, o = st["droop"], st["o"]
    low.fill(BG)

    # ondas del trance (se desvanecen al despertar)
    if droop > 0.02:
        col = mix(BG, RING, droop)
        cx, cy = to_low([(520, 370)], lambda p: p)[0]
        for i in range(6):
            r = (t * 22 + i * 38) % 228 + 8
            pygame.draw.circle(low, col, (cx, cy), r, 1)

    breath = st["breath"]
    body_xf = make_xf(0, 0, breath * 1.5, (450, 680))
    neck_xf = make_xf(st["angle"] * 0.35, 0, breath * 1.5 + droop * 3, (450, 690))
    head_xf = make_xf(st["angle"], breath * 0.8, breath * 2 + droop * 8, HEAD_PIVOT)

    # cuerpo y cuello
    fill(low, BODY + [(600, 920), (40, 920)], body_xf, SHADE)
    stroke(low, BODY, body_xf, 2)
    stroke(low, COLLAR, body_xf, 2)
    stroke(low, BODY_MARK, body_xf, 2)
    fill(low, NECK, neck_xf, SHADE)
    stroke(low, NECK_L, neck_xf, 2)
    stroke(low, NECK_R, neck_xf, 2)

    # cabeza
    fill(low, HEAD, head_xf, BG)
    for b in BLOTS:
        fill(low, b, head_xf, SHADE)
    fill(low, EAR_BLOT, head_xf, SHADE)
    stroke(low, HEAD + [HEAD[0]], head_xf, 2)
    stroke(low, EAR_R, head_xf, 2)
    stroke(low, EAR_L, head_xf, 2)

    # ojos
    draw_eye(low, EYE_L, o, st["gaze"], st["focus"], head_xf)
    draw_eye(low, EYE_R, o, st["gaze"], st["focus"], head_xf)

    # nariz y boca (la boca se entreabre un poco al despertar)
    stroke(low, NOSE_A, head_xf, 2)
    stroke(low, NOSE_B, head_xf, 2)
    open_mouth = (1 - droop) * 5 * (0.5 + 0.5 * math.sin(t * 2.4))
    stroke(low, MOUTH_A, head_xf, 2)
    stroke(low, MOUTH_B, head_xf, 2, off=(0, open_mouth))

    # pelo que se mece
    for i, h in enumerate(HAIR):
        off = (2.5 * math.sin(t * 1.6 + i * 0.9), 2.0 * math.sin(t * 1.3 + i * 1.7))
        stroke(low, h, head_xf, 2, off=off)

    # viñeta oscura mientras dura el trance + fundido inicial desde negro
    dark = max(droop * 0.38, 1 - smooth(t / 0.7))
    if dark > 0.01:
        veil = pygame.Surface((LOW_W, LOW_H))
        veil.fill((20, 25, 45))
        veil.set_alpha(int(255 * dark))
        low.blit(veil, (0, 0))


def draw_frame(screen, low, t):
    render(low, t)
    sw, sh = screen.get_size()
    sc = min(sw / LOW_W, sh / LOW_H)
    w, h = int(LOW_W * sc), int(LOW_H * sc)
    screen.fill(BG)
    screen.blit(pygame.transform.scale(low, (w, h)), ((sw - w) // 2, (sh - h) // 2))


def play_wake_animation(
    screen, clock=None, duration=DURATION, exit_text="EXIT", exit_delay=5.0
):
    """Reproduce la animación; muestra el botón para cerrarla tras `exit_delay`."""
    clock = clock or pygame.time.Clock()
    low = pygame.Surface((LOW_W, LOW_H))
    t0 = pygame.time.get_ticks()
    while True:
        t = (pygame.time.get_ticks() - t0) / 1000
        exit_button = None
        exit_surface = None
        if t >= exit_delay:
            sw, sh = screen.get_size()
            escala = min(sw / LOW_W, sh / LOW_H)
            fuente = pygame.font.SysFont(None, max(18, round(26 * escala)), bold=True)
            exit_surface = fuente.render(exit_text, True, (255, 255, 255))
            ancho = exit_surface.get_width() + 36
            alto = exit_surface.get_height() + 20
            exit_button = pygame.Rect(0, 0, ancho, alto)
            exit_button.center = (sw // 2, sh - max(38, alto // 2 + 16))
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.event.post(e)
                return False
            if (
                e.type == pygame.MOUSEBUTTONDOWN
                and e.button == pygame.BUTTON_LEFT
                and exit_button is not None
                and exit_button.collidepoint(e.pos)
            ):
                return False
        if t >= duration:
            return True
        draw_frame(screen, low, t)
        if exit_button is not None:
            hover = exit_button.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(
            screen, (105, 44, 58) if hover else (62, 38, 48),
            exit_button, border_radius=8,
            )
            pygame.draw.rect(screen, (245, 220, 190), exit_button, 2, border_radius=8)
            screen.blit(exit_surface, exit_surface.get_rect(center=exit_button.center))
        pygame.display.flip()
        clock.tick(60)


def main():
    pygame.init()
    screen = pygame.display.set_mode((960, 714), pygame.RESIZABLE)
    pygame.display.set_caption("Despertar")
    play_wake_animation(screen)
    pygame.quit()


if __name__ == "__main__":
    main()