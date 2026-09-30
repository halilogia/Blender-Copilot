# BLENDER AI COPILOT — TEKNİK DURUM HARİTASI (SOURCE OF TRUTH)

## 1. Ürün Tanımı: Mevcut Durum vs. Hedef Ürün

### Ürün Hedefi (Vision)
> **Blender AI Copilot'un uzun vadeli amacı:**  
> Kullanıcı doğal dil talebini sahne bağlamını anlayarak planlayan, semantic Blender tools ve gerektiğinde harici 3D generation servislerini kullanan, yaptığı değişiklikleri doğrulayan ve güvenli onay mekanizmasıyla Blender sahnesinde gerçekleştiren agentic bir copilot olmaktır.

### Mevcut Durum vs. Hedef Ürün Ayrımı
- **CURRENT (v1.13.0, 2026-09-30, 811 unit test OK):** M1–M9 + v1.0 + v1.1 tamamlanmış; sahneyi okuyabilen (`inspect_*`), güvenli mutasyon yapabilen (`create_primitive`, `transform_object`, `delete_object`, camera/light/modifier/shading/duplicate, **`import_asset`**), her mutasyonda undo state oluşturan, riskli eylemleri `PendingApproval` ile durduran, `ChangeVerifier` ile doğrulayan, vision (`capture_viewport` + `max_side`, Anthropic native multimodal) + stdlib local embedding + check-only auto-update içeren **semantic Blender assistant**; v1.9.0 ile yerel MCP köprüsü, `animate_sequence` (sahne oynatma), yüz ifadeleri ve dudak senkronu, procedural müzik, karakter kütüphanesi ve bükülen uzuvlar, `polish_model`, film araçları (`set_look`, `camera_settings`, `edit_video`, `render_shots`), karakter araçları (`rig_character`, `animate_character`), sinema araçları (`set_environment`, `camera_move`, `render_image`, `render_animation`) (`bridge/`, Claude Code eklentisi) ve modelleme araçları (`create_mesh`, `mesh_edit`, `export_gltf` ...) eklendi.
- **TARGET (Hedeflenen Ürün):** Planning + mutation + verification + vision + materials + asset browser derinleştirme + controlled scripting + opsiyonel external 3D generation yeteneklerine sahip tam kapsamlı **agentic copilot** (v1.2: Blender-runtime mühürleme; v1.3 adayı: text-to-3D araştırması).

---

## 2. Rol Haritası

| Rol | Sorumlu | Sorumluluk Alanı |
| :--- | :--- | :--- |
| **Product Owner** | **Kullanıcı** | Nihai karar verici, vizyon, kabul kriterleri, önceliklendirme ve canlı kabul testleri. |
| **Technical Architect** | **ChatGPT** | Üst düzey mimari tasarım, servis/araç araştırmaları ve stratejik yol haritası. |
| **Implementation Agent** | **Antigravity** | Kod geliştirme, refactoring, thread güvenliği ve yerel test otomasyonu. |
| **3D / AI Research** | **ChatGPT + Antigravity** | Text-to-3D sağlayıcıları, model yetenekleri ve Blender API kısıtları araştırması. |
| **Manual QA** | **Kullanıcı** | Gerçek Blender GUI, 9Router, canlı model ve etkileşim doğrulaması. |
| **Automated QA** | **Antigravity** | Pure Python unit testleri ve headless Blender test suite'leri. |

---

## 3. Mimari İlkeler ve Sınırlar

1. **Strict Thread Boundary**:
   - **Background Worker Thread**: Yalnızca HTTP I/O, SSE streaming ve JSON deserialization yürütür. `bpy` modülüne ve Blender veri bloklarına doğrudan erişimi kesinlikle engellenmiştir.
   - **Blender Main Thread**: Tüm sahne sorguları, mutasyonlar, UI çizimleri ve undo çağrıları yalnızca `bpy.app.timers` (`TimerBridge`) üzerinden ana iş parçacığında çalıştırılır.
2. **Deterministic Semantic Tools Only**:
   - Güvenlik ve stabilite gereği doğrudan `exec()` veya `eval()` ile serbest Python kodu çalıştırma yaklaşımı kullanılmaz. Eylemler şeması önceden tanımlı araçlar (`BaseTool`) üzerinden yürütülür.
3. **Blender Undo Entegrasyonu**:
   - Her başarılı mutasyon için Blender undo state oluşturulur (`bpy.ops.ed.undo_push()`) ve mutasyon tek bir undo adımı olarak tasarlanır.
4. **Deterministic Approval Gate**:
   - Onay kararı LLM'e bırakılamaz. `ApprovalPolicy`, risk seviyesi `MEDIUM` veya `HIGH` olan araç çağrılarını yakalar ve `PENDING_APPROVAL` durumuna geçirir. Kullanıcı açık onay vermeden eylem yürütülmez.
5. **Provider-Agnostic Engine (v1.1: dual dialect)**:
   - Sistem belirli bir modele kilitli değildir; 9Router veya OpenAI uyumlu herhangi bir endpoint üzerinden çalışır. Resmî OpenAI kaynaklarında yer alan `gpt-6-astra` API modeli de dahil olmak üzere OpenAI uyumlu tüm modeller bu çerçevede desteklenen sağlayıcı seçenekleri arasındadır (önceki "Astra yok" tespiti kapatılmıştır).
   - v1.1 ile ikinci kutsanmış lehçe eklendi: Anthropic Messages (`agent/anthropic_provider.py`, `POST /v1/messages`). Seçim deterministiktir (`Config.provider`, `BLENDER_AI_PROVIDER`, Preferences dropdown); LLM seçimi tahmin etmez. Her iki lehçe aynı `SSEParser` + `ToolCallAccumulator` + multimodal gate disiplinini paylaşır.
6. **Credential Hygiene**:
   - API anahtarları sahneye, WindowManager'a, `.blend` dosyasına veya loglara kaydedilmez.

---

## 4. Yol Haritası (Roadmap)

### Tamamlanan Fazlar
- **M1 — Grounding:** Sahne, seçim, obje, materyal ve mesh okuma araçları (`inspect_*`).
- **M2 — Provider / AgentRuntime:** SSE streaming, tool-call accumulation, context builder ve çift yönlü tool döngüsü.
- **M2.9 — Native GPU Viewport Overlay:** Viewport üzerinde çalışan modal HUD arayüzü (`Alt+Space`).
- **M3.1 — Safe Mutation + Undo:** `create_primitive`, `transform_object`, `delete_object` ve `undo_push` entegrasyonu.
- **M4.1 — Deterministic Approval Gate:** Risk seviyeleri, `PendingApproval`, Viewport HUD onay kartı ve `Y`/`N` klavye kısayolları.
  *(Not: Onay UX iyileştirmeleri zorunlu bir milestone değil, bağımsız bir UI backlog maddesidir).*

### Tamamlanan Yeni Fazlar (v1.1, 2026-09-27)
- **v1.1-A — Vision Completion:** `capture_viewport(max_side)` maliyet kalkanı, Anthropic native provider, stdlib local embedding.
- **v1.1-B — Check-Only Auto-Update:** `core/update_check.py` + `HttpClient.get()` + `ai_sidebar.check_updates` (indirme yok).
- **v1.1-C — Local Asset Browser:** `agent/asset_index.py` + `import_asset` + verifier `import` kuralı.

### Gelecek Fazlar (v1.2 — NEW)
- **v1.2.0 — Blender-Runtime Mühürleme:** headless 25/25 (`test_asset_import`, `test_anthropic_roundtrip`), canlı GUI kabul, 500+ obje performans.
- **v1.2.1 — Asset Derinleştirme:** Preferences dizin seçici, N-Panel arama, 256px thumbnail, opsiyonel `location`.
- **v1.2.2 — Update + Topluluk Sürümü:** Diagnostics rozeti, opt-in `auto_check`, Extensions paketi.
- **v1.3 Adayı (söz yok) — External Text-to-3D:** `generate_3d_asset` araştırması; servis seçimi yok. Controlled Python yok (`exec` yasağı sürüyor).

---

## 5. Harici 3D Üretim Prensibi (External 3D Generation Axiom)

Harici 3D entegrasyonunda mimari ayrım şu şekildedir:

$$\text{LLM (Orkestratör / Planlayıcı)} \neq \text{3D Model Üreticisi (Generator)}$$

```text
[ KULLANICI ]
     │ Doğal dil talebi
     ▼
[ LLM Provider ] (Planlayıcı / Orkestratör)
     │
     └── Gelecekteki Araç Adayı: generate_3d_asset(prompt, ...)
              │ (Henüz implementasyon başlamadı — tasarım aşamasında)
              ▼
     [ Harici 3D Servis / Model Adayları ]
     (Temsilî adaylar: Meshy, Tripo, Hyper3D Rodin, TRELLIS.2 vb.)
              │
              └── Çıktı: .glb / .obj
                       │
                       ▼
     [ Blender Adapter & Scene Host ]
              │
              ├── Dosyayı içe aktarır ve sahneye yerleştirir
              ├── Undo state oluşturur
              └── Durumu doğrular (Verification)
```

> **Önemli Not:** `generate_3d_asset` aracı gelecekteki bir semantik araç adayıdır; şu an implementasyonu başlamamıştır. Listelenen 3D servisleri (Meshy, Tripo, Rodin, TRELLIS.2) yalnızca **aday sağlayıcılar/araştırma alternatifleridir**; henüz bir servis seçilmemiş veya nihai entegrasyon kararı verilmemiştir.

---

## 6. Test Durumu ve Standartlar

- **Son doğrulanan otomatik test sonucu (2026-09-27):**
  - `811 Pure Python unit test` — `python tests/run_unit_tests.py` OK (hardening dahil).
  - `25/25 headless Blender suite` PASS (Blender 5.2.2 LTS) — `test_asset_import.py` (6/6) ve `test_anthropic_roundtrip.py` dahil.
  - Yeni suite'ler: `test_anthropic_provider`, `test_local_embed`, `test_update_check`, `test_asset_browser`.
  - Kalan: 1 canlı GUI turu (v1.2.0).
- **Doğrulama Ayrımı:**
  - **AUTOMATED**: Yalnızca Antigravity tarafından scriptler ile koşturulabilen birim ve headless entegrasyon testleridir.
  - **MANUAL**: Gerçek Blender GUI, canlı 3D Viewport HUD, canlı 9Router/Model gecikmesi ve kullanıcı klavye/fare etkileşimlerini içerir. Bu testler yalnızca **Kullanıcı** tarafından gerçek arayüzde bizzat icra edildiğinde "Doğrulandı" statüsü kazanır.

---

*Bu metin, proje için resmi ve bağlayıcı teknik durum belgesi (Source of Truth) olarak kilitlenmiştir.*
