# Demo kütüphanesi

Her model, boş bir Blender sahnesinde tek bir istemle **Claude Code ajanının** Blender Copilot MCP köprüsü üzerinden (yalnız izin listeli araçlar, rastgele Python yok) modellediği bir `.glb` dosyasıdır (`scripts/demo_bench_mcp.py`). İstem, sohbet ve ölçüm her demonun `BENCH/` klasöründe. Sayfada dört görünüm: izometrik, ön, sağ, üst.

Bütün modeller Claude Code (`claude-opus-5-5`) ile MCP köprüsü üzerinden yapıldı; eklentinin kendi Blender içi ajanıyla (9router vb.) bu şekilde test edilmedi.

Kullanmak için: `.glb` dosyasını Godot, Unity ya da Blender'a sürükle (Godot: `res://assets/models/` altına at).

| Model | İstem | Süre | Araç çağrısı | Üçgen | Boyut | Tarih |
|---|---|---|---|---|---|---|
| [barrel](barrel/) | Oyun için düşük poligonlu metal varil modelle (bantlı, kapaklı), dışa aktar. | 0.7 dk | 22 | 868 | 0.63x0.63x0.63 m | 20260930 |
| [campfire](campfire/) | Oyun için düşük poligonlu bir kamp ateşi modelle (taş halka, odunlar, alev), dışa aktar. | 1.5 dk | 42 | 1384 | 1.20x0.92x1.20 m | 20260930 |
| [cannon](cannon/) | Oyun için düşük poligonlu bir top (kanon) modelle: namlu, ahşap iki tekerlekli lav, birkaç mermi yığını. | 1.4 dk | 38 | 1284 | 3.08x0.97x1.57 m | 20260930 |
| [car](car/) | Oyun için düşük poligonlu bir araba modelle: alçak gövde, ayrı kaput ve bagaj hattı, eğimli cam kabin, ön ve arka far, tampon, dört tekerlek ve jant. Gövde ve kabin farklı renk olsun. Tekerlekler yere değsin, gövde tekerlek yuvalarıyla çıkıntı yapmasın. | 1.5 dk | 32 | 1104 | 4.00x1.80x1.50 m | 20260930 |
| [castle](castle/) | Oyun için düşük poligonlu küçük bir kale modelle: dört köşe kulesi, surlar ve mazgallar, kapı kulesi, ortada bir ana kule. | 1.4 dk | 54 | 1418 | 10.25x2.00x10.25 m | 20260930 |
| [chest](chest/) | Oyun için düşük poligonlu bir hazine sandığı modelle: ahşap gövde, kubbeli kapak, metal bantlar, kilit. | 1.3 dk | 25 | 120 | 0.90x0.77x0.67 m | 20260930 |
| [crate](crate/) | Bir oyun için düşük poligonlu ahşap sandık modelle, dışa aktar. | 1.1 dk | 37 | 156 | 0.82x0.80x0.82 m | 20260930 |
| [fence](fence/) | Oyun için düşük poligonlu ahşap bir çit modelle: dört-beş kazık ve iki yatay tahta, tek parça olarak bitişik dizilebilecek genişlikte. | 0.7 dk | 16 | 84 | 2.00x1.00x0.14 m | 20260930 |
| [house](house/) | Oyun için düşük poligonlu küçük bir köy evi modelle (duvar, çatı, kapı, pencere, baca), dışa aktar. | 1.1 dk | 23 | 100 | 4.60x4.20x3.79 m | 20260930 |
| [lamp](lamp/) | Oyun için düşük poligonlu bir sokak lambası modelle (direk, kol, abajur), dışa aktar. | 0.7 dk | 20 | 402 | 1.38x4.00x0.55 m | 20260930 |
| [mushroom](mushroom/) | Oyun için düşük poligonlu büyük bir mantar modelle: kırmızı şapka, beyaz benekler, krem gövde. | 1.0 dk | 27 | 1644 | 2.00x1.84x2.00 m | 20260930 |
| [rifle](rifle/) | Oyun için düşük poligonlu bir savaş dönemi tüfeği modelle: ahşap dipçik, metal namlu, sürgü, tetik koruması, nişangah, kayış. Namlu ileri (+Y) baksın, 1.1 m uzunlukta. | 1.6 dk | 34 | 1196 | 0.13x0.24x1.10 m | 20260930 |
| [robot](robot/) | Oyun için düşük poligonlu sevimli bir robot karakter modelle: kutu kafa, anten, iki göz, gövde, kollar, bacaklar, göğüste bir panel. | 1.0 dk | 29 | 536 | 1.00x1.00x1.00 m | 20260930 |
| [rock](rock/) | Oyun için düşük poligonlu bir kaya kümesi modelle: 3 farklı boyda düzensiz, köşeli kaya, birbirine yaslı, gri tonları ve üstünde biraz yosun yeşili. Zemine oturuyor olsun (alt yüz düz). | 1.1 dk | 23 | 114 | 1.82x1.04x1.76 m | 20260930 |
| [sailboat](sailboat/) | Oyun için düşük poligonlu küçük bir yelkenli tekne modelle: gövde, güverte, direk, iki yelken, dümen. | 1.2 dk | 21 | 324 | 3.10x4.10x1.20 m | 20260930 |
| [soldier](soldier/) | Oyun için düşük poligonlu bir asker karakteri modelle: kask, gövde, kollar, bacaklar, botlar, sırt çantası, elinde tüfek tutma pozunda kollar. Yaklaşık 1.8 m boyunda, T-pozu değil, hafif yürüyüş duruşu olsun; üniforma zeytin yeşili, kask koyu, cilt tonu ayrı. | 1.8 dk | 55 | 1504 | 1.56x3.63x4.80 m | 20260930 |
| [spaceship](spaceship/) | Oyun için düşük poligonlu bir uzay gemisi modelle: gövde, kokpit camı, iki kanat, iki motor ve motor alevleri, ayrı renkli şeritler. | 1.4 dk | 28 | 520 | 4.40x1.45x4.60 m | 20260930 |
| [sword](sword/) | Oyun için düşük poligonlu bir kılıç modelle (bıçak, siper, kabza, topuz), dışa aktar. | 0.9 dk | 17 | 230 | 0.16x0.98x0.05 m | 20260930 |
| [tank](tank/) | Oyun için düşük poligonlu bir tank modelle (gövde, palet, kule, namlu), dışa aktar. | 0.7 dk | 17 | 380 | 1.00x1.00x1.00 m | 20260930 |
| [tent](tent/) | Oyun için düşük poligonlu bir kamp çadırı modelle: üçgen çadır, giriş açıklığı, iki kazık ve ip. | 1.2 dk | 21 | 294 | 1.80x1.35x3.54 m | 20260930 |
| [tree](tree/) | Oyun için düşük poligonlu bir çam ağacı modelle, dışa aktar. | 1.2 dk | 28 | 310 | 5.33x2.65x5.33 m | 20260930 |
| [watchtower](watchtower/) | Oyun için düşük poligonlu ahşap bir gözetleme kulesi modelle: dört ayak, çapraz destekler, platform, korkuluk, çatı, merdiven. | 2.0 dk | 44 | 386 | 3.20x7.50x3.20 m | 20260930 |
| [well](well/) | Oyun için düşük poligonlu bir taş kuyu modelle: yuvarlak taş halka, iki direk, küçük çatı, kova ve ip. | 1.1 dk | 23 | 652 | 2.40x3.30x1.60 m | 20260930 |
| [windmill](windmill/) | Oyun için düşük poligonlu bir yel değirmeni modelle: konik taş gövde, çatı, dört kanatlı pervane (çapraz çıtalı), kapı ve pencere. | 1.6 dk | 35 | 574 | 7.58x26.33x3.70 m | 20260930 |

## Galeri

**barrel**

![barrel](barrel/sheet.png)

**campfire**

![campfire](campfire/sheet.png)

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

**fence**

![fence](fence/sheet.png)

**house**

![house](house/sheet.png)

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

**soldier**

![soldier](soldier/sheet.png)

**spaceship**

![spaceship](spaceship/sheet.png)

**sword**

![sword](sword/sheet.png)

**tank**

![tank](tank/sheet.png)

**tent**

![tent](tent/sheet.png)

**tree**

![tree](tree/sheet.png)

**watchtower**

![watchtower](watchtower/sheet.png)

**well**

![well](well/sheet.png)

**windmill**

![windmill](windmill/sheet.png)
