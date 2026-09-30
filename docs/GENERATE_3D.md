# generate_3d: a trained 3D generator behind the same chat

Higgsfield-style tools make their models with trained generators. Blender Copilot's own tools build models from parts, which chat models do well for props and characters but not for organic or detailed shapes. `generate_3d` lets a trained text-to-3D or image-to-3D model do the modeling while the chat model still directs everything else: lighting, camera, characters, edit, music.

The add-on does **not** bundle or choose a generator. You point it at a service; any service that speaks the small contract below works. Türkçe özet en altta.

## Set it up

```
BLENDER_COPILOT_3D_URL=http://127.0.0.1:8765/generate     # required: where the generator listens
BLENDER_COPILOT_3D_KEY=...                                 # optional: sent as "Authorization: Bearer ..."
```

Set them in the environment Blender starts in (they are read at each call). The URL comes only from the environment, never from the model, so an agent cannot point the add-on at an arbitrary address. Local addresses (127.0.0.1, localhost) always work; a remote address needs Blender's online access to be on (Preferences, System, Network).

Try the pipeline without a GPU using the stand-in server, which returns a ready-made model from `demos/` whose name appears in the prompt:

```bash
python scripts/mock_3d_server.py --port 8765
```

## The contract

```
POST <BLENDER_COPILOT_3D_URL>
Content-Type: application/json
Accept: model/gltf-binary, application/json

{"prompt": "a stylised pine tree, low poly",     # required unless image_base64 is given
 "image_base64": "<png or jpg, base64>",          # optional: image to 3D
 "seed": 7,                                       # optional
 "texture": true}                                 # optional
```

The answer is one of:

- the `.glb` bytes (starts with `glTF`), any content type;
- JSON `{"glb_base64": "..."}`;
- JSON `{"glb_url": "https://..."}` (downloaded with a GET; same network rules);
- JSON `{"error": "message"}` or a non-2xx status: the message is shown to the model.

Files over 80 MB are refused. Wrappers for real engines (Hunyuan3D-2, TRELLIS, Meshy, Tripo, Rodin) are small: receive the JSON, call the engine, return the `.glb`. They are not bundled here and not tested by this project; the tests use the mock contract server (`tests/integration/test_generate_tools.py`).

## The tool

`generate_3d(prompt, name, image_file, height, seed, texture, timeout)`:

1. calls the service (Blender waits; generation can take minutes; up to 30 minutes with `timeout`);
2. saves `<name>.glb` in the export folder;
3. imports it, scales it to `height` meters and stands it on the ground at the origin under one root object;
4. returns the root name, triangle count and size. One undo step removes it.

After that: `set_environment`, `camera_move`, `render_animation`, `edit_video`, `make_soundtrack` as for any other model. A generated model is one solid mesh, so it suits props, scenery and static characters; for a character that walks or talks, model it from parts and rig it (`rig_character`).

## Why it is built this way

Chat models (ChatGPT, Claude, Gemini, free models) direct a deterministic toolset well, but the look of what they build from primitives is limited by the model. A trained 3D generator closes that gap for the assets themselves without changing anything else: the same prompts, the same tools, the same films.

## Türkçe özet

`generate_3d`, senin kurduğun eğitilmiş bir metinden/görselden 3D servisini çağırır (ör. yerel Hunyuan3D veya TRELLIS sunucusu). Eklenti bir üretici seçmez; `BLENDER_COPILOT_3D_URL` (ve isteğe bağlı `BLENDER_COPILOT_3D_KEY`) ortam değişkeni servisi gösterir, adres modelden değil yalnız ortamdan gelir. Servis basit bir sözleşmeye uyar: JSON istek (prompt, isteğe bağlı görsel ve seed), cevap `.glb` baytları, `glb_base64` ya da `glb_url`. Model içe aktarılır, istenen boya ölçeklenir ve zemine oturtulur; sonra ışık, kamera, kurgu ve müzik araçlarıyla çekilir. GPU olmadan denemek için `scripts/mock_3d_server.py` hazır modellerden birini döndürür.
