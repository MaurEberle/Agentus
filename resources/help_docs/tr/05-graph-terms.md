# Terimler

Yardım sohbeti ve düzenleyici için kısa sözlük.

## Grafik / ağ

Düğüm ve kenarlardan oluşan kayıtlı belge. Düzenleyicide düzenler, kopyaları kitaplıkta yönetirsin. **Etkin** ağ hızlı seçimdeki ağıdır — **Başlat** yalnızca onu başlatır.

## Çalıştırma (run)

Etkin grafiğin bir yürütmesi. En fazla **biri** çalışır. Başlat ve durdur başlıkta. Sonuçlar: çalışıyor, başarı, hata, iptal, zaman aşımı.

## Düğümler ve kenarlar

Parçalar (sohbet, orkestratör, ajan, LLM, araç, bilgi, yönlendirici, son) ve tipli bağlantılar. Kutular arasında rastgele oklar geçersizdir.

## Ajan

Sistem istemi olan düğüm. Model, ileti, araçlar ve bilgi bağlantı noktalarından gelir. Orkestratör yoksa ileti onu başlatır, ileti veya devretme yanıtı iletir. Orkestratör varken kendi kanalına bağlıdır: bir görev girer, bir sonuç döner.

## LLM düğümü

Sağlayıcı ve modeli seçer. Yerel Ollama; değilse bulut artı kimlik bilgisi.

## Sohbet

Çalıştırmada kullanıcı metninin tek girişi. Ağ başına en fazla bir. İzleme sohbeti buraya yazar. Orkestratör varken konuşma birkaç ileti boyunca açık kalır.

## Orkestratör

Kendi LLM’i olan düğüm. Çalıştırma sohbetinin tek sesidir, soru sorar ve bağlı ajanları teker teker, her birini bir kanaldan çağırır. En fazla bir. Sohbet yalnız ona bağlanır. İleti çıkışı Son’a veya bir yönlendiriciye gider. Ajan metinlerini ve iç komutları baloncuk olarak görmezsin. Uygulama son sonucu sonraki göreve ekler. Bir ajan ya kanaldadır ya ileti zincirindedir.

## Araç

First-party (HTTP, web araması, tarih/saat, hesap makinesi, dosya erişimi) veya MCP. Dosya erişimi bir kök klasörde kalır, sürücü kökünde değil. Yapılandırma denetçide, yürütme yalnızca çalıştırmada.

## Bilgi (ağ)

Bilgi düğümü: ağ için metin klasörü. Sürücü veya sistem kökü ve yardım derlemi dışında herhangi bir yerde olabilir. Kendi gömme modeli, dizini, topK ve puanı. **Yardım derlemi değil.** Başlangıçta dizin oluşumunu görürsün; güncel bir dizin atlanır.

## Yardım-RAG

Veri klasöründeki yardım klasöründeki belgeler (varsayılan kılavuzlar artı Markdown’ların). Yalnızca yardım sohbet botu. Değişiklikten sonra Ayarlar → Yardım sohbeti altında dizini yeniden oluştur.

## Kimlik bilgisi / credential

Windows kasasında saklanan anahtar. Listelerde yalnızca maske. Grafikte yalnızca kimlik/seçim, asla sır. Dışa aktarım parola içermez.

## MCP

Model Context Protocol: dış araç sunucuları. Ayarlar’da oluşturup etkinleştir, grafikte MCP türünde araç düğümü olarak bağla. Yardım MCP kullanmaz.

## Sağlayıcı

Listede: `ollama` (yerel), `xai`, `openai`, `anthropic` (Claude), `gemini` (bulut: önce kimlik bilgisi, sonra model listesi). Gömmeler: Ollama, OpenAI, Gemini. `openai_compat` eski grafikler ve kimlik bilgileri için geçerli kalır, model listesinde artık yoktur.

## Ollama

Yerel modeller için ayrı hizmet. Uygulama istemcidir. Kuruluysa, adres yerel ise ve kapı yanıt vermiyorsa uygulama onu başlatır ve durdurmaz. Kurulum Ollama’yı oluşturabilir, kısa bekleyebilir ve yanıt verirse iki küçük varsayılan modeli yükleyebilir.

## Kontrol paneli, izleme, geçmiş

Kontrol paneli = özet ve kurulum. İzleme = canlı. Geçmiş = arşiv. Aynı sayfa üç kez değildir.

## Geçerli / geçersiz

Grafiğin doğrulanması. Geçersiz kaydedilebilir ama başlatmaya uygun değildir. Yalnızca geçerli bir ağ etkin yapılabilir.

## Hızlı seçim

Başlıkta etkin ağ seçimi. Kitaplıktaki «Etkin yap» ile aynıdır.

## Tasarruf kipi

Ana model taşımazsa yardım yedek modele geçer. Kontrol paneli bunu Ortam altında gösterebilir.

## Taşınabilir

EXE’nin yanında `portable.txt`: veriler uygulamanın yanında. Kurulu kopya: veriler uygulama veri klasöründe, programlar ayrı.
