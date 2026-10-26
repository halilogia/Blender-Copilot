# 🧠 Blender Copilot Mühendislik Hafızası (KNOWLEDGE.md)

Bu dosya, Blender Copilot eklentisinin Blender Python (`bpy`) API entegrasyon kararlarını (ADR) ve kritik tuzaklarını (Gotchas) belgeler.

---

## 🏛️ Mimari Karar Kayıtları (ADR)

### [ADR-01] Blender Context İzolasyonu ve bpy.ops Kısıtlaması
- **Karar:** Mümkün olan her yerde doğrudan `bpy.ops` çağırmak yerine düşük seviyeli `bpy.data` API'leri ve BMesh tercih edildi.
- **Gerekçe:** `bpy.ops` operatörleri aktif viewport, seçili alan (poll context) ve modal pencerelere sıkı sıkıya bağlıdır. Yanlış pencere bağlamında `RuntimeError: Operator bpy.ops.mesh... poll() failed_context` hatası verir.

### [ADR-02] Atomik Operatör İşlemleri ve Undo Yığını
- **Karar:** Ajanın her toplu modelleme veya materyal adımı tek bir özel `Operator` makrosu içine sarılarak kaydedilir.
- **Gerekçe:** Kullanıcının tek bir `Ctrl+Z` ile ajanın tüm adımını geri alabilmesini sağlamak.

---

## ⚠️ Kritik Teknik Tuzaklar (Gotchas)

### [GOTCHA-01] BMesh Serbest Bırakma (free) Zorunluluğu
- **Tuzak:** `bmesh.new()` veya `bmesh.from_edit_mesh()` sonrası `bm.free()` çağrılmazsa veya mesh'e yazmadan context değiştirilirse Blender çöker (Segmentation fault).
- **Çözüm:** `bmesh` işlemleri daima try/finally bloğunda veya `with` kalıbıyla emniyete alınır.

### [GOTCHA-02] UI Thread ve Arka Plan Model Çağrıları
- **Tuzak:** Yapay zeka HTTP çağrıları ana UI döngüsünde bekletilirse Blender arayüzü donar.
- **Çözüm:** Ajan istekleri arka plan `threading.Thread` içinde çalışır, sahne güncellemeleri ise `bpy.app.timers.register` ile ana thread'e taşınır.
