# 📋 Blender Copilot Görev Takibi (TASKS.md)

---

## 🚀 Aktif Sprint (v2.1)
- [x] **AssetSpec & Parametrik Geometri Derleyicisi:** `core/asset_spec.py` kısıt çözücü, P0 operatörleri (`loft_profiles`, `place_on_socket`, `create_from_spec`) ve manifold/z-fighting kalite denetimleri
- [x] **Ajan Becerileri & Modelleme Hattı:** 5 aşamalı prosedürel modelleme (`blender-procedural-pipeline`), optimizasyon denetimi (`blender-asset-optimization`), araç uzmanlığı (`blender-vehicle-artist`) ve karakter modelleme (`blender-character-artist`) becerilerinin entegrasyonu
- [x] **Core Docs Standardizasyonu:** KNOWLEDGE, TASKS ve SKILLS dosyalarının tamamlanması, public yol anonimizasyonları ve repoya senkronizasyon
- [ ] **Geometry Nodes Desteği:** Node tree yapısını ajanın okuyabilmesi ve procedürel nodelar ekleyebilmesi
- [ ] **Shader Editor Node Otomasyonu:** Principled BSDF tabanlı materyallerin ajan tarafından bağlanması

---

## ⏳ Backlog
- [ ] Blender 4.2+ Extensions platformu manifest uyumluluğu
- [ ] Rigging ve Weight Paint asistanı
- [ ] Düşük poligon (Low Poly) optimizasyon ve Bake otomasyonu

---

## ✅ Tamamlananlar (v2.0)
- [x] Blender 4.x N-Panel (Sidebar) UI arayüzü
- [x] Sahne hiyerarşisi, aktif nesne ve mesh verisini okuma
- [x] BMesh üzerinden doğrudan geometri üretimi
- [x] Tek hamlede atomik Undo/Redo desteği
- [x] Model seçim ve soru netleştirme paneli
