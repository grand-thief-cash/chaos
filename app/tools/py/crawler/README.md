
# For crawling financial factors from factors.directory

# CURL Example

## Example1

CURL
```shell
curl 'https://factors.directory/en/factors/value/value-retained-earnings-per-share?_rsc=j9izt' \
  -H 'accept: */*' \
  -H 'accept-language: en-US,en;q=0.9' \
  -b '_ga=GA1.1.2012860115.1777104652; _ga_SR89ML6JC8=GS2.1.s1777279727$o3$g1$t1777284853$j36$l0$h0' \
  -H 'next-router-state-tree: %5B%22%22%2C%7B%22children%22%3A%5B%5B%22lang%22%2C%22en%22%2C%22d%22%5D%2C%7B%22children%22%3A%5B%22factors%22%2C%7B%22children%22%3A%5B%5B%22categoryId%22%2C%22value%22%2C%22d%22%5D%2C%7B%22children%22%3A%5B%5B%22factorId%22%2C%22value-retained-earnings-per-share%22%2C%22d%22%5D%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%2Cnull%2Cnull%2Cfalse%5D%7D%2Cnull%2Cnull%2Cfalse%5D%7D%2Cnull%2Cnull%2Cfalse%5D%7D%2Cnull%2C%22refetch%22%2Cfalse%5D%7D%2Cnull%2Cnull%2Cfalse%5D%7D%2Cnull%2Cnull%2Ctrue%5D' \
  -H 'next-url: /en' \
  -H 'priority: u=1, i' \
  -H 'referer: https://factors.directory/en' \
  -H 'rsc: 1' \
  -H 'sec-ch-ua: "Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "Windows"' \
  -H 'sec-fetch-dest: empty' \
  -H 'sec-fetch-mode: cors' \
  -H 'sec-fetch-site: same-origin' \
  -H 'user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36' ;
curl 'https://factors.directory/_next/static/chunks/52b6e59d7fc8ae26.js' \
  -H 'sec-ch-ua-platform: "Windows"' \
  -H 'Referer: https://factors.directory/en' \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36' \
  -H 'sec-ch-ua: "Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"' \
  -H 'sec-ch-ua-mobile: ?0' ;
curl 'https://factors.directory/_next/static/chunks/8ffca437f8e25de9.js' \
  -H 'sec-ch-ua-platform: "Windows"' \
  -H 'Referer: https://factors.directory/en' \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36' \
  -H 'sec-ch-ua: "Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"' \
  -H 'sec-ch-ua-mobile: ?0' ;
curl 'https://factors.directory/_next/static/chunks/4057cc9dbcc744c0.css' \
  -H 'sec-ch-ua-platform: "Windows"' \
  -H 'Referer: https://factors.directory/en' \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36' \
  -H 'sec-ch-ua: "Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"' \
  -H 'sec-ch-ua-mobile: ?0' ;
curl 'https://factors.directory/_next/static/chunks/1aa21a85844b2738.js' \
  -H 'sec-ch-ua-platform: "Windows"' \
  -H 'Referer: https://factors.directory/en' \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36' \
  -H 'sec-ch-ua: "Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"' \
  -H 'sec-ch-ua-mobile: ?0' ;
curl 'https://www.google-analytics.com/g/collect?v=2&tid=G-SR89ML6JC8&gtm=45je64n0h2v9203325024za200zd9203325024&_p=1777284853404&gcd=13l3l3l3l1l1&npa=0&dma=0&_eu=AAAAAAQ&_prs=gs&are=1&cid=2012860115.1777104652&frm=0&pscdl=noapi&rcb=10&sr=1280x720&uaa=x86&uab=64&uafvl=Google%2520Chrome%3B147.0.7727.102%7CNot.A%252FBrand%3B8.0.0.0%7CChromium%3B147.0.7727.102&uam=&uamb=0&uap=Windows&uapv=19.0.0&uaw=0&ul=en-us&_s=2&tag_exp=0~115616986~115938466~115938468~116363097~117266401~117512542~118167059&sid=1777279727&sct=3&seg=1&dl=https%3A%2F%2Ffactors.directory%2Fen%2Ffactors%2Fvalue%2Fvalue-retained-earnings-per-share&dt=Retained%20earnings%20per%20share%20-%20seo.factor_title_suffix%20%7C%20Factors%20Directory%20-%20Quantitative%20Trading%20Factor%20Library&en=view&_c=1&_ee=1&ep.event_category=factor&ep.event_label=value-retained-earnings-per-share&ep.dimension1=en&ep.dimension2=Retained%20earnings%20per%20share&_et=20350&tfd=140472' \
  -X 'POST' \
  -H 'accept: */*' \
  -H 'accept-language: en-US,en;q=0.9' \
  -H 'content-length: 0' \
  -H 'origin: https://factors.directory' \
  -H 'priority: u=1, i' \
  -H 'referer: https://factors.directory/' \
  -H 'sec-ch-ua: "Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "Windows"' \
  -H 'sec-fetch-dest: empty' \
  -H 'sec-fetch-mode: no-cors' \
  -H 'sec-fetch-site: cross-site' \
  -H 'sec-fetch-storage-access: active' \
  -H 'user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36' ;
curl 'https://factors.directory/_next/static/chunks/080cf51fd6b95f88.js' \
  -H 'sec-ch-ua-platform: "Windows"' \
  -H 'Referer: https://factors.directory/en/factors/value/value-retained-earnings-per-share' \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36' \
  -H 'sec-ch-ua: "Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"' \
  -H 'sec-ch-ua-mobile: ?0' ;
curl 'chrome-extension://pkgccpejnmalmdinmhkkfafefagiiiad/background/awesome.js' \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36' \
  -H 'Origin: https://factors.directory' \
  -H 'Referer;' ;
curl 'chrome-extension://pkgccpejnmalmdinmhkkfafefagiiiad/background/tools.js' \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36' \
  -H 'Origin: https://factors.directory' \
  -H 'Referer;' ;
curl 'https://factors.directory/_next/static/media/KaTeX_Math-Italic.d8564edb.woff2' \
  -H 'Origin: https://factors.directory' \
  -H 'sec-ch-ua-platform: "Windows"' \
  -H 'Referer: https://factors.directory/_next/static/chunks/4057cc9dbcc744c0.css' \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36' \
  -H 'sec-ch-ua: "Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"' \
  -H 'sec-ch-ua-mobile: ?0' ;
curl 'https://factors.directory/_next/static/media/KaTeX_Main-Regular.12644167.woff2' \
  -H 'Origin: https://factors.directory' \
  -H 'sec-ch-ua-platform: "Windows"' \
  -H 'Referer: https://factors.directory/_next/static/chunks/4057cc9dbcc744c0.css' \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36' \
  -H 'sec-ch-ua: "Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"' \
  -H 'sec-ch-ua-mobile: ?0' ;
curl 'https://www.google-analytics.com/g/collect?v=2&tid=G-SR89ML6JC8&gtm=45je64n0h2v9203325024za200zd9203325024&_p=1777284853404&gcd=13l3l3l3l1l1&npa=0&dma=0&_eu=AEAAAAQ&ae=a&are=1&cid=2012860115.1777104652&frm=0&pscdl=noapi&rcb=10&sr=1280x720&uaa=x86&uab=64&uafvl=Google%2520Chrome%3B147.0.7727.102%7CNot.A%252FBrand%3B8.0.0.0%7CChromium%3B147.0.7727.102&uam=&uamb=0&uap=Windows&uapv=19.0.0&uaw=0&ul=en-us&tag_exp=0~115616986~115938466~115938468~116363097~117266401~117512542~118167059&sid=1777279727&sct=3&seg=1&dl=https%3A%2F%2Ffactors.directory%2Fen%2Ffactors%2Fvalue%2Fvalue-retained-earnings-per-share&dt=Retained%20earnings%20per%20share%20-%20seo.factor_title_suffix%20%7C%20Factors%20Directory%20-%20Quantitative%20Trading%20Factor%20Library&_s=3&tfd=146461' \
  -H 'accept: */*' \
  -H 'accept-language: en-US,en;q=0.9' \
  -H 'content-type: text/plain;charset=UTF-8' \
  -H 'origin: https://factors.directory' \
  -H 'priority: u=1, i' \
  -H 'referer: https://factors.directory/' \
  -H 'sec-ch-ua: "Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "Windows"' \
  -H 'sec-fetch-dest: empty' \
  -H 'sec-fetch-mode: no-cors' \
  -H 'sec-fetch-site: cross-site' \
  -H 'sec-fetch-storage-access: active' \
  -H 'user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36' \
  --data-raw $'en=scroll&epn.percent_scrolled=90&_et=30\r\nen=page_view&_et=944&dr=https%3A%2F%2Ffactors.directory%2Fen'
```

RESPONSE
```RSC
1:"$Sreact.fragment"
2:I[39756,["/_next/static/chunks/ff1a16fafef87110.js","/_next/static/chunks/d6145d29b805a899.js"],"default"]
3:I[37457,["/_next/static/chunks/ff1a16fafef87110.js","/_next/static/chunks/d6145d29b805a899.js"],"default"]
5:I[97367,["/_next/static/chunks/ff1a16fafef87110.js","/_next/static/chunks/d6145d29b805a899.js"],"OutletBoundary"]
6:"$Sreact.suspense"
8:I[97367,["/_next/static/chunks/ff1a16fafef87110.js","/_next/static/chunks/d6145d29b805a899.js"],"ViewportBoundary"]
a:I[97367,["/_next/static/chunks/ff1a16fafef87110.js","/_next/static/chunks/d6145d29b805a899.js"],"MetadataBoundary"]
d:I[68748,["/_next/static/chunks/b066884540f68241.js","/_next/static/chunks/520100b3da6fc730.js","/_next/static/chunks/e7cf22f2504f6e6f.js","/_next/static/chunks/09601403e5a52e02.js","/_next/static/chunks/52b6e59d7fc8ae26.js","/_next/static/chunks/8ffca437f8e25de9.js"],"FactorContent"]
:HL["/_next/static/chunks/4057cc9dbcc744c0.css","style"]
0:{"b":"z36Zfem2wLSDU_t_7pDab","f":[["children",["lang","en","d"],"children","factors",["factors",{"children":[["categoryId","value","d"],{"children":[["factorId","value-retained-earnings-per-share","d"],{"children":["__PAGE__",{}]}]}]}],[["$","$1","c",{"children":[null,["$","$L2",null,{"parallelRouterKey":"children","error":"$undefined","errorStyles":"$undefined","errorScripts":"$undefined","template":["$","$L3",null,{}],"templateStyles":"$undefined","templateScripts":"$undefined","notFound":"$undefined","forbidden":"$undefined","unauthorized":"$undefined"}]]}],{"children":[["$","$1","c",{"children":[null,["$","$L2",null,{"parallelRouterKey":"children","error":"$undefined","errorStyles":"$undefined","errorScripts":"$undefined","template":["$","$L3",null,{}],"templateStyles":"$undefined","templateScripts":"$undefined","notFound":"$undefined","forbidden":"$undefined","unauthorized":"$undefined"}]]}],{"children":[["$","$1","c",{"children":[null,["$","$L2",null,{"parallelRouterKey":"children","error":"$undefined","errorStyles":"$undefined","errorScripts":"$undefined","template":["$","$L3",null,{}],"templateStyles":"$undefined","templateScripts":"$undefined","notFound":"$undefined","forbidden":"$undefined","unauthorized":"$undefined"}]]}],{"children":[["$","$1","c",{"children":["$L4",[["$","link","0",{"rel":"stylesheet","href":"/_next/static/chunks/4057cc9dbcc744c0.css","precedence":"next","crossOrigin":"$undefined","nonce":"$undefined"}],["$","script","script-0",{"src":"/_next/static/chunks/52b6e59d7fc8ae26.js","async":true,"nonce":"$undefined"}],["$","script","script-1",{"src":"/_next/static/chunks/8ffca437f8e25de9.js","async":true,"nonce":"$undefined"}]],["$","$L5",null,{"children":["$","$6",null,{"name":"Next.MetadataOutlet","children":"$@7"}]}]]}],{},null,false,false]},null,false,false]},null,false,false]},null,false,false],["$","$1","h",{"children":[null,["$","$L8","mkiF9uSBO3Bb4RbHC0ZfHv",{"children":"$@9"}],["$","div","mkiF9uSBO3Bb4RbHC0ZfHm",{"hidden":true,"children":["$","$La",null,{"children":["$","$6",null,{"name":"Next.Metadata","children":"$@b"}]}]}]]}],false]],"S":false}
c:T68c,{"@context":"https://schema.org","@type":"Article","headline":"Retained earnings per share","description":"Retained Earnings Per Share (REPS) is an indicator that measures the amount of retained earnings per common share of a company, reflecting the profits accumulated from past operations that have not yet been distributed to shareholders. This indicator can reflect the profitability accumulated within a company and can serve as an important reference for assessing the company's value and future growth potential. Compared with directly using total retained earnings, the per-share indicator is more convenient for cross-company comparisons because it eliminates the impact of differences in equity size, thereby providing a more standardized evaluation basis.","url":"https://factors.directory/en/factors/value/value-retained-earnings-per-share","datePublished":"2026-04-27T10:16:32.546Z","dateModified":"2026-04-27T10:16:32.546Z","author":{"@type":"Organization","name":"Factors Directory","url":"https://factors.directory"},"publisher":{"@type":"Organization","name":"Factors Directory","url":"https://factors.directory","logo":{"@type":"ImageObject","url":"https://factors.directory/factor_logo400.png","width":400,"height":400}},"mainEntityOfPage":{"@type":"WebPage","@id":"https://factors.directory/en/factors/value/value-retained-earnings-per-share"},"articleSection":"value","keywords":"Value Factor","inLanguage":"en","citation":[{"@type":"ScholarlyArticle","headline":"Financial Statement Analysis","datePublished":"","publisher":"","url":""},{"@type":"ScholarlyArticle","headline":"Corporate Financial Management","datePublished":"","publisher":"","url":""}]}4:[["$","script",null,{"type":"application/ld+json","dangerouslySetInnerHTML":{"__html":"$c"}}],["$","script",null,{"type":"application/ld+json","dangerouslySetInnerHTML":{"__html":"{\"@context\":\"https://schema.org\",\"@type\":\"BreadcrumbList\",\"itemListElement\":[{\"@type\":\"ListItem\",\"position\":1,\"name\":\"Home\",\"item\":\"https://factors.directory/en\"},{\"@type\":\"ListItem\",\"position\":2,\"name\":\"Value\",\"item\":\"https://factors.directory/en/factors/value\"},{\"@type\":\"ListItem\",\"position\":3,\"name\":\"Retained earnings per share\",\"item\":\"https://factors.directory/en/factors/value/value-retained-earnings-per-share\"}]}"}}],["$","$Ld",null,{"factor":{"id":"value-retained-earnings-per-share","title":"Retained earnings per share","explanation":"The higher the retained earnings per share, the higher the accumulated undistributed profit corresponding to each share of the company, which may indicate that the company has stronger internal financing capabilities and future development potential. From the perspective of value investment, high retained earnings per share may indicate higher dividends or stock value growth in the future. However, high retained earnings may also mean that the company lacks investment opportunities or shareholders are less willing to pay dividends, so a comprehensive analysis needs to be conducted based on the company's specific situation and industry characteristics.","description":"Retained Earnings Per Share (REPS) is an indicator that measures the amount of retained earnings per common share of a company, reflecting the profits accumulated from past operations that have not yet been distributed to shareholders. This indicator can reflect the profitability accumulated within a company and can serve as an important reference for assessing the company's value and future growth potential. Compared with directly using total retained earnings, the per-share indicator is more convenient for cross-company comparisons because it eliminates the impact of differences in equity size, thereby providing a more standardized evaluation basis.","name":"Retained earnings per share","tags":["Value Factor"],"formulas":[{"text":"Retained earnings per share:","latex":"REPS = \\frac{Retained Earnings_{t}}{Shares Outstanding_{t}}"}],"formulaExplanation":{"text":"in:","symbols":[{"symbol":"REPS","description":"Retained Earnings Per Share."},{"symbol":"Retained Earnings_{t}","description":"Represents the retained earnings of the most recent reporting period (period t). Retained earnings refer to the portion of net profit that a company has extracted but not yet distributed to shareholders, and are usually used to support the company's future development and operations. This value comes from the retained earnings item on the balance sheet and is an important indicator of the company's internal accumulated profitability."},{"symbol":"Shares Outstanding_{t}","description":"Indicates the total common stock capital in the most recent reporting period (period t). Total stock capital refers to the number of all common shares issued by the company and held by shareholders. It is the basis for calculating per-share indicators. This value is usually derived from the company's financial report or announcement."}]},"references":[{"title":"Financial Statement Analysis","authors":"","publication":"","year":"","url":""},{"title":"Corporate Financial Management","authors":"","publication":"","year":"","url":""}],"related":[{"categoryId":"basic-surface","factorId":"basic-surface-retained-earnings-per-share","factorName":"Retained earnings per share"},{"categoryId":"quality","factorId":"quality-retained-earnings-per-share","factorName":"Retained Earnings per Share (REPS)"},{"categoryId":"basic-surface","factorId":"unallocated-profit-per-share","factorName":"Retained Earnings Per Share"},{"categoryId":"basic-surface","factorId":"surplus-reserve-per-share","factorName":"Earnings per share reserve"},{"categoryId":"basic-surface","factorId":"monetary-funds-per-share","factorName":"Cash per share"},{"categoryId":"basic-surface","factorId":"consistent-eps","factorName":"Analyst consensus price-to-earnings ratio is in the bottom"},{"categoryId":"basic-surface","factorId":"per-share-capital-reserve","factorName":"Capital reserve per share"},{"categoryId":"quality","factorId":"shareholder-earnings-to-market-cap","factorName":"Shareholder Earnings to Market Ratio"},{"categoryId":"emotion","factorId":"eps-revision-ratio","factorName":"Analyst consensus EPS revision ratio"},{"categoryId":"basic-surface","factorId":"earnings-per-share","factorName":"Diluted EPS"}],"lang":"en"}}]]
9:[["$","meta","0",{"charSet":"utf-8"}],["$","meta","1",{"name":"viewport","content":"width=device-width, initial-scale=1"}]]
b:[["$","title","0",{"children":"Retained earnings per share - seo.factor_title_suffix | Factors Directory - Quantitative Trading Factor Library"}],["$","meta","1",{"name":"description","content":"Retained Earnings Per Share (REPS) is an indicator that measures the amount of retained earnings per common share of a company, reflecting the profits accu..."}],["$","meta","2",{"name":"author","content":"Factors Directory Team"}],["$","meta","3",{"name":"keywords","content":"Retained earnings per share,quantitative trading,trading strategy,risk management,algorithmic trading,value,Value Factor"}],["$","meta","4",{"name":"creator","content":"Factors Directory"}],["$","meta","5",{"name":"publisher","content":"Factors Directory"}],["$","meta","6",{"name":"robots","content":"index, follow"}],["$","meta","7",{"name":"googlebot","content":"index, follow, max-video-preview:-1, max-image-preview:large, max-snippet:-1"}],["$","link","8",{"rel":"canonical","href":"https://factors.directory/en/factors/value/value-retained-earnings-per-share"}],["$","link","9",{"rel":"alternate","hrefLang":"en","href":"https://factors.directory/en/factors/value/value-retained-earnings-per-share"}],["$","link","10",{"rel":"alternate","hrefLang":"zh","href":"https://factors.directory/zh/factors/value/value-retained-earnings-per-share"}],["$","link","11",{"rel":"alternate","hrefLang":"ar","href":"https://factors.directory/ar/factors/value/value-retained-earnings-per-share"}],["$","link","12",{"rel":"alternate","hrefLang":"id","href":"https://factors.directory/id/factors/value/value-retained-earnings-per-share"}],["$","link","13",{"rel":"alternate","hrefLang":"ja","href":"https://factors.directory/ja/factors/value/value-retained-earnings-per-share"}],["$","link","14",{"rel":"alternate","hrefLang":"ko","href":"https://factors.directory/ko/factors/value/value-retained-earnings-per-share"}],["$","link","15",{"rel":"alternate","hrefLang":"ru","href":"https://factors.directory/ru/factors/value/value-retained-earnings-per-share"}],["$","link","16",{"rel":"alternate","hrefLang":"es","href":"https://factors.directory/es/factors/value/value-retained-earnings-per-share"}],["$","link","17",{"rel":"alternate","hrefLang":"de","href":"https://factors.directory/de/factors/value/value-retained-earnings-per-share"}],["$","link","18",{"rel":"alternate","hrefLang":"fr","href":"https://factors.directory/fr/factors/value/value-retained-earnings-per-share"}],["$","link","19",{"rel":"alternate","hrefLang":"tr","href":"https://factors.directory/tr/factors/value/value-retained-earnings-per-share"}],["$","link","20",{"rel":"alternate","hrefLang":"vi","href":"https://factors.directory/vi/factors/value/value-retained-earnings-per-share"}],["$","link","21",{"rel":"alternate","hrefLang":"th","href":"https://factors.directory/th/factors/value/value-retained-earnings-per-share"}],["$","link","22",{"rel":"alternate","hrefLang":"bn","href":"https://factors.directory/bn/factors/value/value-retained-earnings-per-share"}],["$","link","23",{"rel":"alternate","hrefLang":"hi","href":"https://factors.directory/hi/factors/value/value-retained-earnings-per-share"}],["$","link","24",{"rel":"alternate","hrefLang":"fa","href":"https://factors.directory/fa/factors/value/value-retained-earnings-per-share"}],["$","link","25",{"rel":"alternate","hrefLang":"tl","href":"https://factors.directory/tl/factors/value/value-retained-earnings-per-share"}],["$","link","26",{"rel":"alternate","hrefLang":"ms","href":"https://factors.directory/ms/factors/value/value-retained-earnings-per-share"}],["$","meta","27",{"name":"format-detection","content":"telephone=no, date=no, address=no, email=no"}],["$","meta","28",{"property":"og:title","content":"Retained earnings per share"}],["$","meta","29",{"property":"og:description","content":"Retained Earnings Per Share (REPS) is an indicator that measures the amount of retained earnings per common share of a company, reflecting the profits accu..."}],"$Le","$Lf","$L10","$L11","$L12","$L13","$L14","$L15","$L16","$L17","$L18","$L19","$L1a","$L1b","$L1c","$L1d","$L1e","$L1f","$L20","$L21","$L22","$L23","$L24","$L25","$L26","$L27","$L28","$L29","$L2a","$L2b","$L2c"]
7:null
2d:I[27201,["/_next/static/chunks/ff1a16fafef87110.js","/_next/static/chunks/d6145d29b805a899.js"],"IconMark"]
e:["$","meta","30",{"property":"og:url","content":"https://factors.directory/en/factors/value/value-retained-earnings-per-share"}]
f:["$","meta","31",{"property":"og:locale","content":"en"}]
10:["$","meta","32",{"property":"og:locale:alternate","content":"zh"}]
11:["$","meta","33",{"property":"og:locale:alternate","content":"ar"}]
12:["$","meta","34",{"property":"og:locale:alternate","content":"id"}]
13:["$","meta","35",{"property":"og:locale:alternate","content":"ja"}]
14:["$","meta","36",{"property":"og:locale:alternate","content":"ko"}]
15:["$","meta","37",{"property":"og:locale:alternate","content":"ru"}]
16:["$","meta","38",{"property":"og:locale:alternate","content":"es"}]
17:["$","meta","39",{"property":"og:locale:alternate","content":"de"}]
18:["$","meta","40",{"property":"og:locale:alternate","content":"fr"}]
19:["$","meta","41",{"property":"og:locale:alternate","content":"tr"}]
1a:["$","meta","42",{"property":"og:locale:alternate","content":"vi"}]
1b:["$","meta","43",{"property":"og:locale:alternate","content":"th"}]
1c:["$","meta","44",{"property":"og:locale:alternate","content":"bn"}]
1d:["$","meta","45",{"property":"og:locale:alternate","content":"hi"}]
1e:["$","meta","46",{"property":"og:locale:alternate","content":"fa"}]
1f:["$","meta","47",{"property":"og:locale:alternate","content":"tl"}]
20:["$","meta","48",{"property":"og:locale:alternate","content":"ms"}]
21:["$","meta","49",{"property":"og:type","content":"article"}]
22:["$","meta","50",{"property":"article:section","content":"value"}]
23:["$","meta","51",{"property":"article:tag","content":"Value Factor"}]
24:["$","meta","52",{"name":"twitter:card","content":"summary_large_image"}]
25:["$","meta","53",{"name":"twitter:site","content":"@FactorsDirectory"}]
26:["$","meta","54",{"name":"twitter:creator","content":"@FactorsDirectory"}]
27:["$","meta","55",{"name":"twitter:title","content":"Retained earnings per share"}]
28:["$","meta","56",{"name":"twitter:description","content":"Retained Earnings Per Share (REPS) is an indicator that measures the amount of retained earnings per common share of a company, reflecting the profits accu..."}]
29:["$","link","57",{"rel":"shortcut icon","href":"/factor_logo.png"}]
2a:["$","link","58",{"rel":"icon","href":"/factor_logo.png"}]
2b:["$","link","59",{"rel":"apple-touch-icon","href":"/factor_logo.png"}]
2c:["$","$L2d","60",{}]
```

# How to use

```shell
pip install -r requirements.txt
python factors_directory/main.py
```

# Output 
```shell
factors.jsonl
```
## For each line
```json
{
  "id": "value-retained-earnings-per-share",
  "title": "...",
  "description": "...",
  "formulas": ["..."],
  "source_url": "..."
}
```