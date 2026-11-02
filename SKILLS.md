# 📜 SKILLS.md — Blender Copilot Geliştirici & Ajan Kuralları

Bu doküman, Blender Copilot eklentisinde çalışan tüm ajanlar ve geliştiriciler için mimari standartları, `bpy` kurallarını ve tamamlanma kriterlerini tanımlar.

---

## 🎯 Temel İlkeler ve Sınırlar

- **Platform:** Blender 4.0+ ve dahili Python 3.10/3.11.
- **Harici Bağımlılık Yasağı:** Blender'ın kendi gömülü Python ortamını bozacak harici pip kütüphaneleri eklenemez.
- **Güvenli Sahne İşlemleri:** Doğrudan dosya sistemini silen veya kullanıcı dosyasını (`.blend`) kaydedilmeden üzerine yazan hiçbir otonom komut çalıştırılamaz.

---

## 🛠️ Mimari Kurallar

- **BMesh Önceliği:** Mesh düzenlemelerinde körlemesine `bpy.ops` yerine `bmesh` kullanılmalıdır.
- **Thread Güvenliği:** Uzak LLM API çağrıları asla UI thread'i kilitlememeli, `bpy.app.timers` ile senkronize edilmelidir.
- **AssetSpec & Geometri Derleyicisi:** LLM'lerin serbest koordinat uydurarak havada kalan veya birbirine giren parçalar üretmesini önlemek için doğrudan `bpy` kod yazmak yerine `create_from_spec` (AssetSpec IR) ve P0 operatörleri (`loft_profiles`, `place_on_socket`) tercih edilir. Kısıt çözücü yere basma ($Z=0$), parça proporsiyonları, soket kenetlenmesi ve manifold geometrisi matematiksel olarak derlenir. Tek atomik `Ctrl+Z` adımı garantilidir.

---

## 📦 Yerleşik Ajan Becerileri (Builtin Skills)

Eklenti ve Claude Code ortamı için `plugin/skills/` ve `.claude/skills/` altında tanımlı uzmanlıklar:

1. **`blender-game-assets`:** Düşük poligonlu temel oyun propları (sandık, varil, ağaç, kaya, silah).
2. **`blender-procedural-pipeline`:** 5 aşamalı prosedürel modelleme hattı (Blockout -> Bevel -> Boolean/Greeble -> Color ID -> glTF).
3. **`blender-asset-optimization`:** Poligon bütçesi denetimi, manifold temizliği, LOD0-LOD3 türetimi ve export kapısı.
4. **`blender-vehicle-artist`:** Araç, kamyon, tank, mech ve hava araçları için şasi, tekerlek ve kaporta modelleme akışı.
5. **`blender-character-artist`:** İnsanlar, insansı NPC'ler, askerler ve robotlar için T-pose proporsiyon ve modular low-poly modelleme akışı.
6. **`blender-character-animation`:** Karakter poses, walk-cycle ve animasyon zamanlama kılavuzları.
7. **`blender-cinematic-shot`:** Kamera kompozisyonu, ışıklandırma ve sinematik sahne kurulumu.
8. **`blender-to-godot`:** Blender Copilot ile Godot 4 AI Sidebar arasındaki glTF aktarım ve çarpışma köprüsü.
9. **`blender-lego-artist`:** LDraw CAD ve sanal LEGO modelleme akışı (LDU koordinatları, parça birleştirme, ABS plastik materyalleri ve fotogerçekçi Cycles/Eevee render).

---

## ✅ Tamamlanma Kriteri (Definition of Done)

1. Eklenti Blender'a zip olarak yüklenip etkinleştirildiğinde hata vermemeli (`bl_info` eksiksiz olmalı).
2. Yapılan her modelleme eylemi `Ctrl+Z` ile tek seferde geri alınabilir olmalı.
3. Dokümantasyon 200 satırı aşmamalı ve `TASKS.md` güncel tutulmalı.
