# Project Roadmap — Blender Copilot (güncel)

**CURRENT: v1.1.0 implemented (2026-09-27) — 682 unit tests OK, hardening green, headless 25/25 SUITES PASS (Blender 5.2.2 LTS).**
Kalan: 1 canlı GUI turu (HUD, approval kartı, Anthropic anahtarlı vision, asset undo).
Tamamlanan işlerin geçmişi (M1–M9, v1.0, v1.1): `CHANGELOG.md`. Bu dosya sadece ileriyi gösterir.

---

## v1.2 Roadmap (2026-09-27)

Hedef: v1.1'i Blender-runtime'da mühürlemek + operasyonu büyütmek. Sıra: doğrulama önce, yeni özellik sonra.

### v1.2.0 — Blender-Runtime Mühürleme (öncelik 1)
- [x] Headless suite'ler 23 -> 25: `test_asset_import.py` (6/6: import + `perform_undo`/`redo`, verifier, guardlar), `test_anthropic_roundtrip.py` (Messages SSE -> tool -> verify -> sentez) — 25/25 PASS (Blender 5.2.2 LTS).
- [ ] Canlı GUI kabul: Anthropic anahtarıyla approval kartı, `max_side=256` vision turu, asset import undo (`Ctrl+Z`).
- [ ] Performans: 500+ obje sahnede `AssetLibrary.refresh()` + `LocalIndex.query()` süresi (<200ms hedef, timer_bridge 5ms bütçesi korunur).

### v1.2.1 — Asset Browser Derinleştirme
- [ ] Preferences: asset library dizin seçici + `BLENDER_AI_ASSET_DIR` göstergesi; N-Panel arama kutusu + sonuç listesi (substring + skor).
- [ ] Thumbnail: `.blend` önizleme için `capture_viewport(max_side=256)` isteğe bağlı üretim; disk yazımı yok (önbellek).
- [ ] `import_asset` konumu: opsiyonel `location` argümanı (verifier'a `location` epsilon kuralı ekle).

### v1.2.2 — Update Akışı + Topluluk Sürümü
- [ ] N-Panel Diagnostics: "Check for Updates" butonu + sonuç rozeti (`Up to date` / `vX.Y.Z available`); opt-in `auto_check` (default False).
- [ ] Dağıtım: Extensions platform paketi, `blender_manifest.toml` sürüm disiplini (minor bump kuralı).
- [ ] Dokü: video/onboarder yerine kısa EN/TR "v1.2 live verification" notu (GUI test kanıtıyla).

### v1.3 Adayları (deferred, söz yok)
- Text-to-3D (`generate_3d_asset`) araştırması; harici servis seçimi yok.
- Controlled Python yürütme katmanı (yok; `exec` yasağı sürüyor).

Kabul kapısı (tümü): `python tests/run_unit_tests.py` yeşil ✅ + headless 25/25 ✅ + 1 canlı GUI turu ⬜ + hardening yeşil ✅.
