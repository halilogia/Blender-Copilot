# Tested recipes (all built and exported through the MCP tools, Blender 5.2)

Arguments are shown as `tool(arg=value, ...)`. `prim(...)` = `create_primitive(...)` followed by `apply_transform(object_name=..., location=false)`. Colours are [r, g, b]; add alpha 1.0 for `base_color`. Every recipe ends with `set_origin`, `export_gltf`, `frame_view`, `capture_viewport`.

## Crate (1 m, 204 triangles)
```
prim(CUBE, name="Crate", location=[0,0,0.5], scale=[0.94,0.94,0.94])        set_material Crate "CrateWood" [0.62,0.42,0.22] roughness 0.85
4 posts:  prim(CUBE, "CrPost{i}", loc=(±0.5, ±0.5, 0.5), scale=[0.09,0.09,1.0])          material "CrateFrame" [0.34,0.2,0.09]
8 rim beams (top and bottom, z = 0.045 and 0.955): scale [1.0,0.09,0.09] on the two Y sides, [0.09,1.0,0.09] on the two X sides
4 side slats: loc (0,±0.5,0.5) scale [0.86,0.03,0.1] and (±0.5,0,0.5) scale [0.03,0.86,0.1]
join_objects(all parts + Crate -> "Crate")   set_origin BOTTOM_CENTER   export_gltf(["Crate"], "crate.glb")
```
A single inset cube looks flat without textures; darker frame beams over a lighter body read as a crate.

## Barrel (0.9 m tall, 564 triangles)
```
prim(CYLINDER, "Barrel", loc=(0,0,0.45), scale=[0.6,0.6,0.9])
mesh_edit(Barrel, INSET_FACES, faces={direction:"+Z", threshold:0.9}, thickness=0.07, depth=-0.03)
mesh_edit(Barrel, BEVEL_EDGES, width=0.015, segments=1, sharp_angle=40)
set_material Barrel "BarrelPaint" [0.16,0.27,0.42] roughness 0.45 metallic 0.3
2 bands: prim(CYLINDER, "BarrelBand{i}", loc=(0,0,0.18 / 0.72), scale=[0.64,0.64,0.07]) material "BarrelSteel" [0.32,0.33,0.35] metallic 0.8
join_objects([Barrel, bands] -> "Barrel")   set_origin BOTTOM_CENTER   export_gltf
```

## Tree (about 4.6 m, 364 triangles)
```
prim(CYLINDER, "Trunk", loc=(0,0,1.1), scale=[0.34,0.34,2.2]);  mesh_edit(Trunk, SCALE_TO_HEIGHT_TAPER, top_scale=0.55)
material "Bark" [0.28,0.19,0.12] roughness 0.95
3 crowns: prim(ICOSPHERE, "Crown{i}", size=2.8 / 1.9 / 2.0, scale=[1,1,0.85], loc=(0,0,3.4), (0.8,0.3,2.7), (-0.7,-0.4,2.9))  material "Leaves" [0.2,0.38,0.17]
join_objects([Trunk, crowns] -> "Tree")   set_origin BOTTOM_CENTER   export_gltf
```
Flat shading (the default) gives the faceted low-poly look.

## Rock (24 triangles: use as a background pebble; raise DECIMATE ratio for a hero rock)
```
prim(ICOSPHERE, "Rock", loc=(0,0,0.4), scale=[1.0,0.8,0.6], size=1.3);  add_shape_modifier(Rock, DECIMATE, ratio=0.3)   material "Stone" [0.42,0.41,0.38]
set_origin BOTTOM_CENTER   export_gltf   (export applies the modifier)
```

## Sandbag row (6 bags, 360 triangles)
```
prim(CUBE, "Bag", loc=(0,0,0.14), scale=[0.62,0.34,0.27]);  mesh_edit(Bag, BEVEL_EDGES, width=0.07, segments=2)
material "Canvas" [0.62,0.55,0.38] roughness 0.95;  add_shape_modifier(Bag, ARRAY, count=6, relative_offset=[1.02,0,0])
set_origin BOTTOM_CENTER   export_gltf
```

## Rifle (KAR98K-like, about 1.4 m, 184 triangles, forward = +Y)
```
stock     prim(CUBE, loc=(0,-0.42,-0.03), scale=[0.055,0.42,0.11])   wood [0.36,0.21,0.1]
fore-end  prim(CUBE, loc=(0, 0.30,-0.015), scale=[0.048,0.5,0.055])  wood
receiver  prim(CUBE, loc=(0,-0.02, 0.01), scale=[0.05,0.22,0.065])   metal [0.11,0.11,0.12] roughness 0.4 metallic 0.85
barrel    prim(CYLINDER, loc=(0, 0.62, 0.02), scale=[0.024,0.024,0.95], rotation=[1.5708,0,0])  metal
bolt      prim(CUBE, loc=(0.05,-0.06,0.03), scale=[0.07,0.025,0.025])   metal
sight     prim(CUBE, loc=(0, 1.05, 0.055), scale=[0.012,0.02,0.03])     metal
join_objects(all -> target receiver, new_name="Rifle")   set_origin BOUNDS_CENTER   export_gltf("rifle_kar98k.glb")
```

## Low-poly soldier (1.8 m, 188 triangles)
Boxes: torso (0,0,1.2) scale [0.44,0.24,0.6] uniform colour [0.34,0.36,0.28]; legs (±0.12,0,0.42) scale [0.17,0.2,0.84] trousers [0.2,0.21,0.17]; boots (±0.12,0.03,0.05) scale [0.19,0.3,0.1] [0.08,0.07,0.06]; arms (-0.3,0.05,1.22) scale [0.13,0.15,0.55] and a raised right arm (0.3,0.12,1.3) rotation [-0.9,0,0]; head cube (0,0,1.66) scale [0.2,0.22,0.24] skin [0.78,0.6,0.48]; helmet ICOSPHERE size 0.34 (0,0,1.76) scale [1,1.05,0.7] [0.27,0.3,0.24]; gun box (0.18,0.28,1.28) scale [0.05,0.75,0.08] dark metal. Join, `set_origin` BOTTOM_CENTER, export.

## Checks after building
`inspect_mesh` (dimensions, triangle count), `frame_view` ISO and FRONT with `overlays=false`, `capture_viewport`. If a part floats or sinks, fix its `location` with `transform_object` before joining.
