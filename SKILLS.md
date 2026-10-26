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

---

## ✅ Tamamlanma Kriteri (Definition of Done)

1. Eklenti Blender'a zip olarak yüklenip etkinleştirildiğinde hata vermemeli (`bl_info` eksiksiz olmalı).
2. Yapılan her modelleme eylemi `Ctrl+Z` ile tek seferde geri alınabilir olmalı.
3. Dokümantasyon 200 satırı aşmamalı ve `TASKS.md` güncel tutulmalı.
