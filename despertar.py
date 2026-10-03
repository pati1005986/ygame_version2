"""
Animación en pygame (solo código, sin imágenes): el despertar tras una adicción.

Idea visual
    La primera mitad es el TRANCE: un mundo gris-verdoso y enfermizo, una espiral
    hipnótica que gira, hilos oscuros (como de marioneta) que sujetan la cabeza,
    ojeras, ojos inyectados en sangre, grano de TV, aberración cromática y una
    viñeta que late como un corazón lento.
    El momento clave es la RUPTURA: los hilos se rompen, la espiral estalla en
    fragmentos, un destello blanco, una gran bocanada de aire... y el color VUELVE
    (piel, ojos, fondo), la luz del amanecer entra, la pupila se contrae y cae
    una lágrima de alivio.

Secuencia inicial (9 s; después la respiración, el parpadeo y el ambiente siguen):
    0.0 - 2.2 s  trance: ojos cerrados, cabeza caída, espiral, hilos, glitch
    2.2 - 3.3 s  los párpados tiemblan, los hilos se tensan
    3.3 s        RUPTURA: hilos rotos, destello, la espiral estalla, bocanada
    3.4 - 5.4 s  abre los ojos y levanta la cabeza; el color regresa
    5.5 s        parpadeo
    4.6 - 7 s    una lágrima de alivio
    5.9 - 8.1 s  mira a izquierda, derecha y al frente, ya despierto

Para usarla como intro de tu juego:
    from despertar import play_wake_animation
    play_wake_animation(screen)          # permanece activa hasta pulsar «Salir»
"""
import math
import random
import pygame

# ----------------------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------------------
BASE_W, BASE_H = 1200, 890          # sistema de coordenadas con el que se definió el dibujo
LOW_W, LOW_H = 320, 238             # resolución interna (look pixel-art)
S = LOW_W / BASE_W
BG = (244, 236, 212)                # piel despierta (cálida)
INK = (27, 27, 40)
SHADE = (176, 166, 184)             # sombras despiertas
SKIN_SICK = (168, 184, 166)         # piel pálida / verdosa del trance
SHADE_SICK = (88, 98, 108)
WHITE = (246, 248, 238, 255)
WHITE_SICK = (232, 190, 190)        # ojo inyectado en sangre
NIGHT_TOP = (16, 14, 26)
NIGHT_BOTTOM = (46, 52, 44)
DAWN_TOP = (62, 72, 112)
DAWN_BOTTOM = (238, 166, 112)
T_SNAP = 3.3                        # instante de la ruptura

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

    # sick: 1 = atrapado por la adicción, 0 = libre (el color vuelve poco a poco)
    sick = 1.0 if t < T_SNAP else 1 - smooth((t - T_SNAP) / 2.8)
    awake = 1 - sick
    dt = t - T_SNAP
    flash = math.exp(-dt * 7) if dt >= 0 else 0.0
    gasp = math.sin(math.pi * clamp(dt / 0.9)) if dt >= 0 else 0.0

    # latido: lento y pesado en el trance, más vivo al despertar
    rate = lerp(1.0, 1.5, awake)
    ph = (t * rate) % 1.0
    beat = math.exp(-ph * 10) + 0.55 * math.exp(-((ph - 0.3) % 1.0) * 12)

    droop = 1 - smooth((t - 3.0) / 2.6)          # 1 = cabeza caída, 0 = erguida
    jolt = 5 * math.sin(math.pi * clamp((t - 3.2) / 0.5))
    sway = 1.3 * math.sin(0.9 * (t - 5.8)) if t > 5.8 else 0.0
    tremor = 0.7 * sick * math.sin(t * 37) * smooth((t - 1.0) / 1.5)   # temblor del síndrome
    angle = droop * (10 + 3 * math.sin(1.3 * t)) - jolt + sway + tremor

    wander = 1 - smooth((t - 4.6) / 1.2)
    gx = keyframes(t, [(0, 0), (5.9, 0), (6.6, -14), (6.7, -14), (7.2, 13), (7.7, 13), (8.2, 0)])
    gx += wander * 10 * math.sin(t * 0.9)
    gy = wander * 6 * math.sin(t * 1.7)

    focus = smooth((t - 5.0) / 1.5)
    breath = math.sin(t * lerp(1.5, 2.4, 1 - droop))

    return dict(
        o=o, droop=droop, angle=angle, gaze=(gx, gy), focus=focus, breath=breath,
        sick=sick, awake=awake, flash=flash, gasp=gasp, beat=beat,
        skin=mix(SKIN_SICK, BG, awake),
        shade=mix(SHADE_SICK, SHADE, awake),
        white=mix(WHITE_SICK, WHITE[:3], awake) + (255,),
    )


# ----------------------------------------------------------------------------
# Dibujo
# ----------------------------------------------------------------------------
def draw_eye(low, eye, o, gaze, st, xf):
    sick = st["sick"]
    p0, p1 = eye
    vx, vy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(vx, vy)
    nx, ny = -vy / L, vx / L                       # normal apuntando hacia abajo
    mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)

    up_sag = lerp(38, -70, o)                      # párpado superior
    low_sag = lerp(38, 22, o)                      # párpado inferior
    up = quad(p0, (mid[0] + nx * up_sag, mid[1] + ny * up_sag), p1)
    lo = quad(p0, (mid[0] + nx * low_sag, mid[1] + ny * low_sag), p1)

    # ojeras: media luna morada bajo el ojo que se desvanece al despertar
    if sick > 0.03:
        bag = quad((p0[0] + nx * 6, p0[1] + ny * 6),
                   (mid[0] + nx * (low_sag + 62), mid[1] + ny * (low_sag + 62)),
                   (p1[0] + nx * 6, p1[1] + ny * 6))
        bag_col = mix(st["skin"], (92, 70, 112), 0.62 * sick)
        pygame.draw.polygon(low, bag_col, to_low(lo, xf) + to_low(bag[::-1], xf))

    if o > 0.03:
        poly = to_low(up, xf) + to_low(lo[::-1], xf)
        layer = pygame.Surface((LOW_W, LOW_H), pygame.SRCALPHA)
        mask = pygame.Surface((LOW_W, LOW_H), pygame.SRCALPHA)
        pygame.draw.polygon(layer, st["white"], poly)

        # venitas rojas del ojo cansado
        if sick > 0.08:
            vein = (205, 70, 82, int(230 * sick))
            for (qx, qy), sgn in ((p0, 1), (p1, -1)):
                for k in (-0.16, 0.16):
                    s = (qx + nx * (low_sag * 0.3), qy + ny * (low_sag * 0.3))
                    e = (s[0] + sgn * vx * 0.38 / 1.0, s[1] + sgn * vy * 0.38 + k * L)
                    (a1, a2) = to_low([s, e], xf)
                    pygame.draw.line(layer, vein, a1, a2, 1)

        k = (up_sag + low_sag) / 4
        cx, cy = mid[0] + nx * k + gaze[0], mid[1] + ny * k + gaze[1]
        (px, py), = to_low([(cx, cy)], xf)
        # pupila dilatada en el trance; se contrae con la luz
        r = lerp(13, 23, sick) * S
        pygame.draw.circle(layer, INK, (px, py), r)
        pygame.draw.circle(layer, WHITE, (px - 1.4, py - 1.4), max(1.0, r * 0.28))

        pygame.draw.polygon(mask, (255, 255, 255, 255), poly)
        layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)   # recorta al ojo
        low.blit(layer, (0, 0))

    stroke(low, up, xf, 2)
    if o > 0.15:
        stroke(low, lo, xf, 1)

    # ceja (caída y tensa en el trance, arqueada al despertar)
    h = lerp(58, 82, o) + 6 * (1 - sick) * o
    bc = (mid[0] - nx * h, mid[1] - ny * h)
    ux, uy = vx / L, vy / L
    pa = (bc[0] - ux * 40, bc[1] - uy * 40)
    pb = (bc[0] + ux * 45, bc[1] + uy * 45)
    stroke(low, chaikin([pa, (bc[0] - nx * 6, bc[1] - ny * 6), pb]), xf, 2)


def draw_atmosphere(low, t, st):
    """Fondo: pasa de un mundo murky y enfermizo a un amanecer cálido."""
    sick, awake, beat = st["sick"], st["awake"], st["beat"]
    top = mix(NIGHT_TOP, DAWN_TOP, awake)
    bottom = mix(NIGHT_BOTTOM, DAWN_BOTTOM, awake)
    for y in range(LOW_H):
        low.fill(mix(top, bottom, y / LOW_H), (0, y, LOW_W, 1))

    # halo detrás de la cabeza: verdoso y latiendo -> dorado y amplio
    center = (int(520 * S), int(365 * S))
    pulse = 1.0 + 0.03 * math.sin(t * 1.7) + 0.05 * beat * sick
    grow = 1.0 + 0.7 * awake
    glow = pygame.Surface((LOW_W, LOW_H), pygame.SRCALPHA)
    glow_color = mix((70, 120, 96), (255, 196, 128), awake)
    for radius, alpha in ((90, 9), (74, 12), (60, 15), (46, 19)):
        pygame.draw.circle(glow, (*glow_color, int(alpha * (0.8 + 0.8 * awake))),
                           center, round(radius * S * pulse * grow))
    low.blit(glow, (0, 0))

    # rayos de luz del amanecer
    if awake > 0.02:
        rays = pygame.Surface((LOW_W, LOW_H), pygame.SRCALPHA)
        src = (LOW_W * 0.97, -14)
        for k in range(5):
            ang = 1.95 + k * 0.2 + 0.03 * math.sin(t * 0.5 + k)
            w = 0.05 + 0.012 * (k % 2)
            al = int(34 * awake * (0.7 + 0.3 * math.sin(t * 0.8 + k * 1.3)))
            pts = [src,
                   (src[0] + 420 * math.cos(ang - w), src[1] + 420 * math.sin(ang - w)),
                   (src[0] + 420 * math.cos(ang + w), src[1] + 420 * math.sin(ang + w))]
            pygame.draw.polygon(rays, (255, 220, 160, al), pts)
        low.blit(rays, (0, 0))

    # ceniza que cae (trance) ...
    if sick > 0.02:
        for i in range(30):
            x = (i * 61 + 7 + 4 * math.sin(t * 0.6 + i)) % LOW_W
            y = (i * 43 + t * (5 + i % 5)) % LOW_H
            v = int((40 + 30 * (i % 3)) * sick)
            pygame.draw.circle(low, (v, v + 6, v + 2), (int(x), int(y)), 1)
    # ... y luciérnagas doradas que suben (despertar)
    if awake > 0.02:
        for i in range(26):
            x = (i * 67 + 23 + 7 * math.sin(t * 0.8 + i)) % LOW_W
            y = LOW_H - ((i * 41 + (t - T_SNAP) * (8 + i % 5)) % LOW_H)
            tw = 0.55 + 0.45 * math.sin(t * (1.4 + i % 3) + i)
            b = clamp(tw * awake * 1.2)
            col = tuple(int(c * b) for c in (255, 214, 150))
            pygame.draw.circle(low, col, (int(x), int(y)), 1 if i % 4 else 2)


def draw_spiral(low, t, st):
    """Espiral hipnótica del trance. Al romperse se convierte en fragmentos."""
    cx, cy = 520 * S, 365 * S
    dt = t - T_SNAP
    layer = pygame.Surface((LOW_W, LOW_H), pygame.SRCALPHA)

    if dt < 0.3:
        fade = 1.0 if dt < 0 else 1 - dt / 0.3
        scale = 1.0 if dt < 0 else 1 + dt * 3.5
        spin = t * (1.1 + 1.6 * smooth((t - 1.5) / 1.8))       # gira cada vez más rápido
        col = mix((54, 78, 92), (96, 70, 112), 0.5 + 0.5 * math.sin(t * 0.7))
        col = (*col, int(150 * fade))
        for arm in (0, math.pi):
            pts = []
            for j in range(120):
                th = j * 0.12
                r = (2.9 * th) * scale * (1 + 0.05 * math.sin(th * 3 - t * 2.5))
                a = th + spin + arm
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a) * 0.92))
            pygame.draw.lines(layer, col, False, pts, 1)

    # fragmentos que salen despedidos
    if 0 <= dt < 1.7:
        life = 1 - dt / 1.7
        for i in range(44):
            ang = i * 2.39996 + 0.4
            sp = 50 + (i * 37) % 70
            d = sp * dt / (1 + dt * 1.4)
            x, y = cx + d * math.cos(ang), cy + d * math.sin(ang) * 0.9 + 12 * dt * dt
            ln = 2 + i % 4
            col = mix((120, 150, 170), (255, 214, 150), clamp(dt / 0.9))
            pygame.draw.line(layer, (*col, int(230 * life)), (x, y),
                             (x + ln * math.cos(ang + dt * 3), y + ln * math.sin(ang + dt * 3)), 1)
    low.blit(layer, (0, 0))


STRING_ATTACH = [(400, 190), (480, 162), (560, 165), (640, 200), (700, 260), (340, 240)]


def draw_strings(low, t, head_xf):
    """Hilos de marioneta que sujetan la cabeza; se rompen en T_SNAP."""
    layer = pygame.Surface((LOW_W, LOW_H), pygame.SRCALPHA)
    dt = t - T_SNAP
    tension = smooth((t - 2.0) / 1.2)
    n = 18
    for i, a in enumerate(STRING_ATTACH):
        ax, ay = head_xf(a)
        top = (a[0] + (a[0] - 520) * 0.35, -120)
        amp = lerp(9, 1.2, tension)
        pts = []
        for j in range(n + 1):
            u = j / n                                   # 0 arriba, 1 en la cabeza
            wob = amp * math.sin(u * 9 + t * 2.6 + i) * (1 - 0.3 * u)
            pts.append((lerp(top[0], ax, u) + wob, lerp(top[1], ay, u)))

        if dt < 0:
            segs = [(pts, 230)]
        else:
            fade = clamp(1 - dt / 1.1)
            kb = int(n * 0.45)
            upper = [(x, y - dt * dt * 1500) for x, y in pts[:kb + 1]]
            lower = []
            m = len(pts) - kb
            for j, (x, y) in enumerate(pts[kb:]):
                u2 = j / (m - 1)
                lower.append((x + 40 * dt * (1 - u2) * (1 if i % 2 else -1),
                              y + dt * dt * 900 * (1 - u2)))
            segs = [(upper, int(230 * fade)), (lower, int(230 * fade))]

        for seg, al in segs:
            if al > 4:
                pygame.draw.lines(layer, (24, 20, 34, al), False,
                                  [(x * S, y * S) for x, y in seg], 1)
    low.blit(layer, (0, 0))


def draw_tear(low, t, st, xf):
    """Una lágrima de alivio que resbala por la mejilla derecha."""
    dt = t - 4.6
    if not (0 <= dt < 2.4):
        return
    u = dt / 2.4
    x = 662 - dt * 3
    y = 372 + (dt ** 1.4) * 46
    size = clamp(dt / 0.5)
    col = mix((196, 224, 244), st["skin"], clamp((u - 0.75) / 0.25))
    start = (662, 372)
    stroke(low, [start, (x, y)], xf, 1, mix(col, st["skin"], 0.45))
    fill(low, blob(x, y, 7 * size, 10 * size, 8), xf, col)
    (hx, hy), = to_low([(x - 2, y - 3)], xf)
    low.set_at((int(hx), int(hy)), (250, 252, 255))


_VIG = None


def get_vignette():
    global _VIG
    if _VIG is None:
        sw, sh = 32, 24
        small = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for yy in range(sh):
            for xx in range(sw):
                d = math.hypot((xx - sw / 2) / (sw / 2), (yy - sh / 2) / (sh / 2))
                a = clamp((d - 0.45) / 0.85) ** 1.5
                small.set_at((xx, yy), (0, 0, 0, int(255 * a)))
        _VIG = pygame.transform.smoothscale(small, (LOW_W, LOW_H))
    return _VIG


def chromatic(low, k):
    """Aberración cromática: separa los canales R y B k píxeles."""
    if k < 1:
        return
    out = pygame.Surface((LOW_W, LOW_H))
    out.fill((0, 0, 0))
    for chan, dx in (((255, 0, 0), -k), ((0, 255, 0), 0), ((0, 0, 255), k)):
        c = low.copy()
        c.fill(chan, special_flags=pygame.BLEND_RGB_MULT)
        out.blit(c, (dx, 0), special_flags=pygame.BLEND_RGB_ADD)
    low.blit(out, (0, 0))


def glitch(low, t, st):
    """Cortes horizontales y grano de TV; desaparecen al despertar."""
    sick = st["sick"]
    dt = t - T_SNAP
    rng = random.Random(int(t * 12))
    forced = 0 <= dt < 0.3
    if sick > 0.2 and (forced or rng.random() < 0.2 * sick):
        for _ in range(3 if forced else 2):
            y = rng.randrange(0, LOW_H - 12)
            h = rng.randrange(3, 10)
            dx = rng.choice((-1, 1)) * rng.randrange(4, 14 if forced else 10)
            strip = low.subsurface((0, y, LOW_W, h)).copy()
            low.blit(strip, (dx, y))
    for _ in range(int(90 * sick)):
        x, y = rng.randrange(LOW_W), rng.randrange(LOW_H)
        c = low.get_at((x, y))
        d = rng.choice((-24, 24))
        low.set_at((x, y), (int(clamp(c[0] + d, 0, 255)), int(clamp(c[1] + d, 0, 255)), int(clamp(c[2] + d, 0, 255))))


def render(low, t):
    st = state(t)
    droop, o, sick = st["droop"], st["o"], st["sick"]
    skin, shade = st["skin"], st["shade"]
    draw_atmosphere(low, t, st)
    draw_spiral(low, t, st)

    breath, gasp = st["breath"], st["gasp"]
    body_xf = make_xf(0, 0, breath * 1.5 - gasp * 4, (450, 680))
    neck_xf = make_xf(st["angle"] * 0.35, 0, breath * 1.5 + droop * 3 - gasp * 3, (450, 690))
    head_xf = make_xf(st["angle"], breath * 0.8, breath * 2 + droop * 8 - gasp * 3, HEAD_PIVOT)

    # cuerpo y cuello
    fill(low, BODY + [(600, 920), (40, 920)], body_xf, shade)
    stroke(low, BODY, body_xf, 2)
    stroke(low, COLLAR, body_xf, 2)
    stroke(low, BODY_MARK, body_xf, 2)
    fill(low, NECK, neck_xf, shade)
    stroke(low, NECK_L, neck_xf, 2)
    stroke(low, NECK_R, neck_xf, 2)

    # cabeza (la piel recupera el color)
    fill(low, HEAD, head_xf, skin)
    for b in BLOTS:
        fill(low, b, head_xf, shade)
    fill(low, EAR_BLOT, head_xf, shade)
    stroke(low, HEAD + [HEAD[0]], head_xf, 2)
    stroke(low, EAR_R, head_xf, 2)
    stroke(low, EAR_L, head_xf, 2)

    # ojos
    draw_eye(low, EYE_L, o, st["gaze"], st, head_xf)
    draw_eye(low, EYE_R, o, st["gaze"], st, head_xf)

    # nariz y boca (jadea con la bocanada y se entreabre al despertar)
    stroke(low, NOSE_A, head_xf, 2)
    stroke(low, NOSE_B, head_xf, 2)
    open_mouth = (1 - droop) * 5 * (0.5 + 0.5 * math.sin(t * 2.4)) + gasp * 9
    stroke(low, MOUTH_A, head_xf, 2)
    stroke(low, MOUTH_B, head_xf, 2, off=(0, open_mouth))

    # pelo que se mece
    for i, h in enumerate(HAIR):
        off = (2.5 * math.sin(t * 1.6 + i * 0.9), 2.0 * math.sin(t * 1.3 + i * 1.7))
        stroke(low, h, head_xf, 2, off=off)

    draw_tear(low, t, st, head_xf)
    draw_strings(low, t, head_xf)

    # efectos de pantalla: grano, cortes y aberración cromática
    glitch(low, t, st)
    dt = t - T_SNAP
    k = 2.2 * sick * (0.6 + 0.8 * st["beat"])
    if dt >= 0:
        k += 6 * math.exp(-dt * 10)
    chromatic(low, int(round(k)))

    # viñeta que late en el trance y se abre al despertar
    vig = get_vignette()
    vig.set_alpha(int(255 * clamp((0.3 + 0.7 * sick) * (1 + 0.14 * st["beat"] * sick))))
    low.blit(vig, (0, 0))

    # destello blanco de la ruptura
    if st["flash"] > 0.02:
        fl = pygame.Surface((LOW_W, LOW_H))
        fl.fill((255, 246, 228))
        fl.set_alpha(int(235 * st["flash"]))
        low.blit(fl, (0, 0))

    # Fundido inicial desde negro.
    dark = 1 - smooth(t / 0.7)
    if dark > 0.01:
        veil = pygame.Surface((LOW_W, LOW_H))
        veil.fill((8, 11, 20))
        veil.set_alpha(int(255 * dark))
        low.blit(veil, (0, 0))


def draw_frame(screen, low, t):
    render(low, t)
    sw, sh = screen.get_size()
    sc = min(sw / LOW_W, sh / LOW_H)
    w, h = int(LOW_W * sc), int(LOW_H * sc)
    screen.fill(NIGHT_TOP)
    screen.blit(pygame.transform.scale(low, (w, h)), ((sw - w) // 2, (sh - h) // 2))


def play_wake_animation(
    screen,
    clock=None,
    exit_text="EXIT",
    exit_delay=5.0,
    button_renderer=None,
):
    """Mantiene la animación en movimiento hasta que se pulse el botón de salida."""
    clock = clock or pygame.time.Clock()
    low = pygame.Surface((LOW_W, LOW_H))
    t0 = pygame.time.get_ticks()
    while True:
        t = (pygame.time.get_ticks() - t0) / 1000
        exit_button = None
        exit_surface = None
        sw, sh = screen.get_size()
        if button_renderer is not None:
            sx = sw / button_renderer.ancho
            sy = sh / button_renderer.alto
            original = button_renderer.boton_salir
            exit_button = pygame.Rect(
                round(original.x * sx),
                round(original.y * sy),
                round(original.width * sx),
                round(original.height * sy),
            )
            escala_ui = min(sx, sy) * button_renderer._escala()
            fuente = pygame.font.SysFont(
                "comicsansms", max(14, round(22 * escala_ui)), bold=True
            )
        else:
            escala = min(sw / LOW_W, sh / LOW_H)
            fuente = pygame.font.SysFont(
                None, max(18, round(26 * escala)), bold=True
            )
            exit_button = pygame.Rect(0, 0, 170, 54)
            exit_button.bottomright = (sw - 26, sh - 26)
        exit_surface = fuente.render(exit_text, True, (255, 255, 255))
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
        draw_frame(screen, low, t)
        if exit_button is not None:
            hover = exit_button.collidepoint(pygame.mouse.get_pos())
            if button_renderer is not None:
                button_renderer.reloj_pulso = (
                    pygame.time.get_ticks() - t0
                ) / 1000
                rect_dibujo = button_renderer._dibujar_boton_comic(
                    screen, exit_button, hover
                )
                button_renderer._texto_centrado(
                    screen, exit_text, fuente, rect_dibujo.center, (255, 255, 255)
                )
            else:
                pygame.draw.rect(
                    screen,
                    (105, 44, 58) if hover else (62, 38, 48),
                    exit_button,
                    border_radius=8,
                )
                pygame.draw.rect(
                    screen, (245, 220, 190), exit_button, 2, border_radius=8
                )
                screen.blit(
                    exit_surface, exit_surface.get_rect(center=exit_button.center)
                )
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