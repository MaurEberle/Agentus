# Agentus Network — kısa kılavuz

Agentus Network **yerel bir masaüstü uygulamasıdır**. Bu PC’de ajan, dil modeli ve araçlardan ağlar kurar, **bir** çalıştırma başlatır ve canlı izlersin. Arayüz uygulamanın kendisine aittir (kendi penceresi); Chrome veya bir `file://` sayfası değildir.

Ollama **ayrı bir hizmettir**. Agentus Network’ü kapatmak veya kaldırmak Ollama’yı durdurmaz ve modelleri silmez. Ollama bu PC’de kuruluysa, Ayarlar’daki adres yerel ise ve hizmet kapalıysa uygulama pencere açılınca onu başlatır.

## Pencere ve gezinme

Solda (telefonda: hamburger menü):

- **Kontrol paneli** — ana sayfa, kurulum, etkin ağ, son çalıştırmalar
- **Ağ** — düzenleyici (bir grafik)
- **Kitaplık** — kayıtlı tüm ağlar
- **İzleme** — canlı çalıştırma
- **Geçmiş** — biten çalıştırmalar ve istatistik

**Ayarlar** başlık çubuğundadır (dişli), sol gezinmede değil.

Başlıkta ayrıca: **Başlat** / **Durdur**, etkin ağın **hızlı seçimi**, zil (bildirimler), açık/koyu/sistem, dil (Deutsch, English, Español, Français, Türkçe, Português, 中文, 日本語, العربية) ve pencere düğmeleri (küçült, kapla, kapat).

Logoyu veya boş başlığı sürükleyerek pencereyi taşırsın. Başlat, Durdur, hızlı seçim ve sağdaki düğmeler sürükleme alanı değildir.

## İlk tur

1. Ollama’ya erişilebilmeli. Kurulu ama kapalıysa uygulama yerel hizmeti kendisi başlatır. Kurulum Ollama’yı oluşturabilir, kısa süre arka planda başlatabilir ve küçük modeller `nomic-embed-text` ile `llama3.2:1b`’yi yalnız Ollama yanıt verirse çeker. Model anahtarı olmayan sessiz kurulum hiçbir şey indirmez. Başarısız bir indirme kurulumu yine de başarıyla bitirir.
2. **Ayarlar → Çalışma zamanı** altında bağlantıyı denetle; model listesi boş olmamalı.
3. **Ayarlar → Yardım sohbeti** altında sağlayıcı ve sohbet modelini ayarla (varsayılan: Ollama + `llama3.2:1b`). Gömme **başka** bir modeldir (`nomic-embed-text`).
4. **Kitaplıkta** veya düzenleyicide bir ağ oluştur, kaydet, hızlı seçimde **etkin yap**.
5. Başlıktan **Başlat**. Çalıştırmayı **İzleme** altında görürsün.

Kontrol paneli eksik adımları kurulum kartları olarak gösterir.

## En küçük ağ

Düzenleyicide (**Ağ**) en az:

1. **Sohbet** (`chat_input`) — en fazla bir
2. **Ajan** — sistem istemi
3. **LLM** — sağlayıcı ve model
4. **Son** (`end`) — en az bir

Bağlantılar (tipli bağlantı noktaları, rastgele oklar değil):

- Sohbet **İleti** → Ajan **İleti**
- LLM **LLM** → Ajan **LLM**
- Ajan **İleti** → Son

İsteğe bağlı **Orkestratör**: sohbet yalnız orkestratöre, bir LLM orkestratöre, orkestratörden her ajanın kanalına bir **Kanal** ve orkestratörden **Son**’a **İleti**. Çalıştırma sohbetinin tek sesidir, soru sorar ve ajanları teker teker çağırır. Ajan metinleri ve iç komutlar baloncuk olarak görünmez. Her ajan kendi metnini tutar. Araçlı bir ajan, yazarın metnini ve yazdığı dosyaların listesini alır. Orkestratör yalnızca kısa bir özet görür. Bir ajanın aracı varsa ve onu çağırmazsa ya da çağrı başarısız olursa görev açık kalır. Bu iş sohbette tamamlanmış diye bildirilmez. Sohbet, çalıştırmayı bitirene kadar açık kalır. Orkestratör yoksa her ajan ileti ve devretme üzerinden kendi zinciridir. Bir ajan ya kanaldadır ya zincirdedir, ikisinde birden değil.

İsteğe bağlı: **Araç** ajanın **Araç** bağlantı noktasına, **Bilgi** **Bilgi**’ye. Kaydet. **Kitaplıkta** hızlı seçim henüz değilse «Etkin yap».

## Başlat ve durdur

**Başlat**, **etkin** ağın (hızlı seçim) **bir** çalıştırmasını başlatır. İkinci bir ağ asla paralel çalışmaz. **Durdur**’a kadar ikinci başlatma reddedilir.

**Durdur** çalıştırmayı iptal eder (sonuç **İptal**, **Hata** değil). Ollama açık kalır.

Etkin ağ yoksa hiçbir şey başlamaz. Geçersiz bir ağı (doğrulama hatası, eksik model) başlamadan düzenleyicide denetlemelisin.

Etkin ağ çalışırken düzenleyicideki **bu** belge salt okunur. Diğer ağlara bakmaya devam edebilirsin; kitaplıkta çalışan ağı silmek kilitlidir.

Pencereyi kapatmak çalıştırmayı ve uygulamayı bitirir. Ollama yaşamaya devam eder.

## Yardım sohbeti ağ sohbeti değildir

Sağ alt: baloncuk = **uygulama yardımı** (bu kılavuz, grafik terimleri, isteğe bağlı web araması). Karşılama ilk açılışta açıklar.

**İzleme**’de **Sohbet** sekmesi = grafiğin **çalıştırma sohbeti** (Sohbet düğümü). Orkestratör yoksa ajanlara giriştir. Orkestratör varken konuşmadır: ajan çağırmadan önce sana sorabilir.

İkisi **geçmiş**, araç veya kimlik bilgisi paylaşmaz. Yardım **hiçbir** MCP sunucusu kullanmaz.

## Ollama ve bulut

- **Yerel:** Ollama, Ayarlar’da çalışma zamanı. Modelleri orada listeler ve dener. Uygulama çalışma anında sessizce model **indirmez**.
- **Bulut:** kimlik bilgileri **Ayarlar → Kimlik bilgileri** (xAI, OpenAI, Claude, Gemini, web araması, …). LLM düğümünde Ollama, xAI, OpenAI, Claude veya Gemini seçersin. Uygun kimlik bilgisi olmayan bulut geçersizdir. Listeler yalnızca bir **maske** gösterir, sırrı asla. LLM düğümleri ve yardım grafikte anahtarla değil, adla kimlik bilgisine işaret eder.

OpenAI uyumlu bir temel URL artık Çalışma zamanında sunulmaz. Bu türdeki mevcut kimlik bilgileri Kimlik bilgilerinde durur.

## Tek örnek

İkinci bir başlatma mevcut pencereyi öne getirir. İkinci bir arka uç veya çalıştırma olmaz.

## Taşınabilir ve kurulu

Kurulu uygulama verileri yerel **Agentus-Network** klasörüne koyar, programın yanına değil. Taşınabilir çeşitte (`portable.txt` EXE’nin yanında) veriler **EXE’nin yanında** durur. Portable’da WebView2 ve Ollama’yı sen getirirsin.
