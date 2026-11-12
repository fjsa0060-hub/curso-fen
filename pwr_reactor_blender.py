# -*- coding: utf-8 -*-
"""
PWR genérico de 4 lazos (inspirado en diseños públicos de Westinghouse)
Maqueta didáctica para Blender -> GLB -> visor Three.js          (versión 2)
=======================================================================

Contenido: vasija y tapa, toberas, penetraciones de instrumentación,
barrilete, paneles de blindaje neutrónico, placas inferiores perforadas,
envolvente con sus placas horizontales, soporte secundario, núcleo con
elementos combustibles detallados (varillas, tubos guía, rejillas y
cabezales), internos superiores, barras de control y mecanismos.

Uso
---
  a) Blender > pestaña Scripting > Abrir este archivo > Run Script (Alt+P)
  b) Línea de comandos:
       blender --background --python pwr_reactor_blender.py -- --out /ruta/salida

Compatibilidad: Blender 3.6 LTS, 4.x y 5.x.

Convenios
---------
  * Unidades: metros. Eje Z vertical. z = 0 en el punto más bajo del
    interior del fondo de la vasija.
  * Cada componente lleva propiedades personalizadas que se exportan como
    "extras" del GLB; el visor las muestra como ficha técnica.
  * [NRC]  dato del Westinghouse Technology Systems Manual de la NRC,
           sección 3.1 "Reactor Vessel and Internals" (ML11223A212).
  * [UFSAR] dato de tablas públicas de UFSAR de plantas de 4 lazos.
  * [EST]  valor aproximado o puramente didáctico. NO es dato de ingeniería.
"""

import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

IN = 0.0254  # pulgada -> metro

# ============================================================================
# 1. PARÁMETROS (editar aquí)
# ============================================================================
P = {
    # --- Vasija -------------------------------------------------------------
    "ves_ri": 173.0 * IN / 2,       # [NRC] diámetro interior de la virola 173 in
    "ves_t": 8.5 * IN,              # [NRC] espesor en la zona del núcleo 8,5 in
    "ves_t_bottom": 5.5 * IN,       # [NRC] espesor del fondo 5,5 in
    "head_t": 6.5 * IN,             # [NRC] espesor de la tapa 6,5 in
    "flange_ro": 205.0 * IN / 2,    # [UFSAR] diámetro exterior de la brida 205 in
    "n_studs": 54,                  # [NRC] 54 pernos de cierre
    "stud_r": 7.0 * IN / 2,         # [NRC] pernos de 7 in de diámetro
    "z_flange": 10.30,              # [EST] plano de unión vasija-tapa
    "z_ledge": 10.03,               # [EST] escalón de apoyo de los internos
    "ledge_ri": 2.32,               # [EST]
    "head_flange_h": 0.60,          # [EST]
    # --- Toberas e instrumentación ------------------------------------------
    "z_nozzle": 8.40,               # [EST] cota del eje de toberas
    "inlet_rb": 27.2 * IN / 2,      # [NRC] tobera de entrada 27,2 in de diámetro interior
    "outlet_rb": 28.8 * IN / 2,     # [NRC] tobera de salida 28,8 in
    "inlet_angles": [67.5, 112.5, 247.5, 292.5],    # [EST] reparto angular esquemático
    "outlet_angles": [22.5, 157.5, 202.5, 337.5],   # [EST]
    "n_bmi": 58,                    # [NRC] 58 penetraciones de instrumentación en el fondo
    "bmi_inside": 12.0 * IN,        # [NRC] sobresalen 12 in dentro de la vasija
    # --- Internos inferiores -------------------------------------------------
    "barrel_ri": 147.25 * IN / 2,   # [NRC] diámetro del barrilete 147,25 in
    "barrel_t": 0.057,              # [EST] espesor
    "barrel_len": 330.75 * IN,      # [NRC] longitud del barrilete 330,75 in
    "barrel_flange_t": 0.10,        # [EST]
    "lsp_t": 18.0 * IN,             # [NRC] placa soporte inferior: 18 in de espesor
    "lcp_t": 2.0 * IN,              # [NRC] placa inferior del núcleo: 2 in
    "lcp_hole_r": 0.032,            # [EST] radio de los 4 orificios por elemento
    "lsp_hole_r": 0.060,            # [EST]
    "baffle_t": 0.028,              # [EST] chapas de la envolvente
    "n_formers": 8,                 # [EST] niveles de placas horizontales (formers)
    "pad_h": 147.0 * IN,            # [NRC] paneles de blindaje: 147 in de alto
    "pad_w": 48.0 * IN,             # [NRC] 48 in de ancho
    "pad_t": 2.75 * IN,             # [NRC] 2,7-2,8 in de espesor
    "pad_angles": [45, 135, 225, 315],   # [EST] frente a las esquinas del núcleo
    # --- Núcleo y elemento combustible ---------------------------------------
    "core_rows": [7, 11, 13, 13, 15, 15, 15, 15, 15, 15, 15, 13, 13, 11, 7],  # 193 [NRC]
    "fa_pitch": 0.215,              # [EST] paso entre elementos ~21,5 cm
    "fa_side": 8.426 * IN,          # [UFSAR] sección 8,426 x 8,426 in
    "fa_height": 4.06,              # [EST] longitud total ~4,06 m
    "fa_active": 144.0 * IN,        # [NRC] longitud activa 144 in
    "rod_pitch": 0.496 * IN,        # [NRC] paso entre varillas 0,496 in
    "rod_r": 0.374 * IN / 2,        # [NRC] diámetro exterior de varilla 0,374 in
    "rod_len": 151.6 * IN,          # [NRC] longitud de varilla 151,6 in
    "thimble_r": 0.482 * IN / 2,    # [NRC] tubo guía 0,482 in de diámetro exterior
    "n_grids": 8,                   # [NRC] 8 rejillas por elemento
    "z_core_bottom": 2.75,          # [EST] apoyo de los elementos
    "detail_fuel": True,            # False = prismas simples (modelo más ligero)
    # --- Internos superiores -------------------------------------------------
    "ucp_t": 3.0 * IN,              # [NRC] placa superior del núcleo: 3 in
    "usp_t": 5.0 * IN,              # [NRC] placa soporte superior: 5 in
    "usp_r": 172.0 * IN / 2,        # [NRC] y 172 in de diámetro
    "n_support_columns": 48,        # [NRC] 48 columnas soporte
    "z_guide_top": 11.20,           # [EST] extremo superior de los tubos guía
    # --- Barras de control ---------------------------------------------------
    "rcca_travel": 144.0 * IN,      # [NRC] recorrido 144 in en pasos de 5/8 in
    "rcca_rodlet_len": 3.85,        # [EST]
    "rcca_shaft_len": 7.30,         # [EST] eje de accionamiento
    "crdm_height": 5.50,            # [EST] altura del mecanismo sobre la tapa
    # --- Malla y exportación -------------------------------------------------
    "seg_big": 64, "seg_mid": 32, "seg_small": 12,
    "use_booleans": True,           # perforar vasija y barrilete en las toberas
    "export_glb": True,
    "use_draco": True,              # compresión Draco (el visor la descomprime)
    "glb_name": "reactor_pwr.glb",
}

# Cotas derivadas
P["barrel_ro"] = P["barrel_ri"] + P["barrel_t"]
P["z_barrel_top"] = P["z_ledge"] + P["barrel_flange_t"]
P["z_barrel_bottom"] = P["z_barrel_top"] - P["barrel_len"]
P["z_lsp"] = (P["z_barrel_bottom"], P["z_barrel_bottom"] + P["lsp_t"])
P["z_lcp"] = (P["z_core_bottom"] - P["lcp_t"], P["z_core_bottom"])
P["z_ucp"] = (P["z_core_bottom"] + P["fa_height"] + 0.02,
              P["z_core_bottom"] + P["fa_height"] + 0.02 + P["ucp_t"])
P["z_usp"] = (P["z_flange"] - P["usp_t"], P["z_flange"])

# Desplazamientos de la vista explosionada (m, ejes de Blender).
EXPLODE = {
    "vasija": (0, 0, 0), "tapa": (0, 0, 25.0), "pernos": (0, 0, 26.0),
    "crdm": (0, 0, 25.0), "rcca": (0, 0, 22.0), "internos_sup": (0, 0, 19.5),
    "nucleo": (0, 0, 17.5), "internos_inf": (0, 0, 9.5), "tobera_radial": 1.5,
}

FUENTE = ("NRC, Westinghouse Technology Systems Manual, sec. 3.1 «Reactor Vessel and "
          "Internals» (ML11223A212). Sección del elemento: UFSAR de Vogtle, tabla 4.3-1. "
          "Brida de la vasija: tabla 5.2-3 de un UFSAR de 4 lazos.")

# ============================================================================
# 2. MATERIALES (PBR, compatibles con glTF)
# ============================================================================
MATERIALS = {
    #  nombre                       color base (RGB)      metal  rugos.
    "PWR_Acero_baja_aleacion":   ((0.23, 0.25, 0.27), 0.90, 0.55),
    "PWR_Acero_inox_304":        ((0.62, 0.64, 0.66), 1.00, 0.32),
    "PWR_Acero_inox_mate":       ((0.48, 0.50, 0.52), 1.00, 0.48),
    "PWR_Zircaloy":              ((0.58, 0.59, 0.54), 1.00, 0.38),
    "PWR_Inconel_718":           ((0.42, 0.40, 0.36), 1.00, 0.42),
    "PWR_Barra_control":         ((0.20, 0.20, 0.22), 1.00, 0.30),
    "PWR_Acero_pernos":          ((0.12, 0.12, 0.13), 0.95, 0.45),
    "PWR_CRDM":                  ((0.36, 0.38, 0.40), 0.95, 0.42),
}


def get_material(name):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    color, metallic, rough = MATERIALS[name]
    if bpy.app.version < (5, 0, 0):
        mat.use_nodes = True
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = rough
    mat.diffuse_color = (*color, 1.0)
    return mat


# ============================================================================
# 3. UTILIDADES DE GEOMETRÍA
# ============================================================================
def circle(cx, cy, r, n, phase=0.0):
    return [(cx + r * math.cos(phase + 2 * math.pi * i / n),
             cy + r * math.sin(phase + 2 * math.pi * i / n)) for i in range(n)]


class MeshBuilder:
    """Acumula primitivas en una sola malla. 'mat' es la ranura de material activa."""

    def __init__(self):
        self.verts, self.faces, self.face_mats = [], [], []
        self.mat = 0

    def _face(self, idx):
        self.faces.append(idx)
        self.face_mats.append(self.mat)

    # -- sólido de revolución alrededor de Z a partir de un perfil (r, z) ----
    def lathe(self, profile, segs, transform=None, closed=True):
        base = len(self.verts)
        rings, idx = [], base
        for r, z in profile:
            if r < 1e-6:
                self.verts.append((0.0, 0.0, z))
                rings.append([idx] * segs)
                idx += 1
            else:
                rings.append(list(range(idx, idx + segs)))
                for j in range(segs):
                    a = 2 * math.pi * j / segs
                    self.verts.append((r * math.cos(a), r * math.sin(a), z))
                idx += segs
        n = len(profile)
        for i in range(n if closed else n - 1):
            a, b = rings[i], rings[(i + 1) % n]
            for j in range(segs):
                k = (j + 1) % segs
                quad = []
                for v in (a[j], b[j], b[k], a[k]):
                    if v not in quad:
                        quad.append(v)
                if len(quad) >= 3:
                    self._face(quad)
        if transform:
            for i in range(base, len(self.verts)):
                self.verts[i] = transform(self.verts[i])
        return self

    def cylinder(self, x, y, z0, z1, r, segs, r_in=0.0):
        prof = [(r_in, z0), (r, z0), (r, z1), (r_in, z1)]
        return self.lathe(prof, segs, lambda v: (v[0] + x, v[1] + y, v[2]))

    def tube_open(self, x, y, z0, z1, r, segs):
        """Tubo sin tapas (varillas): la mitad de triángulos que un cilindro."""
        return self.lathe([(r, z0), (r, z1)], segs, lambda v: (v[0] + x, v[1] + y, v[2]),
                          closed=False)

    def box(self, x0, x1, y0, y1, z0, z1):
        b = len(self.verts)
        self.verts += [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                       (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                  (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self._face([b + i for i in f])
        return self

    def frame(self, half, wall, z0, z1):
        """Marco cuadrado hueco (rejillas y envolvente de cabezales)."""
        h, w = half, wall
        self.box(-h, h, -h, -h + w, z0, z1).box(-h, h, h - w, h, z0, z1)
        self.box(-h, -h + w, -h + w, h - w, z0, z1).box(h - w, h, -h + w, h - w, z0, z1)
        return self

    def arc_solid(self, r0, r1, z0, z1, a0_deg, a1_deg, n):
        """Sector cilíndrico macizo (paneles de blindaje, llaves)."""
        b = len(self.verts)
        for i in range(n + 1):
            a = math.radians(a0_deg + (a1_deg - a0_deg) * i / n)
            c, s = math.cos(a), math.sin(a)
            self.verts += [(r0 * c, r0 * s, z0), (r1 * c, r1 * s, z0),
                           (r1 * c, r1 * s, z1), (r0 * c, r0 * s, z1)]
        for i in range(n):
            p, q = b + 4 * i, b + 4 * (i + 1)
            for k in range(4):
                self._face([p + k, p + (k + 1) % 4, q + (k + 1) % 4, q + k])
        self._face([b, b + 1, b + 2, b + 3])
        e = b + 4 * n
        self._face([e + 3, e + 2, e + 1, e])
        return self

    def plate(self, loops, z0, z1):
        """Placa plana con orificios: loops[0] es el contorno; el resto, agujeros."""
        flat = [p for loop in loops for p in loop]
        tris = tessellate_polygon([[Vector((x, y, 0.0)) for x, y in loop] for loop in loops])
        b, n = len(self.verts), len(flat)
        self.verts += [(x, y, z0) for x, y in flat] + [(x, y, z1) for x, y in flat]
        for t in tris:
            self._face([b + i for i in t])
            self._face([b + n + i for i in t])
        s = 0
        for loop in loops:
            m = len(loop)
            for i in range(m):
                j = (i + 1) % m
                self._face([b + s + i, b + s + j, b + n + s + j, b + n + s + i])
            s += m
        return self

    def to_mesh(self, name, smooth=True, sharp_angle=35.0, materials=()):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(self.verts, [], self.faces)
        for m in materials:
            mesh.materials.append(get_material(m))
        if len(materials) > 1:
            mesh.polygons.foreach_set("material_index", self.face_mats)
        finish_mesh(mesh, smooth, sharp_angle)
        return mesh


def finish_mesh(mesh, smooth=True, sharp_angle=35.0):
    """Recalcula normales hacia fuera y aplica sombreado suave con aristas vivas."""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    if smooth:
        mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
        if hasattr(mesh, "set_sharp_from_angle"):          # Blender >= 4.1
            mesh.set_sharp_from_angle(angle=math.radians(sharp_angle))
        elif hasattr(mesh, "use_auto_smooth"):             # Blender <= 4.0
            mesh.use_auto_smooth = True
            mesh.auto_smooth_angle = math.radians(sharp_angle)
    mesh.update()


def arc(zc, radius, a0_deg, a1_deg, n):
    """Puntos (r, z) de un arco centrado en el eje, a cota zc."""
    pts = []
    for i in range(n + 1):
        a = math.radians(a0_deg + (a1_deg - a0_deg) * i / n)
        pts.append((max(radius * math.cos(a), 0.0), zc + radius * math.sin(a)))
    return pts


def radial_transform(angle_deg, z):
    """Lleva un sólido de revolución (eje Z) a un eje radial horizontal."""
    ca, sa = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))

    def tf(v):
        x, y, zz = v[2], v[0], v[1]
        return (x * ca - y * sa, x * sa + y * ca, zz + z)
    return tf


def bottom_head_z(r):
    """Cota de la superficie interior del fondo semiesférico a radio r."""
    R = P["ves_ri"]
    return R - math.sqrt(R * R - r * r)


def head_outer_z(r):
    """Cota de la superficie exterior de la cúpula de la tapa a radio r."""
    R = P["ves_ri"] + P["head_t"]
    return P["z_flange"] + P["head_flange_h"] + math.sqrt(R * R - r * r)


# ============================================================================
# 4. ESCENA: colecciones, objetos y metadatos
# ============================================================================
ROOT_NAME = "PWR_Reactor"


def reset_root():
    """Elimina una maqueta anterior (solo lo creado por este script)."""
    old = bpy.data.collections.get(ROOT_NAME)
    if old:
        meshes = {o.data for o in old.all_objects if o.type == "MESH"}
        for o in list(old.all_objects):
            bpy.data.objects.remove(o, do_unlink=True)
        for c in list(old.children_recursive):
            bpy.data.collections.remove(c)
        bpy.data.collections.remove(old)
        for m in meshes:
            if m and m.users == 0:
                bpy.data.meshes.remove(m)
    root = bpy.data.collections.new(ROOT_NAME)
    bpy.context.scene.collection.children.link(root)
    return root


def set_props(obj, props):
    for k, v in props.items():
        obj[k] = list(v) if isinstance(v, (tuple, list)) else v


def new_empty(name, coll, parent=None, props=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.5
    coll.objects.link(e)
    e.parent = parent
    set_props(e, props or {})
    return e


def new_object(name, mesh, coll, parent=None, location=(0, 0, 0), props=None):
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    obj.parent = parent
    obj.location = location
    set_props(obj, props or {})
    return obj


def new_system(root, key, nombre, descripcion):
    """Un sistema = una colección de Blender + un Empty padre (nodo del GLB)."""
    coll = bpy.data.collections.new(key)
    root.children.link(coll)
    empty = new_empty(key, coll, props={
        "pwr_tipo": "sistema", "nombre": nombre, "descripcion": descripcion})
    return coll, empty


def info(nombre, funcion, material, datos, simplificacion, color, explode=(0, 0, 0), **extra):
    """Ficha técnica. 'datos' solo lleva valores documentados; lo aproximado va en
    'simplificacion'."""
    d = {"pwr_tipo": "componente", "nombre": nombre, "funcion": funcion,
         "material": material, "datos": datos, "simplificacion": simplificacion,
         "color_didactico": color, "explode": explode, "fuente": FUENTE}
    d.update(extra)
    return d


def boolean_cut(obj, cutter_builder):
    """Resta a 'obj' la malla acumulada en cutter_builder (y la descarta)."""
    cmesh = cutter_builder.to_mesh("PWR_tmp_cutter", smooth=False)
    cutter = bpy.data.objects.new("PWR_tmp_cutter", cmesh)
    obj.users_collection[0].objects.link(cutter)
    mod = obj.modifiers.new("corte", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = cutter
    try:
        mod.solver = "EXACT"
    except Exception:
        pass
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    new_mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    old = obj.data
    obj.modifiers.remove(mod)
    new_mesh.name = old.name
    obj.data = new_mesh
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cutter, do_unlink=True)
    bpy.data.meshes.remove(cmesh)
    finish_mesh(obj.data, True)


# ============================================================================
# 5. MAPA DEL NÚCLEO Y RETÍCULA DEL ELEMENTO
# ============================================================================
COLS = "RPNMLKJHGFEDCBA"     # denominación habitual de columnas (sin I, O, Q)


def core_cells():
    """[(dx, dy, etiqueta)] con dx, dy en pasos de elemento desde el centro."""
    cells = []
    half = len(P["core_rows"]) // 2
    for row, width in enumerate(P["core_rows"]):
        for dx in range(-(width // 2), width // 2 + 1):
            cells.append((dx, half - row, f"{COLS[dx + half]}-{row + 1:02d}"))
    return cells


def core_outline(offset):
    """Contorno escalonado del núcleo (polígono cerrado) separado 'offset' hacia fuera."""
    p, rows = P["fa_pitch"], P["core_rows"]
    half = len(rows) // 2
    right = []
    for row in range(len(rows) - 1, -1, -1):           # de abajo arriba
        dy = half - row
        hw = (rows[row] // 2 + 0.5) * p + offset
        y0 = (dy - 0.5) * p - (offset if row == len(rows) - 1 else 0)
        y1 = (dy + 0.5) * p + (offset if row == 0 else 0)
        # en los escalones el borde se desplaza con la fila más ancha
        if row < len(rows) - 1 and rows[row + 1] < rows[row]:
            y0 -= offset
        if row > 0 and rows[row - 1] < rows[row]:
            y1 += offset
        right += [(hw, y0), (hw, y1)]
    pts = right + [(-x, y) for x, y in reversed(right)]
    out = []
    for q in pts:
        if not out or (abs(q[0] - out[-1][0]) > 1e-9 or abs(q[1] - out[-1][1]) > 1e-9):
            out.append(q)
    return out


def rcca_cells(cells):
    """53 posiciones [NRC] con simetría de octante; la distribución es esquemática [EST]."""
    extra = {(5, 3), (3, 5)}
    return [(dx, dy, tag) for dx, dy, tag in cells
            if (dx % 2 == 0 and dy % 2 == 0) or (abs(dx), abs(dy)) in extra]


def support_column_cells(cells, rset):
    """48 columnas soporte [NRC] en posiciones sin haz de control (reparto esquemático)."""
    out = [(dx, dy) for dx, dy, _ in cells
           if dx % 2 == 1 and dy % 2 == 1 and (dx, dy) not in rset]
    out += [(7, 0), (-7, 0), (0, 7), (0, -7)]
    return out[:P["n_support_columns"]]


def bmi_cells(cells):
    """58 posiciones con instrumentación intranuclear [NRC]; reparto esquemático [EST]."""
    cand = [(dx, dy) for dx, dy, _ in cells if (dx - 2 * dy) % 3 == 0]
    cand.sort(key=lambda c: (c[0] ** 2 + c[1] ** 2, c))
    return cand[:P["n_bmi"]]


def thimble_lattice():
    """24 posiciones de tubo guía en la retícula 17x17 (índices -8..8 desde el centro)."""
    out = []
    for row, cols in ((6, (-3, 0, 3)), (5, (-5, 5)), (3, (-6, -3, 0, 3, 6)), (0, (-6, -3, 3, 6))):
        for sgn in ((1, -1) if row else (1,)):
            out += [(c, sgn * row) for c in cols]
    return out


# ============================================================================
# 6. CONSTRUCTORES DE COMPONENTES
# ============================================================================
def build_vessel(root, cells):
    coll, sysobj = new_system(root, "01_Vasija_de_presion", "Vasija de presión",
                              "Barrera de presión del circuito primario que aloja el núcleo.")
    ri, t = P["ves_ri"], P["ves_t"]
    ro = ri + t
    zf, zl, fro = P["z_flange"], P["z_ledge"], P["flange_ro"]
    seg = P["seg_big"]

    # --- cuerpo ---------------------------------------------------------------
    prof = arc(ri, ri + P["ves_t_bottom"], -90, 0, 14)
    prof += [(ro, ri + 0.40), (ro, zf - 0.85), (fro, zf - 0.60), (fro, zf),
             (P["ledge_ri"], zf), (P["ledge_ri"], zl), (ri, zl)]
    prof += arc(ri, ri, 0, -90, 14)
    body = new_object("Vasija_cuerpo", MeshBuilder().lathe(prof, seg).to_mesh(
        "Vasija_cuerpo", materials=["PWR_Acero_baja_aleacion"]), coll, sysobj, props=info(
        "Vasija del reactor (cuerpo)",
        "Contiene el núcleo y los internos y soporta la presión del primario.",
        "Acero aleado al manganeso-molibdeno; las superficies en contacto con el "
        "refrigerante llevan un recubrimiento de acero inoxidable depositado por soldadura.",
        "Diámetro interior de la virola: 173 in (4,39 m). Altura: 525,8 in (13,4 m). "
        "Espesores: 8,5 in en la zona del núcleo y 5,5 in en el fondo. Recubrimiento "
        "inoxidable de 0,156 in. Diseño: 2485 psig y 650 °F. Los internos cuelgan de "
        "un escalón de la brida.",
        "Transiciones de espesor y cotas verticales aproximadas; un solo material (no "
        "se distingue el recubrimiento); sin soportes, aislamiento ni soldaduras.",
        "#5b6b7a", EXPLODE["vasija"]))

    # --- tapa -------------------------------------------------------------------
    hz = zf + P["head_flange_h"]
    hro = ri + P["head_t"]
    prof = [(fro, zf), (fro, hz)] + arc(hz, hro, 0, 90, 14) + arc(hz, ri, 90, 0, 14) + [(ri, zf)]
    mb = MeshBuilder().lathe(prof, seg)
    mb.cylinder(0.215, 0.215, head_outer_z(0.30) - 0.05, head_outer_z(0.30) + 0.45, 0.0127, 8)
    new_object("Tapa_vasija", mb.to_mesh("Tapa_vasija", materials=["PWR_Acero_baja_aleacion"]),
               coll, sysobj, props=info(
        "Tapa de la vasija (desmontable)",
        "Cierra la vasija; se retira en cada recarga para acceder al núcleo. Sus "
        "penetraciones alojan los mecanismos de accionamiento de las barras.",
        "Acero aleado con recubrimiento interior inoxidable.",
        "Espesor: 6,5 in. Cierre con dos juntas tóricas metálicas concéntricas y línea "
        "de detección de fugas entre ambas. Lleva un tubo de venteo de Inconel.",
        "Cúpula semiesférica idealizada; penetraciones sin mecanizar; sin columnas de "
        "termopares ni orejetas de izado. El venteo está agrandado para que se vea.",
        "#7d8fa1", EXPLODE["tapa"]))

    # --- pernos -----------------------------------------------------------------
    mb = MeshBuilder()
    rs = (P["ledge_ri"] + fro) / 2 + 0.01
    for i in range(P["n_studs"]):
        a = 2 * math.pi * i / P["n_studs"]
        x, y = rs * math.cos(a), rs * math.sin(a)
        mb.cylinder(x, y, hz - 0.02, hz + 0.40, P["stud_r"], 10)
        mb.cylinder(x, y, hz, hz + 0.24, P["stud_r"] * 1.5, 6)
    new_object("Pernos_cierre", mb.to_mesh("Pernos_cierre", materials=["PWR_Acero_pernos"]),
               coll, sysobj, props=info(
        "Pernos de cierre",
        "Mantienen la tapa apretada contra la brida de la vasija.",
        "Acero aleado de alta resistencia.",
        "54 pernos de 7 in (17,8 cm) de diámetro.",
        "Solo se dibuja la parte visible sobre la brida; sin arandelas ni roscas.",
        "#2f3a44", EXPLODE["pernos"]))

    # --- toberas ----------------------------------------------------------------
    zn = P["z_nozzle"]

    def nozzle_profile(rb, inner_lip):
        p = ([(rb, P["barrel_ro"] + 0.03), (rb + 0.06, P["barrel_ro"] + 0.03), (rb + 0.06, 2.20)]
             if inner_lip else [(rb, 2.20)])
        return p + [(rb + 0.43, 2.20), (rb + 0.43, 2.55), (rb + 0.15, 2.95),
                    (rb + 0.10, 3.35), (rb, 3.35)]

    for key, nombre, rb, angles, lip, color, funcion, datos in (
        ("Toberas_entrada", "Toberas de entrada (rama fría)", P["inlet_rb"], P["inlet_angles"],
         False, "#3d7fc4",
         "Reciben el refrigerante de las bombas; el caudal baja por el espacio anular "
         "(downcomer) entre vasija y barrilete hasta el plenum inferior.",
         "4 toberas de 27,2 in (0,69 m) de diámetro interior."),
        ("Toberas_salida", "Toberas de salida (rama caliente)", P["outlet_rb"], P["outlet_angles"],
         True, "#d2553f",
         "Conducen el refrigerante caliente desde el plenum superior hacia los "
         "generadores de vapor.",
         "4 toberas de 28,8 in (0,73 m) de diámetro interior, enfrentadas a las cuatro "
         "bocas de salida del barrilete."),
    ):
        grp = new_empty(key, coll, sysobj, info(
            nombre, funcion, "Forja de acero aleado con recubrimiento inoxidable.",
            datos, "Reparto angular y forma del refuerzo esquemáticos; sin apoyos de la "
            "vasija ni transición a la tubería.", color))
        for n, ang in enumerate(angles, 1):
            mb = MeshBuilder().lathe(nozzle_profile(rb, lip), P["seg_mid"],
                                     radial_transform(ang, zn))
            d = EXPLODE["tobera_radial"]
            new_object(f"{key}_{n}", mb.to_mesh(f"{key}_{n}", materials=["PWR_Acero_baja_aleacion"]),
                       coll, grp, props={"explode": (d * math.cos(math.radians(ang)),
                                                    d * math.sin(math.radians(ang)), 0),
                                         "detalle": f"Lazo {n} · {ang:.1f}°"})

    if P["use_booleans"]:
        cut = MeshBuilder()
        for rb, angles in ((P["inlet_rb"], P["inlet_angles"]), (P["outlet_rb"], P["outlet_angles"])):
            for ang in angles:
                cut.lathe([(0, 1.99), (rb, 1.99), (rb, 3.0), (0, 3.0)], P["seg_mid"],
                          radial_transform(ang, zn))
        boolean_cut(body, cut)

    # --- penetraciones de instrumentación del fondo ---------------------------
    mb = MeshBuilder()
    for dx, dy in bmi_cells(cells):
        x, y = dx * P["fa_pitch"], dy * P["fa_pitch"]
        z = bottom_head_z(math.hypot(x, y))
        mb.cylinder(x, y, z - P["ves_t_bottom"] - 0.25, z + P["bmi_inside"], 0.025, 8)
    new_object("Penetraciones_instrumentacion",
               mb.to_mesh("Penetraciones_instrumentacion", materials=["PWR_Acero_inox_304"]),
               coll, sysobj, props=info(
        "Penetraciones de instrumentación intranuclear",
        "Por ellas entran desde el fondo los detectores móviles que miden el flujo "
        "neutrónico dentro del núcleo.",
        "Tubos de aleación de níquel o acero inoxidable soldados al fondo.",
        "58 penetraciones; cada una sobresale 12 in (30 cm) dentro de la vasija.",
        "Reparto en planta esquemático; tubos verticales macizos; sin las columnas guía "
        "que las prolongan hasta el núcleo.",
        "#d9c24a", EXPLODE["vasija"]))
    return sysobj


def build_lower_internals(root, cells):
    coll, sysobj = new_system(root, "02_Internos_inferiores", "Internos inferiores",
                              "Soportan el núcleo y dirigen el caudal de refrigerante.")
    seg = P["seg_big"]
    bri, bro = P["barrel_ri"], P["barrel_ro"]
    zl, zb, zt = P["z_ledge"], P["z_barrel_bottom"], P["z_barrel_top"]
    ex = EXPLODE["internos_inf"]
    pitch = P["fa_pitch"]
    occupied = {(dx, dy) for dx, dy, _ in cells}

    # --- barrilete (con llaves radiales y pasadores de la placa superior) ---------
    mb = MeshBuilder().lathe([(bro, zb), (bro, zl), (P["ledge_ri"] - 0.01, zl),
                              (P["ledge_ri"] - 0.01, zt), (bri, zt), (bri, zb)], seg)
    for k in range(6):                                   # 6 llaves radiales [NRC]
        mb.arc_solid(bro, bro + 0.13, zb + 0.02, zb + 0.30, k * 60 - 2.5, k * 60 + 2.5, 2)
    for k in range(4):                                   # 4 pasadores a 90° [NRC]
        mb.arc_solid(bri - 0.035, bri, P["z_ucp"][0] - 0.02, P["z_ucp"][1] + 0.02,
                     k * 90 - 1.2, k * 90 + 1.2, 2)
    barrel = new_object("Barrilete", mb.to_mesh("Barrilete", materials=["PWR_Acero_inox_304"]),
                        coll, sysobj, props=info(
        "Barrilete del núcleo",
        "Cilindro colgado de la brida de la vasija. Soporta el núcleo, separa el caudal "
        "descendente (downcomer) del ascendente y transmite las cargas a la vasija.",
        "Acero inoxidable austenítico tipo 304.",
        "Diámetro 147,25 in (3,74 m) y longitud 330,75 in (8,40 m). Cuatro bocas de "
        "salida en la parte superior. Abajo, seis llaves radiales lo centran en la vasija; "
        "cuatro pasadores a 90° alinean la placa superior del núcleo.",
        "Espesor de pared y brida aproximados; sin las 16 toberas de refrigeración de "
        "la tapa ni las ranuras de los formers.",
        "#9aa7b3", ex))
    if P["use_booleans"]:
        cut = MeshBuilder()
        for ang in P["outlet_angles"]:
            cut.lathe([(0, 1.5), (P["outlet_rb"], 1.5), (P["outlet_rb"], 2.1), (0, 2.1)],
                      P["seg_mid"], radial_transform(ang, P["z_nozzle"]))
        boolean_cut(barrel, cut)

    # --- paneles de blindaje neutrónico --------------------------------------------
    zc = P["z_core_bottom"] + P["fa_height"] / 2
    half_ang = math.degrees(P["pad_w"] / 2 / (bro + 0.02))
    mb = MeshBuilder()
    for a in P["pad_angles"]:
        mb.arc_solid(bro + 0.02, bro + 0.02 + P["pad_t"], zc - P["pad_h"] / 2, zc + P["pad_h"] / 2,
                     a - half_ang, a + half_ang, 10)
    new_object("Paneles_blindaje_neutronico",
               mb.to_mesh("Paneles_blindaje_neutronico", materials=["PWR_Acero_inox_mate"]),
               coll, sysobj, props=info(
        "Paneles de blindaje neutrónico",
        "Reducen la dosis de neutrones rápidos que recibe la pared de la vasija en las "
        "zonas donde el núcleo queda más cerca. Llevan las guías de las cápsulas de "
        "vigilancia del material de la vasija.",
        "Acero inoxidable tipo 304.",
        "4 paneles de 147 in de alto (3,73 m), 48 in de ancho (1,22 m) y entre 2,7 y "
        "2,8 in de espesor, fijados al exterior del barrilete con separadores que dejan "
        "pasar caudal de refrigeración.",
        "Posición angular esquemática; sin separadores, tornillos ni cápsulas de vigilancia.",
        "#37b8c4", ex))

    # --- placa soporte inferior (18 in, con orificios) ----------------------------
    z0, z1 = P["z_lsp"]
    loops = [circle(0, 0, bri - 0.002, seg)]
    loops += [circle(dx * pitch, dy * pitch, P["lsp_hole_r"], 12) for dx, dy in sorted(occupied)]
    new_object("Placa_soporte_inferior",
               MeshBuilder().plate(loops, z0, z1).to_mesh(
                   "Placa_soporte_inferior", materials=["PWR_Acero_inox_mate"]),
               coll, sysobj, props=info(
        "Placa soporte inferior del núcleo",
        "Cierra el barrilete por abajo, al que va soldada, y transmite el peso del "
        "núcleo. Sus orificios dejan subir el refrigerante desde el plenum inferior.",
        "Acero inoxidable austenítico tipo 304.",
        "Espesor: 18 in (46 cm). Unas columnas la unen a la placa inferior del núcleo.",
        "Un orificio por elemento, de diámetro aproximado; el número y tamaño reales no "
        "figuran en la fuente.",
        "#a2579e", ex))

    # --- columnas entre placas -----------------------------------------------------
    mb = MeshBuilder()
    for i in range(-8, 8, 2):
        for j in range(-8, 8, 2):
            if all((i + a, j + b) in occupied for a in (0, 1) for b in (0, 1)):
                mb.cylinder((i + 0.5) * pitch, (j + 0.5) * pitch, z1, P["z_lcp"][0], 0.045, 10)
    new_object("Columnas_soporte_inferiores",
               mb.to_mesh("Columnas_soporte_inferiores", materials=["PWR_Acero_inox_304"]),
               coll, sysobj, props=info(
        "Columnas soporte inferiores",
        "Transmiten el peso del núcleo desde la placa inferior del núcleo a la placa "
        "soporte inferior.",
        "Acero inoxidable austenítico tipo 304.",
        "Instaladas entre la placa inferior del núcleo y la placa soporte.",
        "Número y posiciones esquemáticos (la fuente no los da).",
        "#c98fc6", ex))

    # --- placa inferior del núcleo (2 in, 4 orificios y 2 pasadores por elemento) ---
    z0, z1 = P["z_lcp"]
    q = P["fa_side"] / 4
    loops = [circle(0, 0, bri - 0.002, seg)]
    for dx, dy in sorted(occupied):
        for sx in (-1, 1):
            for sy in (-1, 1):
                loops.append(circle(dx * pitch + sx * q, dy * pitch + sy * q, P["lcp_hole_r"], 12))
    mb = MeshBuilder().plate(loops, z0, z1)
    pin = P["fa_side"] / 2 - 0.02
    for dx, dy in occupied:
        for s in (-1, 1):
            mb.cylinder(dx * pitch + s * pin, dy * pitch + s * pin, z1, z1 + 0.04, 0.010, 6)
    new_object("Placa_inferior_nucleo",
               mb.to_mesh("Placa_inferior_nucleo", materials=["PWR_Acero_inox_mate"]),
               coll, sysobj, props=info(
        "Placa inferior del núcleo",
        "Sobre ella apoyan los elementos combustibles. Sus pasadores encajan en el "
        "cabezal inferior de cada elemento y sus orificios reparten el caudal.",
        "Acero inoxidable austenítico tipo 304.",
        "Espesor: 2 in (5 cm). Por cada elemento combustible hay cuatro orificios de "
        "paso de caudal y dos pasadores de alineación (772 orificios y 386 pasadores).",
        "Diámetro de orificios y pasadores aproximado.",
        "#e04f8b", ex))

    # --- envolvente (baffle) ---------------------------------------------------------
    t = P["baffle_t"]
    z0, z1 = P["z_core_bottom"], P["z_ucp"][0]
    h = pitch / 2
    mb = MeshBuilder()
    for dx, dy in occupied:
        cx, cy = dx * pitch, dy * pitch
        if (dx + 1, dy) not in occupied:
            mb.box(cx + h, cx + h + t, cy - h - t, cy + h + t, z0, z1)
        if (dx - 1, dy) not in occupied:
            mb.box(cx - h - t, cx - h, cy - h - t, cy + h + t, z0, z1)
        if (dx, dy + 1) not in occupied:
            mb.box(cx - h - t, cx + h + t, cy + h, cy + h + t, z0, z1)
        if (dx, dy - 1) not in occupied:
            mb.box(cx - h - t, cx + h + t, cy - h - t, cy - h, z0, z1)
    new_object("Envolvente_nucleo",
               mb.to_mesh("Envolvente_nucleo", smooth=False, materials=["PWR_Acero_inox_304"]),
               coll, sysobj, props=info(
        "Envolvente del núcleo (baffle)",
        "Chapas verticales que siguen el contorno escalonado del núcleo y obligan al "
        "refrigerante a pasar por los elementos combustibles.",
        "Acero inoxidable austenítico tipo 304.",
        "Chapas verticales atornilladas a los formers. El caudal que se desvía por "
        "esta región es el 1,84 % del total.",
        "Espesor aproximado; sin tornillos ni juntas entre chapas.",
        "#e6d34a", ex))

    # --- formers ------------------------------------------------------------------------
    mb = MeshBuilder()
    outline = core_outline(t + 0.001)
    for k in range(P["n_formers"]):
        zf_ = z0 + 0.12 + (z1 - z0 - 0.27) * k / (P["n_formers"] - 1)
        mb.plate([circle(0, 0, bri - 0.002, seg), outline], zf_, zf_ + 0.03)
    new_object("Formers", mb.to_mesh("Formers", smooth=False, materials=["PWR_Acero_inox_mate"]),
               coll, sysobj, props=info(
        "Placas horizontales de la envolvente (formers)",
        "Unen las chapas de la envolvente con el barrilete y les dan rigidez.",
        "Acero inoxidable austenítico tipo 304.",
        "Placas horizontales atornilladas a ranuras circulares del barrilete, con "
        "pequeños orificios para el caudal de refrigeración.",
        f"Se representan {P['n_formers']} niveles (la fuente no da el número); sin "
        "orificios ni tornillos.",
        "#b9a233", ex))

    # --- soporte secundario del núcleo ----------------------------------------------------
    gap = 0.5 * IN                                       # holgura en caliente 1/2 in [NRC]
    prof = [(0, gap)] + [(r, bottom_head_z(r) + gap) for r in (0.2, 0.4, 0.6, 0.75)]
    prof += [(r, bottom_head_z(r) + gap + 0.06) for r in (0.75, 0.6, 0.4, 0.2)] + [(0, gap + 0.06)]
    mb = MeshBuilder().lathe(prof, 32)
    for k in range(4):                                   # 4 columnas absorbedoras [NRC]
        a = math.radians(45 + 90 * k)
        x, y = 0.45 * math.cos(a), 0.45 * math.sin(a)
        mb.cylinder(x, y, bottom_head_z(0.45) + gap + 0.05, P["z_lsp"][0], 0.07, 12)
    new_object("Soporte_secundario_nucleo",
               mb.to_mesh("Soporte_secundario_nucleo", materials=["PWR_Acero_inox_304"]),
               coll, sysobj, props=info(
        "Soporte secundario del núcleo",
        "Salvaguarda pasiva: si fallara el apoyo del barrilete, limita la caída del "
        "núcleo y absorbe la energía del impacto contra el fondo de la vasija.",
        "Acero inoxidable austenítico tipo 304.",
        "4 columnas absorbedoras de energía sobre una placa base con la forma del "
        "fondo. Holgura en caliente con la vasija: 1/2 in; desplazamiento total "
        "admitido: 1 1/4 in.",
        "Tamaño de la placa base y de las columnas aproximado; sin las guías de "
        "instrumentación que comparten este conjunto.",
        "#8a6fd1", ex))
    return sysobj


def fuel_assembly_mesh():
    """Elemento combustible 17x17. Ranuras: 0 aleación de circonio, 1 Inconel, 2 inoxidable."""
    s, hgt, rp = P["fa_side"], P["fa_height"], P["rod_pitch"]
    half = s / 2
    mats = ["PWR_Zircaloy", "PWR_Inconel_718", "PWR_Acero_inox_304"]
    mb = MeshBuilder()
    if not P["detail_fuel"]:
        mb.mat = 2
        mb.box(-half, half, -half, half, 0.0, 0.09)
        mb.box(-half, half, -half, half, hgt - 0.10, hgt)
        mb.mat = 0
        mb.box(-half + 0.004, half - 0.004, -half + 0.004, half - 0.004, 0.09, hgt - 0.10)
        return mb.to_mesh("Elemento_combustible", smooth=False, materials=mats)

    # cabezal inferior: cuatro patas + placa perforada
    mb.mat = 2
    leg = 0.045
    for sx in (-1, 1):
        for sy in (-1, 1):
            x0, y0 = sx * half, sy * half
            mb.box(min(x0, x0 - sx * leg), max(x0, x0 - sx * leg),
                   min(y0, y0 - sy * leg), max(y0, y0 - sy * leg), 0.0, 0.055)
    mb.box(-half, half, -half, half, 0.055, 0.085)
    # cabezal superior: placa adaptadora, envolvente, placa superior y muelles
    zt = hgt - 0.09
    mb.box(-half, half, -half, half, zt, zt + 0.018)
    mb.frame(half, 0.008, zt + 0.018, zt + 0.07)
    mb.frame(half, 0.022, zt + 0.07, zt + 0.078)
    mb.mat = 1
    for sy in (-1, 1):                                    # muelles de sujeción (Inconel)
        mb.box(-half + 0.03, half - 0.03, sy * (half - 0.018) - 0.006, sy * (half - 0.018) + 0.006,
               zt + 0.078, hgt)
    for sx in (-1, 1):
        mb.box(sx * (half - 0.018) - 0.006, sx * (half - 0.018) + 0.006, -half + 0.03, half - 0.03,
               zt + 0.078, hgt)
    # rejillas: las de los extremos, de Inconel; las intermedias, de aleación de circonio
    n = P["n_grids"]
    for k in range(n):
        zg = 0.13 + (zt - 0.30) * k / (n - 1)
        mb.mat = 1 if k in (0, n - 1) else 0
        mb.frame(half - 0.001, 0.004, zg, zg + 0.045)
    # tubos guía (24) + tubo de instrumentación + varillas (264)
    mb.mat = 0
    thimbles = set(thimble_lattice()) | {(0, 0)}
    z_rod0 = 0.10
    for i in range(-8, 9):
        for j in range(-8, 9):
            if (i, j) in thimbles:
                mb.tube_open(i * rp, j * rp, 0.085, zt, P["thimble_r"], 6)
            else:
                mb.tube_open(i * rp, j * rp, z_rod0, z_rod0 + P["rod_len"], P["rod_r"], 6)
    return mb.to_mesh("Elemento_combustible", sharp_angle=50.0, materials=mats)


def build_core(root, cells):
    coll, sysobj = new_system(root, "03_Nucleo", "Núcleo",
                              "Región donde se produce la fisión y se calienta el refrigerante.")
    mesh = fuel_assembly_mesh()
    grp = new_empty("Elementos_combustibles", coll, sysobj, info(
        "Elementos combustibles (193)",
        "Cada elemento agrupa las varillas de combustible, con pastillas de UO₂ dentro "
        "de una vaina de aleación de circonio, y los tubos guía donde entran las barras "
        "de control. Las rejillas mantienen la separación entre varillas.",
        "Vainas de Zircaloy-4. Rejillas de aleación de circonio con aletas de mezcla en "
        "la zona de mayor flujo y de Inconel 718 en los extremos. Cabezales de acero "
        "inoxidable 304; muelles de sujeción de Inconel 718.",
        "193 elementos de 17×17 con 264 varillas cada uno (50 952 en total), 24 tubos "
        "guía y un tubo central de instrumentación. 8 rejillas por elemento. Varilla: "
        "0,374 in de diámetro exterior (9,5 mm), vaina de 0,0225 in, 151,6 in de "
        "longitud y 144 in (3,66 m) de longitud activa; paso entre varillas 0,496 in. "
        "Pastilla de UO₂ de 0,3225 in de diámetro. Cabezal inferior: placa perforada "
        "con cuatro patas. Cabezal superior: placa adaptadora, envolvente, placa "
        "superior y muelles de sujeción.",
        "Varillas y tubos como prismas hexagonales huecos; rejillas reducidas a su "
        "banda exterior; cabezales sin perforar; muelles como pletinas. Longitud total "
        "del elemento y cotas de las rejillas aproximadas. Todos los elementos son "
        "iguales (no se distinguen enriquecimientos).",
        "#4f9d69", EXPLODE["nucleo"]))
    for dx, dy, tag in cells:
        new_object(f"EC_{tag}", mesh, coll, grp,
                   location=(dx * P["fa_pitch"], dy * P["fa_pitch"], P["z_core_bottom"]),
                   props={"detalle": f"Posición {tag}"})
    return sysobj


def build_upper_internals(root, cells, rccas):
    coll, sysobj = new_system(root, "04_Internos_superiores", "Internos superiores",
                              "Sujetan el núcleo por arriba y guían las barras de control.")
    seg = P["seg_big"]
    ex = EXPLODE["internos_sup"]
    pitch = P["fa_pitch"]
    (u0, u1), (s0, s1) = P["z_ucp"], P["z_usp"]
    rset = {(dx, dy) for dx, dy, _ in rccas}
    occupied = sorted({(dx, dy) for dx, dy, _ in cells})

    # --- placa superior del núcleo (3 in, una abertura por elemento) ---------------
    loops = [circle(0, 0, P["barrel_ri"] - 0.004, seg)]
    loops += [circle(dx * pitch, dy * pitch, 0.088 if (dx, dy) in rset else 0.070, 16)
              for dx, dy in occupied]
    mb = MeshBuilder().plate(loops, u0, u1)
    pin = P["fa_side"] / 2 - 0.02
    for dx, dy in occupied:
        for s in (-1, 1):
            mb.cylinder(dx * pitch + s * pin, dy * pitch - s * pin, u0 - 0.035, u0, 0.010, 6)
    new_object("Placa_superior_nucleo",
               mb.to_mesh("Placa_superior_nucleo", materials=["PWR_Acero_inox_mate"]),
               coll, sysobj, props=info(
        "Placa superior del núcleo",
        "Posiciona el cabezal superior de los elementos y limita su desplazamiento "
        "vertical; el refrigerante sale del núcleo por sus aberturas.",
        "Acero inoxidable austenítico tipo 304.",
        "Diámetro 147,25 in (3,74 m) y espesor 3 in (7,6 cm). Se alinea con el "
        "barrilete mediante ranuras que encajan en cuatro pasadores a 90°.",
        "Una abertura circular por elemento, mayor donde pasa un haz de control; forma "
        "y tamaño de las aberturas y de los pasadores aproximados.",
        "#e07a3a", ex))

    # --- placa soporte superior (5 in, 172 in) ---------------------------------------
    loops = [circle(0, 0, P["usp_r"], seg)]
    loops += [circle(dx * pitch, dy * pitch, 0.096, 16) for dx, dy in sorted(rset)]
    new_object("Placa_soporte_superior",
               MeshBuilder().plate(loops, s0, s1).to_mesh(
                   "Placa_soporte_superior", materials=["PWR_Acero_inox_mate"]),
               coll, sysobj, props=info(
        "Placa soporte superior",
        "De ella cuelgan las columnas soporte y los tubos guía; queda aprisionada entre "
        "la brida del barrilete y la tapa.",
        "Acero inoxidable austenítico tipo 304.",
        "Espesor 5 in (12,7 cm) y diámetro 172 in (4,37 m).",
        "Placa plana con un paso por tubo guía; sin las penetraciones de los termopares.",
        "#6c8ebf", ex))

    # --- muelle de sujeción de los internos --------------------------------------------
    zs = P["z_barrel_top"]
    mb = MeshBuilder().lathe([(2.19, zs), (2.30, zs), (2.30, s0), (2.19, s0)], seg)
    new_object("Muelle_sujecion_internos",
               mb.to_mesh("Muelle_sujecion_internos", materials=["PWR_Inconel_718"]),
               coll, sysobj, props=info(
        "Muelle de sujeción de los internos",
        "Anillo elástico que, al apretar la tapa, mantiene comprimidos los internos "
        "superiores e inferiores contra el escalón de la vasija.",
        "Acero inoxidable de alta resistencia.",
        "Un único muelle anular alojado en una ranura de la brida del barrilete.",
        "Se dibuja como anillo de sección rectangular.",
        "#d94a4a", ex))

    # --- tubos guía ----------------------------------------------------------------------
    mb = MeshBuilder()
    for dx, dy in rset:
        mb.cylinder(dx * pitch, dy * pitch, u1, P["z_guide_top"], 0.095, 16, r_in=0.083)
    new_object("Tubos_guia", mb.to_mesh("Tubos_guia", materials=["PWR_Acero_inox_304"]),
               coll, sysobj, props=info(
        "Tubos guía de barras de control",
        "Guían y protegen del caudal transversal a los haces de barras de control "
        "cuando están extraídos del núcleo.",
        "Acero inoxidable austenítico tipo 304.",
        "Uno por cada haz de control.",
        "Tubo cilíndrico continuo; los reales son de sección compuesta con placas guía "
        "interiores. Diámetro y cota superior aproximados.",
        "#c9a227", ex))

    # --- columnas soporte --------------------------------------------------------------------
    mb = MeshBuilder()
    cols = support_column_cells(cells, rset)
    for dx, dy in cols:
        mb.cylinder(dx * pitch, dy * pitch, u1, s0, 0.06, 12, r_in=0.045)
    new_object("Columnas_soporte", mb.to_mesh("Columnas_soporte", materials=["PWR_Acero_inox_304"]),
               coll, sysobj, props=info(
        "Columnas soporte superiores",
        "Unen la placa soporte superior con la placa superior del núcleo y transmiten "
        "las cargas; parte de ellas aloja termopares de salida del núcleo.",
        "Acero inoxidable austenítico tipo 304.",
        f"{len(cols)} columnas. Por la tapa salen 65 termopares de salida del núcleo.",
        "Posiciones esquemáticas; tubos lisos.",
        "#58a55c", ex))
    return sysobj


def build_reactivity_control(root, rccas):
    coll, sysobj = new_system(root, "05_Control_de_reactividad", "Control de reactividad",
                              "Barras de control y sus mecanismos de accionamiento.")
    pitch, rp = P["fa_pitch"], P["rod_pitch"]
    travel = P["rcca_travel"]
    z_active_top = P["z_core_bottom"] + 0.10 + (P["rod_len"] + P["fa_active"]) / 2

    # --- haz de barras de control (malla compartida) ------------------------------------
    L = P["rcca_rodlet_len"]
    mb = MeshBuilder()
    for i, j in thimble_lattice():
        mb.cylinder(i * rp, j * rp, 0.0, L, 0.0048, 6)
    mb.box(-0.08, 0.08, -0.08, 0.08, L - 0.02, L)
    mb.cylinder(0, 0, L, L + 0.20, 0.03, 10)
    mb.cylinder(0, 0, L + 0.20, L + 0.20 + P["rcca_shaft_len"], 0.022, 8)
    mesh = mb.to_mesh("Haz_barras_control", materials=["PWR_Barra_control"])
    grp = new_empty("Barras_de_control", coll, sysobj, info(
        "Barras de control (53 haces RCCA)",
        "Absorben neutrones para regular la potencia y parar el reactor. En un disparo "
        "caen por gravedad al cortarse la corriente de los mecanismos.",
        "Absorbente de plata-indio-cadmio (80 %-15 %-5 %) en vaina de acero inoxidable 304.",
        "53 haces, cada uno con 24 varillas absorbentes que entran en los 24 tubos guía "
        "del elemento. Recorrido: 144 in (3,66 m) en pasos de 5/8 in. Peso del haz: 157 lb.",
        "Distribución de los haces en el núcleo esquemática; araña reducida a una "
        "placa; longitud del eje de accionamiento aproximada.",
        "#e08a1e", EXPLODE["rcca"], recorrido=travel))
    for dx, dy, tag in rccas:
        new_object(f"RCCA_{tag}", mesh, coll, grp,
                   location=(dx * pitch, dy * pitch, z_active_top + 0.04),
                   props={"detalle": f"Posición {tag}"})

    # --- mecanismos (malla compartida): adaptador, 3 bobinas, carcasa e indicador --------
    H = P["crdm_height"]
    prof = [(0, -0.25), (0.05, -0.25), (0.05, 0.55), (0.085, 0.55), (0.085, 0.70)]
    for k in range(3):                                   # tres bobinas [NRC]
        zc = 0.70 + 0.30 * k
        prof += [(0.16, zc), (0.16, zc + 0.22), (0.085, zc + 0.22), (0.085, zc + 0.30)]
    z_h = 1.60
    prof += [(0.045, z_h), (0.045, z_h + 0.10), (0.075, z_h + 0.10),
             (0.075, z_h + 0.10 + travel), (0.045, z_h + 0.10 + travel), (0.045, H), (0, H)]
    mesh = MeshBuilder().lathe(prof, P["seg_small"]).to_mesh("Mecanismo_CRDM", materials=["PWR_CRDM"])
    grp = new_empty("Mecanismos_accionamiento", coll, sysobj, info(
        "Mecanismos de accionamiento (53 CRDM)",
        "Mecanismos electromagnéticos de trinquetes que suben o bajan paso a paso el "
        "eje de cada haz y lo sueltan en caso de disparo.",
        "Contención de presión de acero inoxidable 304; piezas magnéticas de inoxidable "
        "de la serie 400.",
        "Un mecanismo por haz. Tres bobinas magnéticas mueven los trinquetes en pasos "
        "de 5/8 in. La pila de bobinas del indicador de posición cubre los 144 in de "
        "recorrido. Diseño: 2485 psig y 650 °F.",
        "Cuerpo de revolución macizo; sin trinquetes, cableado ni ventilación. Altura "
        "total y diámetros aproximados.",
        "#c0504d", EXPLODE["crdm"]))
    for dx, dy, tag in rccas:
        x, y = dx * pitch, dy * pitch
        new_object(f"CRDM_{tag}", mesh, coll, grp, location=(x, y, head_outer_z(math.hypot(x, y))),
                   props={"detalle": f"Posición {tag}"})
    return sysobj


# ============================================================================
# 7. EXPORTACIÓN
# ============================================================================
def output_dir():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--out" in argv:
        return os.path.abspath(argv[argv.index("--out") + 1])
    if bpy.data.filepath:
        return os.path.dirname(bpy.data.filepath)
    here = globals().get("__file__", "")
    if here and os.path.isfile(here):
        return os.path.dirname(os.path.abspath(here))
    return os.path.expanduser("~")


def export_glb(root):
    path = os.path.join(output_dir(), P["glb_name"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ours = set(root.all_objects)
    for o in bpy.context.view_layer.objects:
        o.select_set(o in ours)
    bpy.ops.export_scene.gltf(
        filepath=path, export_format="GLB", use_selection=True,
        export_apply=True, export_extras=True, export_yup=True,
        export_cameras=False, export_lights=False, export_animations=False,
        export_draco_mesh_compression_enable=P["use_draco"])
    print(f"[PWR] GLB exportado: {path} ({os.path.getsize(path) / 1024:.0f} kB)")
    return path


# ============================================================================
# 8. PROGRAMA PRINCIPAL
# ============================================================================
def main():
    root = reset_root()
    cells = core_cells()
    rccas = rcca_cells(cells)
    assert len(cells) == 193 and len(rccas) == 53, (len(cells), len(rccas))

    build_vessel(root, cells)
    build_lower_internals(root, cells)
    build_core(root, cells)
    build_upper_internals(root, cells, rccas)
    build_reactivity_control(root, rccas)

    n_tri = sum(sum(len(p.vertices) - 2 for p in o.data.polygons)
                for o in root.all_objects if o.type == "MESH")
    print(f"[PWR] {len(root.all_objects)} objetos, {len(cells)} elementos, "
          f"{len(rccas)} haces de control, {n_tri} triángulos (contando instancias)")
    if P["export_glb"]:
        export_glb(root)


if __name__ == "__main__":
    main()
