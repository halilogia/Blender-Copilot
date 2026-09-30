# Demo kütüphanesi

Her model, boş bir Blender sahnesinde tek bir istemle bir ajanın izin listeli araçlarla (rastgele Python yok) modellediği bir `.glb` dosyasıdır: ya **Claude Code** Blender Copilot MCP köprüsü üzerinden, ya da eklentinin **kendi Blender içi ajanı** 9router üzerinden (`Ajan` sütunu hangisi olduğunu söyler) (`scripts/demo_bench_mcp.py`). `shot-` ile başlayanlar **çekimdir**: ajan modeli yapar, ışığı kurar, kamerayı hareket ettirir ve MP4 render alır (yalnız sohbet modeli, elle müdahale yok). İstem, sohbet ve ölçüm her demonun `BENCH/` klasöründe. Modellerde sayfada dört görünüm var (izometrik, ön, sağ, üst); çekimlerde videodan dört kare.

Kullanmak için: `.glb` dosyasını Godot, Unity ya da Blender'a sürükle (Godot: `res://assets/models/` altına at); MP4 dosyaları herhangi bir oynatıcıda açılır.

| Model | Ajan | İstem | Süre | Araç çağrısı | Üçgen | Boyut | Tarih |
|---|---|---|---|---|---|---|---|
| [barrel](barrel/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu metal varil modelle (bantlı, kapaklı), dışa aktar. | 0.7 dk | 22 | 868 | 0.63x0.63x0.63 m | 20260930 |
| [barrel-claudesonnet46](barrel-claudesonnet46/) | Blender Copilot ajanı (9router) · ag/claude-sonnet-4-6 | Oyun için düşük poligonlu metal varil modelle (bantlı, kapaklı), dışa aktar. | 2.5 dk | 34 | 872 | 0.66x1.04x0.66 m | 20260930 |
| [campfire](campfire/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu bir kamp ateşi modelle (taş halka, odunlar, alev), dışa aktar. | 1.5 dk | 42 | 1384 | 1.20x0.92x1.20 m | 20260930 |
| [campfire-claudesonnet46](campfire-claudesonnet46/) | Blender Copilot ajanı (9router) · ag/claude-sonnet-4-6 | Oyun için düşük poligonlu bir kamp ateşi modelle (taş halka, odunlar, alev), dışa aktar. | 3.3 dk | 40 | 1090 | 1.10x0.55x1.10 m | 20260930 |
| [cannon](cannon/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu bir top (kanon) modelle: namlu, ahşap iki tekerlekli lav, birkaç mermi yığını. | 1.4 dk | 38 | 1284 | 3.08x0.97x1.57 m | 20260930 |
| [car](car/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu bir araba modelle: alçak gövde, ayrı kaput ve bagaj hattı, eğimli cam kabin, ön ve arka far, tampon, dört tekerlek ve jant. Gövde ve kabin farklı renk olsun. Tekerlekler yere değsin, gövde tekerlek yuvalarıyla çıkıntı yapmasın. | 1.5 dk | 32 | 1104 | 4.00x1.80x1.50 m | 20260930 |
| [castle](castle/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu küçük bir kale modelle: dört köşe kulesi, surlar ve mazgallar, kapı kulesi, ortada bir ana kule. | 1.4 dk | 54 | 1418 | 10.25x2.00x10.25 m | 20260930 |
| [chest](chest/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu bir hazine sandığı modelle: ahşap gövde, kubbeli kapak, metal bantlar, kilit. | 1.3 dk | 25 | 120 | 0.90x0.77x0.67 m | 20260930 |
| [crate](crate/) | Claude Code (MCP) · claude-opus-5-5 | Bir oyun için düşük poligonlu ahşap sandık modelle, dışa aktar. | 1.1 dk | 37 | 156 | 0.82x0.80x0.82 m | 20260930 |
| [crate-claudesonnet46](crate-claudesonnet46/) | Blender Copilot ajanı (9router) · ag/claude-sonnet-4-6 | Bir oyun için düşük poligonlu ahşap sandık modelle, dışa aktar. | 2.0 dk | 25 | 168 | 1.01x1.52x1.01 m | 20260930 |
| [fence](fence/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu ahşap bir çit modelle: dört-beş kazık ve iki yatay tahta, tek parça olarak bitişik dizilebilecek genişlikte. | 0.7 dk | 16 | 84 | 2.00x1.00x0.14 m | 20260930 |
| [house](house/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu küçük bir köy evi modelle (duvar, çatı, kapı, pencere, baca), dışa aktar. | 1.1 dk | 23 | 100 | 4.60x4.20x3.79 m | 20260930 |
| [house-claudesonnet46](house-claudesonnet46/) | Blender Copilot ajanı (9router) · ag/claude-sonnet-4-6 | Oyun için düşük poligonlu küçük bir köy evi modelle (duvar, çatı, kapı, pencere, baca), dışa aktar. | 2.5 dk | 32 | 68 | 6.60x4.80x5.60 m | 20260930 |
| [house-geminiproagent](house-geminiproagent/) | Blender Copilot ajanı (9router) · ag/gemini-pro-agent | Oyun için düşük poligonlu küçük bir köy evi modelle (duvar, çatı, kapı, pencere, baca), dışa aktar. | 1.2 dk | 22 | 56 | 2.40x3.50x2.27 m | 20260930 |
| [house-spacebunnyalpha](house-spacebunnyalpha/) | Blender Copilot ajanı (9router) · openrouter/space-bunny-alpha | Oyun için düşük poligonlu küçük bir köy evi modelle (duvar, çatı, kapı, pencere, baca), dışa aktar. | 2.6 dk | 30 | 80 | 4.20x3.90x3.40 m | 20260930 |
| [lamp](lamp/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu bir sokak lambası modelle (direk, kol, abajur), dışa aktar. | 0.7 dk | 20 | 402 | 1.38x4.00x0.55 m | 20260930 |
| [mushroom](mushroom/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu büyük bir mantar modelle: kırmızı şapka, beyaz benekler, krem gövde. | 1.0 dk | 27 | 1644 | 2.00x1.84x2.00 m | 20260930 |
| [rifle](rifle/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu bir savaş dönemi tüfeği modelle: ahşap dipçik, metal namlu, sürgü, tetik koruması, nişangah, kayış. Namlu ileri (+Y) baksın, 1.1 m uzunlukta. | 1.6 dk | 34 | 1196 | 0.13x0.24x1.10 m | 20260930 |
| [robot](robot/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu sevimli bir robot karakter modelle: kutu kafa, anten, iki göz, gövde, kollar, bacaklar, göğüste bir panel. | 1.0 dk | 29 | 536 | 1.00x1.00x1.00 m | 20260930 |
| [rock](rock/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu bir kaya kümesi modelle: 3 farklı boyda düzensiz, köşeli kaya, birbirine yaslı, gri tonları ve üstünde biraz yosun yeşili. Zemine oturuyor olsun (alt yüz düz). | 1.1 dk | 23 | 114 | 1.82x1.04x1.76 m | 20260930 |
| [sailboat](sailboat/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu küçük bir yelkenli tekne modelle: gövde, güverte, direk, iki yelken, dümen. | 1.2 dk | 21 | 324 | 3.10x4.10x1.20 m | 20260930 |
| [shot-campfire-handheld-claudesonnet46](shot-campfire-handheld-claudesonnet46/) | Blender Copilot ajanı (9router) · ag/claude-sonnet-4-6 | Taş halkalı bir kamp ateşi modelle (odunlar, alev), gece ışığı kur ve elde çekilmiş gibi hafif titreyen (handheld) 4 saniyelik bir MP4 çek. | 3.4 dk | 34 | - | 4.0 sn video | 20260930 |
| [shot-castle-orbit-claudesonnet46](shot-castle-orbit-claudesonnet46/) | Blender Copilot ajanı (9router) · ag/claude-sonnet-4-6 | Bir kale modelle (kuleler, surlar), gün batımı ışığı kur ve kamerayı kalenin etrafında yavaşça döndürüp 5 saniyelik bir MP4 çek. | 3.7 dk | 56 | - | 5.0 sn video | 20260930 |
| [shot-castle-orbit-geminiproagent](shot-castle-orbit-geminiproagent/) | Blender Copilot ajanı (9router) · ag/gemini-pro-agent | Bir kale modelle (kuleler, surlar), gün batımı ışığı kur ve kamerayı kalenin etrafında yavaşça döndürüp 5 saniyelik bir MP4 çek. | 2.4 dk | 29 | - | 5.0 sn video | 20260930 |
| [shot-house-night-claudesonnet46](shot-house-night-claudesonnet46/) | Blender Copilot ajanı (9router) · ag/claude-sonnet-4-6 | Küçük bir köy evi modelle (duvar, çatı, kapı, pencere, baca), gece ışığı kur ve kamerayı evin çevresinde yay çizdirerek (arc) 4 saniyelik bir MP4 çek. | 2.4 dk | 21 | - | 8.0 sn video | 20260930 |
| [shot-robot-vertigo-spacebunnyalpha](shot-robot-vertigo-spacebunnyalpha/) | Blender Copilot ajanı (9router) · openrouter/space-bunny-alpha | Sevimli bir robot modelle, neon ışık kur ve dolly zoom (vertigo) efektiyle 3 saniyelik bir MP4 çek. | 5.0 dk | 49 | - | 5.0 sn video | 20260930 |
| [shot-soldier-dolly-claudesonnet46](shot-soldier-dolly-claudesonnet46/) | Blender Copilot ajanı (9router) · ag/claude-sonnet-4-6 | Elinde tüfek tutan düşük poligonlu bir asker modelle, kapalı hava (overcast) ışığı kur ve kamerayı askere yavaşça yaklaştıran (dolly_in) 4 saniyelik bir MP4 çek. | 3.7 dk | 36 | - | 4.0 sn video | 20260930 |
| [shot-tank-crane-claudesonnet46](shot-tank-crane-claudesonnet46/) | Blender Copilot ajanı (9router) · ag/claude-sonnet-4-6 | Düşük poligonlu bir tank modelle (gövde, palet, kule, namlu), gün batımı ışığında kamerayı yukarı kaldıran (crane_up) 4 saniyelik bir MP4 çek. | 2.8 dk | 29 | - | 4.0 sn video | 20260930 |
| [shot-tank-crane-geminiproagent](shot-tank-crane-geminiproagent/) | Blender Copilot ajanı (9router) · ag/gemini-pro-agent | Düşük poligonlu bir tank modelle (gövde, palet, kule, namlu), gün batımı ışığında kamerayı yukarı kaldıran (crane_up) 4 saniyelik bir MP4 çek. | 1.8 dk | 34 | - | 4.0 sn video | 20260930 |
| [soldier](soldier/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu bir asker karakteri modelle: kask, gövde, kollar, bacaklar, botlar, sırt çantası, elinde tüfek tutma pozunda kollar. Yaklaşık 1.8 m boyunda, T-pozu değil, hafif yürüyüş duruşu olsun; üniforma zeytin yeşili, kask koyu, cilt tonu ayrı. | 1.8 dk | 55 | 1504 | 1.56x3.63x4.80 m | 20260930 |
| [spaceship](spaceship/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu bir uzay gemisi modelle: gövde, kokpit camı, iki kanat, iki motor ve motor alevleri, ayrı renkli şeritler. | 1.4 dk | 28 | 520 | 4.40x1.45x4.60 m | 20260930 |
| [sword](sword/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu bir kılıç modelle (bıçak, siper, kabza, topuz), dışa aktar. | 0.9 dk | 17 | 230 | 0.16x0.98x0.05 m | 20260930 |
| [sword-claudesonnet46](sword-claudesonnet46/) | Blender Copilot ajanı (9router) · ag/claude-sonnet-4-6 | Oyun için düşük poligonlu bir kılıç modelle (bıçak, siper, kabza, topuz), dışa aktar. | 2.5 dk | 32 | 120 | 0.50x1.40x0.10 m | 20260930 |
| [tank](tank/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu bir tank modelle (gövde, palet, kule, namlu), dışa aktar. | 0.7 dk | 17 | 380 | 1.00x1.00x1.00 m | 20260930 |
| [tank-claudesonnet46](tank-claudesonnet46/) | Blender Copilot ajanı (9router) · ag/claude-sonnet-4-6 | Oyun için düşük poligonlu bir tank modelle (gövde, palet, kule, namlu), dışa aktar. | 2.2 dk | 34 | 364 | 4.38x1.60x7.40 m | 20260930 |
| [tent](tent/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu bir kamp çadırı modelle: üçgen çadır, giriş açıklığı, iki kazık ve ip. | 1.2 dk | 21 | 294 | 1.80x1.35x3.54 m | 20260930 |
| [tree](tree/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu bir çam ağacı modelle, dışa aktar. | 1.2 dk | 28 | 310 | 5.33x2.65x5.33 m | 20260930 |
| [tree-claudesonnet46](tree-claudesonnet46/) | Blender Copilot ajanı (9router) · ag/claude-sonnet-4-6 | Oyun için düşük poligonlu bir çam ağacı modelle, dışa aktar. | 1.6 dk | 21 | 310 | 2.40x4.00x2.40 m | 20260930 |
| [watchtower](watchtower/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu ahşap bir gözetleme kulesi modelle: dört ayak, çapraz destekler, platform, korkuluk, çatı, merdiven. | 2.0 dk | 44 | 386 | 3.20x7.50x3.20 m | 20260930 |
| [well](well/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu bir taş kuyu modelle: yuvarlak taş halka, iki direk, küçük çatı, kova ve ip. | 1.1 dk | 23 | 652 | 2.40x3.30x1.60 m | 20260930 |
| [windmill](windmill/) | Claude Code (MCP) · claude-opus-5-5 | Oyun için düşük poligonlu bir yel değirmeni modelle: konik taş gövde, çatı, dört kanatlı pervane (çapraz çıtalı), kapı ve pencere. | 1.6 dk | 35 | 574 | 7.58x26.33x3.70 m | 20260930 |

## Galeri

**barrel**

![barrel](barrel/sheet.png)

**barrel-claudesonnet46**

![barrel-claudesonnet46](barrel-claudesonnet46/sheet.png)

**campfire**

![campfire](campfire/sheet.png)

**campfire-claudesonnet46**

![campfire-claudesonnet46](campfire-claudesonnet46/sheet.png)

**cannon**

![cannon](cannon/sheet.png)

**car**

![car](car/sheet.png)

**castle**

![castle](castle/sheet.png)

**chest**

![chest](chest/sheet.png)

**crate**

![crate](crate/sheet.png)

**crate-claudesonnet46**

![crate-claudesonnet46](crate-claudesonnet46/sheet.png)

**fence**

![fence](fence/sheet.png)

**house**

![house](house/sheet.png)

**house-claudesonnet46**

![house-claudesonnet46](house-claudesonnet46/sheet.png)

**house-geminiproagent**

![house-geminiproagent](house-geminiproagent/sheet.png)

**house-spacebunnyalpha**

![house-spacebunnyalpha](house-spacebunnyalpha/sheet.png)

**lamp**

![lamp](lamp/sheet.png)

**mushroom**

![mushroom](mushroom/sheet.png)

**rifle**

![rifle](rifle/sheet.png)

**robot**

![robot](robot/sheet.png)

**rock**

![rock](rock/sheet.png)

**sailboat**

![sailboat](sailboat/sheet.png)

**shot-campfire-handheld-claudesonnet46** ([video](shot-campfire-handheld-claudesonnet46/shot-campfire-handheld-claudesonnet46.mp4))

![shot-campfire-handheld-claudesonnet46](shot-campfire-handheld-claudesonnet46/sheet.png)

**shot-castle-orbit-claudesonnet46** ([video](shot-castle-orbit-claudesonnet46/shot-castle-orbit-claudesonnet46.mp4))

![shot-castle-orbit-claudesonnet46](shot-castle-orbit-claudesonnet46/sheet.png)

**shot-castle-orbit-geminiproagent** ([video](shot-castle-orbit-geminiproagent/shot-castle-orbit-geminiproagent.mp4))

![shot-castle-orbit-geminiproagent](shot-castle-orbit-geminiproagent/sheet.png)

**shot-house-night-claudesonnet46** ([video](shot-house-night-claudesonnet46/shot-house-night-claudesonnet46.mp4))

![shot-house-night-claudesonnet46](shot-house-night-claudesonnet46/sheet.png)

**shot-robot-vertigo-spacebunnyalpha** ([video](shot-robot-vertigo-spacebunnyalpha/shot-robot-vertigo-spacebunnyalpha.mp4))

![shot-robot-vertigo-spacebunnyalpha](shot-robot-vertigo-spacebunnyalpha/sheet.png)

**shot-soldier-dolly-claudesonnet46** ([video](shot-soldier-dolly-claudesonnet46/shot-soldier-dolly-claudesonnet46.mp4))

![shot-soldier-dolly-claudesonnet46](shot-soldier-dolly-claudesonnet46/sheet.png)

**shot-tank-crane-claudesonnet46** ([video](shot-tank-crane-claudesonnet46/shot-tank-crane-claudesonnet46.mp4))

![shot-tank-crane-claudesonnet46](shot-tank-crane-claudesonnet46/sheet.png)

**shot-tank-crane-geminiproagent** ([video](shot-tank-crane-geminiproagent/shot-tank-crane-geminiproagent.mp4))

![shot-tank-crane-geminiproagent](shot-tank-crane-geminiproagent/sheet.png)

**soldier**

![soldier](soldier/sheet.png)

**spaceship**

![spaceship](spaceship/sheet.png)

**sword**

![sword](sword/sheet.png)

**sword-claudesonnet46**

![sword-claudesonnet46](sword-claudesonnet46/sheet.png)

**tank**

![tank](tank/sheet.png)

**tank-claudesonnet46**

![tank-claudesonnet46](tank-claudesonnet46/sheet.png)

**tent**

![tent](tent/sheet.png)

**tree**

![tree](tree/sheet.png)

**tree-claudesonnet46**

![tree-claudesonnet46](tree-claudesonnet46/sheet.png)

**watchtower**

![watchtower](watchtower/sheet.png)

**well**

![well](well/sheet.png)

**windmill**

![windmill](windmill/sheet.png)
