# Project Roadmap — Blender Copilot (güncel)

**CURRENT: v1.9.0 implemented (2026-09-30) — film araçları (38 kamera hareketi, ışık ve renk ayarı, çok planlı kurgu) + yerel MCP köprüsü + modelleme araçları + sinema araçları (ışık, kamera hareketi, MP4 render) + karakter animasyonu (rig, yürüme/koşma/nişan/el sallama/zıplama) + Claude Code eklentisi; 781 unit tests OK, hardening green, headless 32/32 SUITES PASS (Blender 5.2.2 LTS).**
Bitmiş işlerin kaydı `CHANGELOG.md`’de tutulur; bu dosya yalnızca kalan işi gösterir.

---

## v1.9.1 — Blender-Runtime Mühürleme (sıradaki)

Kapsam: kod değişimi yok (gerekmedikçe); v1.1’in makinede kanıtı.

- [ ] **Canlı GUI kabul turu** (manuel, kullanıcı):
  1. Anthropic anahtarıyla bir `delete_object` onayı: kart görünür, `Y` onaylar + sahne değişir, `N` reddeder + LLM’ye `USER_REJECTED` döner.
  2. `capture_viewport(max_side=256)` vision turu: `image_id` metadata döner, base64 diske düşmez.
  3. Asset import + `Ctrl+Z`: obje gelir, undo kaldırır, redo geri getirir.
  4. HUD çok satırlı yanıt taşmaz; N-Panel history + diagnostics görünür.
- [ ] **Performans probu**: 500+ objeli sahnede `AssetLibrary.refresh()` + `LocalIndex.query()` <200ms; `TimerBridge` 5ms tick bütçesi korunur.
- Kabul: yukarıdaki 4 madde işaretli + unit/headless yeşil kalır.

## v1.9.2 — Asset Browser Derinleştirme

- [ ] Preferences’a asset library dizin seçici + `BLENDER_AI_ASSET_DIR` göstergesi (`ui/preferences.py`).
- [ ] N-Panel arama kutusu + skorlu sonuç listesi (`ui/panel.py`, `agent/asset_index.py` `search()` reuse).
- [ ] İsteğe bağlı 256px `.blend` thumbnail (`capture_viewport(max_side=256)`, yalnızca önbellek, disk yazımı yok).
- [ ] `import_asset(location=...)` opsiyonel argümanı + verifier `location` epsilon kuralı + unit test.
- Kabul: yeni unit testler + headless `test_asset_import.py` yeşil + 1 GUI import turu.

## v1.9.3 — Update Akışı + Topluluk Sürümü

- [ ] N-Panel Diagnostics: "Check for Updates" butonu + sonuç rozeti (`Up to date` / `vX.Y.Z available`); opt-in `auto_check` (default False).
- [ ] Dağıtım: Extensions platform paketi + `blender_manifest.toml` sürüm disiplini (her release’te minor bump, `bl_info` senkron).
- [ ] Kısa EN/TR "v1.2 live verification" notu (GUI kanıtıyla; video/onboarder yok).
- Kabul: `main`’de sürüm 1.9.3, paket kurulur + açılır, check-updates rozeti canlıda görülür.

## v1.10 Adayları (deferred, söz yok)

- Text-to-3D (`generate_3d_asset`) araştırması; harici servis seçimi yok.
- Controlled Python yürütme katmanı yok; `exec`/`eval` yasağı sürüyor.

---

Kabul kapısı (tümü): unit yeşil ✅ + headless 32/32 ✅ + GUI turu ⬜ + hardening yeşil ✅.
Çalışma sırası: v1.9.1 -> v1.9.2 -> v1.9.3; v1.10’a kapı kapalı.
