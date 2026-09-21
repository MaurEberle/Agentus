# Düzenleyici ve kitaplık

**Ağ** altındaki düzenleyici **bir** grafik belgesini düzenler. **Kitaplık** katalogdur: liste, içe aktarma, silme, etkin yapma. Tuval yalnızca düzenleyicidedir; kitaplık, izleme veya geçmişte yoktur.

## İki yer

| Yer | URL anlamı | Tipik eylemler |
|-----|----------|-------------------|
| Düzenleyici | Yeni veya yüklenmiş bir ağ | Çizim, denetçi, kaydet, Aç iletişim kutusu, çoğalt, açık grafiği dışa aktar |
| Kitaplık | tüm ağlar | Arama, etiketler, etkin yap, birden fazla dosyayı içe/dışa aktar, sil |

**Etkin yap** ve **Sil** kitaplığa aittir (etkin için hızlı seçim). Düzenleyicideki Aç kutusu yalnızca **bir** ağ açar, hiçbir şey silmez.

## Düzenleyici yüzeyi

Üstte **şerit**: Yeni, Kaydet, Farklı kaydet, Aç, Çoğalt, Dışa aktar, Doğrula, Geri al/Yinele, Görünüm (sığdır, ızgara, hizala, minikart), Kitaplığa.

Orta: **Palet** (sol), **tuval**, **Denetçi** (sağ). Masaüstünde katlanabilirler. Dar ekranlarda çekmecedir. Boş bir ağ yalnızca ilk düğümü paletten tuvale sürükleme ipucunu gösterir. Kenarlar, izleme ve geçmişteki gibi eğridir.

Düğümler paletten sürüklenir. Kartlar kompakt kalır; formlar denetçidedir. Çoklu seçim Shift veya lastikle. Delete seçimi siler. Geri al: Ctrl+Z.

**Tam bu** ağ çalışırken: **Salt okunur** şeridi — önce başlıktan durdur.

## Düğüm türleri

| Ad | Tür | Görev |
|-------------|-----|---------|
| Sohbet | `chat_input` | Çalışma sohbeti. **En fazla bir.** Çıkış **İleti**. Orkestratör varken sohbet sorular için açık kalır. |
| Orkestratör | `orchestrator` | Çalıştırma sohbetinin sesi. Girişler **İleti** ve **LLM**. Ajan başına bir **Kanal** çıkışı. **İleti** yalnız **Son** veya yönlendiriciye. **En fazla bir.** |
| LLM | `llm` | Sağlayıcı (Ollama, xAI, OpenAI, Claude, Gemini), model, bulut kimlik bilgisi, sıcaklık, belirteç sınırı. Çıkış **LLM**. |
| Ajan | `agent` | Sistem istemi. Girişler İleti, LLM, Araç, Bilgi ve isteğe bağlı **Kanal**. Çıkışlar İleti ve Devretme. Kanal yalnız orkestratörden gelir. Kanalsız ajan ileti üzerinden bir kez çalışır. |
| Araç | `tool` | First-party: HTTP, web araması, tarih/saat, hesap makinesi, dosya erişimi — veya **MCP**. Çıkış **Araç**. |
| Bilgi | `knowledge` | Ağ için dosya klasörü. Çıkış **Bilgi**, yalnızca ajanın Bilgi bağlantı noktasına. |
| Yönlendirici | `router` | İletiyi koşullara göre ayırır (ilk satır / adlı dallar) artı varsayılan çıkış. |
| Son | `end` | Bitiş. **En az bir.** |

## Bağlantılar

Yalnızca uyumlu bağlantı noktaları:

- İleti’den İleti’ye (Sohbet → Ajan veya Sohbet → Orkestratör, Ajan → Son, Ajan → Yönlendirici, yönlendirici dalları → …). Orkestratör İleti’yi yalnız Son’a veya bir yönlendiriciye gönderir.
- Kanaldan kanala (Orkestratör → Ajan). Ajan başına bir bağlantı noktası. Yanıt çalıştırma içinde döner, ikinci kenar gerekmez.
- LLM çıkışı ajanın veya orkestratörün **LLM**’sine — her ajan ve orkestratör **tam olarak bir** böyle kenar ister
- Araç çıkışı ajan **Araç**’ına (birden fazla izinli)
- Bilgi çıkışı yalnızca ajan **Bilgi**’sine
- Döngüler yasaktır (döngüsüz yönlü grafik)

Geçersiz sürükleme reddedilir.

## Denetçi

Düğüm seçili değil: **açık** ağın adı, açıklaması, etiketleri, istatistiği, doğrulama listesi.

Düğüm seçili:

- **LLM:** sağlayıcı, model (çalışma zamanı listesi), bulut kimlik bilgisi, ping, gelişmiş sıcaklık / en fazla belirteç. Kimlik bilgisi olmadan bulut geçersizdir.
- **Ajan:** sistem istemi ve görünen ad. Ajan bir kanaldaysa denetçi görevlerin orkestratörden geldiğini açıklar.
- **Araç:** tür. HTTP: yöntem ve URL, isteğe bağlı kimlik bilgisi. Web araması: web araması türünde kimlik bilgisi. Dosya erişimi: kök klasör, sürücü kökü değil; ajan yalnız onun altında çalışır, yazma ve silme anahtardır. MCP: Ayarlar’dan etkin sunucu; varsayılan o sunucunun tüm araçları.
- **Bilgi:** kaynak klasör (klasör seçimi), gömme sağlayıcısı (Ollama, OpenAI veya Gemini) ve gömme modeli, topK, puan eşiği, **Dizini yenile**. Klasör sürücü veya sistem kökü ve yardım derlemi dışında herhangi bir yerde olabilir. Bulut gömmeleri kimlik bilgisi ister. Dizin bu ağa aittir, yardıma değil.
- **Sohbet:** yer tutucu, başlangıç metni, «Giriş gerekli» anahtarı.
- **Orkestratör:** sistem istemi. Model bir soru, bir ajanın kanalından tek görev, bir yanıt veya bitiş seçer. Ajanlar kanallardır, ikinci bir liste değil.
- **Yönlendirici:** adlı dallar (ad + koşul) ve varsayılan.

Sırlar denetçi metnine ve grafik dışa aktarımına **ait değildir** — yalnızca bir kimlik bilgisi seçimi.

## Doğrulama

Şeritteki **Doğrula** şunları da denetler:

- Ad boş değil
- en fazla bir sohbet, en fazla bir orkestratör, en az bir son
- her ajan: tam olarak bir LLM kenarı. Orkestratör yoksa gelen bir ileti. Orkestratör varken tam olarak bir kanal ve aynı ajanda ileti zinciri yok
- LLM: model set; bulut: kimlik bilgisi
- Araç: tür; MCP: etkin sunucu, tarif kök yolu istiyorsa kök yolu; dosya erişimi: sürücü kökü olmayan bir klasör
- Bilgi: yol dolu, kök değil, yardım derlemi değil, sağlayıcı istiyorsa gömme kimlik bilgisi
- sarkan kenar yok, döngü yok, uyumlu bağlantı türleri

Geçerli/Geçersiz rozet olarak görünür. Geçersiz ağlar kaydedilebilir ama kötü başlar.

## Kaydet, aç, dışa aktar

- **Kaydet** (Ctrl+S): ilk sefer ad iletişim kutusu, sonra güncelleme. URL `/network/…` olur.
- **Farklı kaydet:** yeni belge, açık olan olur.
- **Aç:** kayıtlı bir ağ; arama ve sıralama. Toplu işlem ve silme yalnızca kitaplıkta.
- **Çoğalt:** yalnızca zaten kayıtlı belgede; kopyayı açar.
- **Dışa aktar:** açık grafiğin indirilmesi. `credentialId` içerir, anahtar içermez. Kitaplıkta içe aktarma ekli sırları atar.

Kaydetmeden çıkış: Kaydet / At / İptal iletişim kutusu.

## Kitaplık

Arama (ad, açıklama, etiketler), sıralama, «yalnızca geçerli» / «yalnızca etkin» süzgeçleri. Çoklu seçim.

Eylemler: Yeni (düzenleyici), Aç, Çoğalt, Yeniden adlandır, Etiket koy, **Etkin yap** (yalnızca geçerli bir ağ), Sil, İçe aktar, Dışa aktar.

Silme çalışma alanı kaydını kaldırır; diskteki bilgi kaynak dosyalarını, yardım derlemini ve geçmiş çalıştırmalarını kaldırmaz. **Çalışan** bir ağ atlanır. Etkin ağı silmek hızlı seçimi boşaltır.

İçe aktarma: ad çakışan dosyalar yeniden adlandırılır veya atlanır. Desteklenmeyen şema sürümleri reddedilir.
