# Project Roadmap — Blender Copilot (güncel)

**CURRENT: v1.18.0 implemented (2026-09-30) — modelleme + malzeme presetleri + sinema / film + karakter + yerel MCP köprüsü + Claude Code eklentisi + `check_shot` + `check_model`; 835 unit tests OK, hardening green, headless 38/38 SUITES PASS (Blender 5.2.2 LTS).**
Bitmiş işlerin kaydı `CHANGELOG.md`’de tutulur; bu dosya yalnızca kalan işi gösterir.

## Yön (2026-09-30)

Çekirdek ürün: **AI’nin Blender sahnesini güvenilir biçimde anlaması, modellemesi, düzenlemesi, malzeme / ışık / kamera vermesi, sonucu doğrulaması** ve gerektiğinde animasyon üretmesi. Film, müzik, karakter animasyonu isteğe bağlı paketlerdir (`core/tool_packs.py`: yalnız istekte yüklenir). **Film tarafı dondurulur:** yeni kamera preset’i, müzik özelliği, prop, film efekti eklenmez; yalnız kalite ve çekirdek boşlukları kapatılır.

**Mimari karşılık (2026-09-30):** Godot'daki "dosya-öncelikli" Blender'da birebir olmaz (`.blend` ikili dosya). Karşılığı: canlı Blender datablock'ları çalışma alanıdır; her AI görevi bir işlem (task) olarak izlenir. ✅ Anlamsal anlık görüntü + fark (`task_report`), ✅ görev çapında geri alma ve doğrulama (`task_rollback`, panelde "Undo AI task"), ✅ doğrulama kapısı olarak `check_model` / `check_shot` (ajan çağırır). Bilerek yapılmadı: her görev için zorunlu Apply / Reject penceresi (geri alma sonradan daha az rahatsız eder), `.blend`'i kendiliğinden kaydetmek (kullanıcının kaydedilmemiş elle değişiklikleri olabilir; Ctrl+S kullanıcıya ait). Dosya tabanlı varlıklar (doku, `.glb`, görüntü, video) zaten dosya-öncelikli: geçici dosyaya yaz, doğrula, taşı.

Sıra (biri bitmeden sonrakine geçilmez; her adımda entegrasyon testi + ücretsiz modelle bir demo):

1. **Belge tutarlılığı** ✅ (rozet, test sayıları, bu dosya).
2. ✅ **`check_model`** (model kalite kontrolü, `check_shot`’ın modelleme karşılığı): ayrık geometri, non-manifold, ters normal, uygulanmamış ölçek, origin, zeminin altı, üçgen bütçesi, çakışan nesneler, sıfır hacimli parça, materyalsiz mesh, tekrarlı vertex, UV gerekli ama yok; her bulgu için düzelten araç önerisi. Ajan raporu okuyup kendi düzeltir.
3. **UV + doku hattı**: `unwrap_uv` (smart project / seam’li), `inspect_uv`, ve **preset malzemeleri dokuya pişirme** (`bake_material`): glTF dışa aktarımında procedural malzeme kaybolmasın (Godot’ya gerçek doku gitsin).
4. ✅ **Mesh düzenleme paketi** (araç sayısı artmaz, `mesh_edit` işlemleri derinleşir): loop cut, dissolve, bridge, boolean sonrası temizlik, normal çevirme / yeniden hesaplama, seçim (normal / alan / malzeme), ayır / birleştir.
5. ✅ **Dağıtma (scatter) ve arazi**: yol / alan boyunca örnekleme, rastgele ölçek ve dönüş; önce Python ile bağlı kopyalar, Geometry Nodes sonra.
6. **Gerçek armature / IK / NLA**: bilerek bekletiliyor. Parça tabanlı karakter `.glb` olarak Godot'ya animasyonuyla gidiyor; armature için `animate_character` tümüyle kemik pozuna taşınmalı (büyük iş, sohbet modelleri için kazanç belirsiz). Bir oyunda iskelet / retarget gerçekten gerekince açılır.
7. ✅ **Model başına ölçüm**: `scripts/model_report.py` (sonuçlar `docs/MODELS.md`), standart üç görev `bench-*`.

Bırakıldı: `animate_object` (düşük değer), yeni film / müzik özellikleri.

## Kullanıcıya ait: Canlı GUI kabul turu (bekliyor)

Kod değişimi gerektirmez; makinede kanıt:

- [ ] Bir `delete_object` onayı: kart görünür, `Y` onaylar + sahne değişir, `N` reddeder + LLM’ye `USER_REJECTED` döner.
- [ ] `capture_viewport(max_side=256)` vision turu: `image_id` döner, base64 diske düşmez.
- [ ] Asset import + `Ctrl+Z`: obje gelir, undo kaldırır, redo geri getirir.
- [ ] HUD çok satırlı yanıt taşmaz; N-Panel history + diagnostics görünür.
- [ ] 500+ objeli sahnede `AssetLibrary.refresh()` + `LocalIndex.query()` <200 ms.
- [ ] Yeni: Godot AI Sidebar → Ayarlar → Blender ile bağlantı, gerçek pencerede.

## Sonra (söz yok)

- Asset Browser arayüzü (dizin seçici, arama kutusu, thumbnail), update akışı rozeti, Extensions paketi.
- Serbest bpy betiği (`run_script`) yalnız sıkı kum havuzuyla (yalnız export klasörüne yazar, ağ ve silme kapalı, onaylı); `exec` / `eval` yasağı bu araç dışında sürer.
- Sculpt, Geometry Nodes serbest düzenleme.

---

Kabul kapısı (tümü): unit yeşil ✅ + headless 38/38 ✅ + GUI turu ⬜ (kullanıcı) + hardening yeşil ✅.
