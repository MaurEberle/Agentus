# Ayarlar

Başlık çubuğundaki dişli. Solda bölümler: Görünüm, Kimlik bilgileri, Çalışma zamanı, Yardım sohbeti, MCP sunucuları, Veri, Hakkında. Bölüm değiştirirken kaydedilmemiş alanlar: Kal / At iletişim kutusu.

## Görünüm

Açık, koyu veya sistem — başlık dahil tüm uygulamada geçerlidir. **Dil** bayraklı bir açılır listedir: Deutsch, English, Español, Français, Türkçe, Português, 中文, 日本語, العربية. Parantezdeki ad, geçerli arayüz dilindeki çeviridir.

**Yardım düğmesi** anahtarı sağ alttaki baloncuğu gösterir veya gizler. Sohbet botunun **yapılandırması** baloncuk gizli olsa da **Yardım sohbeti** altındadır.

## Kimlik bilgileri

Bulut modelleri, web araması ve bazı MCP tarifleri için adlı sırlar. Oluştur: ad, tür, sır **bir kez**. Sonra yalnızca **maske**. Düzenleme sırrı değiştirebilir (boş = değişmez).

Türler arasında: xAI, OpenAI, Claude, Gemini, OpenAI uyumlu, web araması, GitHub, Azure, GitLab, Slack, Notion, Atlassian, Linear, Postgres, belirteç.

Yardım profili, bir ağ (LLM/araç) veya bir MCP sunucusu kimlik bilgisini kullanırken **Sil** kilitlidir. Önce atamayı kaldır.

## Çalışma zamanı

**Ollama temel URL’si** (genelde Ollama’nın yerel adresi). **Bağlantıyı denetle** ve **model listesi** uygulamadan gider. Liste **Normal modeller** ve **Gömme modelleri** diye ayrılır. Adında `embed` geçen model gömme sayılır. Boş grup **Yok** gösterir.

Adres yerel ise ve Ollama kurulu ama kapalıysa uygulama pencere açılınca hizmeti başlatır ve durdurmaz. Ollama’ya erişilemezse yerel LLM düğümleri ve varsayılan yardım durur. Modelleri Ollama ile veya kurulumda yüklersin; uygulama çalışma anında sessizce **çekmez**. OpenAI uyumlu bir temel URL burada artık sunulmaz.

## Yardım sohbeti

Yardım widget’ının tek yeri. Sohbet sağlayıcısı ve modeli olmadan eksiktir.

- Sohbet sağlayıcısı ve modeli (varsayılan Ollama / `llama3.2:1b`)
- isteğe bağlı bulut kimlik bilgisi
- **Gömme sağlayıcısı ve modeli** (varsayılan Ollama / `nomic-embed-text`) — bu sohbet modeli **değildir**
- isteğe bağlı tasarruf modeli (yedek, varsayılan aynı küçük sohbet modeli)
- web araması aç/kapa artı arama kimlik bilgisi; kimlik bilgisi olmadan sohbet yapılandırılmış kalır, arama kapalıdır
- bağlantıyı denetle, geçmişi sil, **dizini yeniden oluştur**, karşılama ekranını yeniden göster

Gömme modelini değiştirdikten veya yardım derlemine yeni dosya ekledikten sonra: **dizini yeniden oluştur**. Ayarlardan çıksan da iş sürer. İkinci tıklama ikinci bir dizin başlatmaz. Derlem, veri klasöründeki yardım belgeleri klasörüdür, ağ bilgisi değildir. Uygulamayla gelen yeni kılavuzlar orada duran dosyaların üzerine yazmaz.

Yardım arayüz dilinde yanıtlar. Model o dili kullanamazsa İngilizce yanıtlar. Kılavuzların belge başlıklarını söylemez. Yalnız web araması kaynak gösterir: başlık ve adres. Modelin iç düşünme blokları görünmez. Yardım **hiçbir** MCP sunucusu ve grafiklerin knowledge’ını kullanmaz.

## MCP sunucuları

Dış araçlar için şablonlar (**tarifler**): GitHub, dosya sistemi, Git, Playwright, Postgres, Slack, Notion, Office biçimleri ve diğerleri. Tarifler birlikte gelen programlar değildir. Birçoğu PC’de Node/`npx`, Docker veya `uvx` artı bir kimlik bilgisi ister.

Varsayılan: sunucu **etkin değil**. Uygulama açılışta MCP süreçlerini başlatmaz; bir çalıştırma bağlı bir MCP araç düğümüne ihtiyaç duyunca başlatır.

Bir tariften (kimlik bilgisi, isteğe bağlı kök yolu) veya **özel sunucu** olarak (komut, argümanlar veya URL) oluştur. Bilinmeyen komutları yalnızca güveniyorsan kullan. Sonda erişilebilirliği denetler; Node/Docker/`uvx` yoksa «Çalışma zamanı yok».

Office PDF ve Office biçimlerini birleştirir; tekil hazır ayarları gerçekten gerekirse aç.

Silme sunucu yapılandırmasını kaldırır, Ollama’yı ve kimlik bilgilerini değil.

## Veri

**Veri klasörünü** ve depoların durumunu gösterir: Ayarlar, Yardım, Çalışma alanı, Geçmiş — SQL görünümü ve sır yok.

Klasör **değiştirmek** yalnızca hiçbir ağ başlamıyor, çalışmıyor veya durmuyorken. Sürücü veya sistem kökleri geçersizdir. İsteğe bağlı içeriği yeni klasöre kopyala; eski klasör kalır.

**Taşınabilir** veya dışarıdan dayatılan klasör: yol **salt okunur**.

**Geçmiş saklama:** 30 / 90 / 365 gün veya sınırsız (varsayılan 90). Geçmiş sayfası eski kayıtları buna göre temizleyebilir.

## Hakkında

UI ve API sürümü, kabaca Ollama durumu, depoların erişilebilir olup olmadığı. Sır yok, paylaşacağın bir yüzeyde kullanıcı adı içeren iç yollar yok.
