# vedanture

A text-adventure style explorer for the Ṛgveda, built on the fully
morphologically annotated corpus from the
[VedaWeb project](https://vedaweb.uni-koeln.de/) (University of Cologne).

Every word in the Ṛgveda (~164,000 tokens across 10,552 verses) is linked
to its dictionary lemma and tagged with full morphological features.
Vedanture lets you navigate this data interactively — reading hymns,
inspecting word-by-word annotation, browsing paradigms, following
concordance threads, looking up Grassmann's dictionary, and hearing the
Vedic pitch accent.

## Sample session

```
% python3 rv.py
Ṛgveda Explorer
  1.1  to open the first hymn  ·  find soma  to search  ·  h for help


› 7.33
RV 7.33  14 verses

  7.33.1
    śvityáñco mā dakṣiṇatáskapardāḥ-
    dhiyaṁjinvā́so abhí hí pramandúḥ
    uttíṣṭhan voce pári barhíṣo nr̥̄́n
    ná me dūrā́d ávitave vásiṣṭhāḥ

  7.33.2
    dūrā́d índram anayann ā́ suténa
    tiró vaiśantám áti pā́ntam ugrám
    pā́śadyumnasya vāyatásya sómāt
    sutā́d índro 'vr̥ṇītā vásiṣṭhān

  7.33.3
    evén nú kaṁ síndhum ebhis tatāra-
    evén nú kam bhedám ebhir jaghāna
    evén nú kaṁ dāśarājñé sudā́sam
    prā́vad índro bráhmaṇā vo vasiṣṭhāḥ

  7.33.4
    júṣṭī naro bráhmaṇā vaḥ pitr̥̄ṇā́m
    ákṣam avyayaṁ ná kílā riṣātha
    yác chákvarīṣu br̥hatā́ ráveṇa-
    -índre śúṣmam ádadhātā vasiṣṭhāḥ

  7.33.5
    úd dyā́m ivét tr̥ṣṇájo nāthitā́saḥ-
    -ádīdhayur dāśarājñé vr̥tā́saḥ
    vásiṣṭhasya stuvatá índro aśrod
    urúṁ tŕ̥tsubhyo akr̥ṇod ulokám

  7.33.6
    daṇḍā́ ivéd goájanāsa āsan
    párichinnā bharatā́ arbhakā́saḥ
    ábhavac ca puraetā́ vásiṣṭhaḥ-
    ā́d ít tŕ̥tsūnāṁ víśo aprathanta

  7.33.7
    tráyaḥ kr̥ṇvanti bhúvaneṣu rétas
    tisráḥ prajā́ ā́ryā jyótiragrāḥ
    tráyo gharmā́sa uṣásaṁ sacante
    sárvām̐ ít tā́m̐ ánu vidur vásiṣṭhāḥ

  7.33.8
    sū́ryasyeva vakṣátho jyótir eṣāṁ
    samudrásyeva mahimā́ gabhīráḥ
    vā́tasyeva prajavó nā́nyéna
    stómo vasiṣṭhā ánvetave vaḥ

  7.33.9
    tá ín niṇyáṁ hŕ̥dayasya praketaíḥ
    sahásravalśam abhí sáṁ caranti
    yaména tatám paridhíṁ váyanto
    -apsarása úpa sedur vásiṣṭhāḥ

  7.33.10
    vidyúto jyótiḥ pári saṁjíhānam
    mitrā́váruṇā yád ápaśyatāṁ tvā
    tát te jánmotaíkaṁ vasiṣṭha-
    -agástyo yát tvā viśá ājabhā́ra

  7.33.11
    utā́si maitrāvaruṇó vasiṣṭha-
    -urváśyā brahman mánasó 'dhi jātáḥ
    drapsáṁ skannám bráhmaṇā daívyena
    víśve devā́ḥ púṣkare tvādadanta

  7.33.12
    sá praketá ubháyasya pravidvā́n
    sahásradāna utá vā sádānaḥ
    yaména tatám paridhíṁ vayiṣyánn
    apsarásaḥ pári jajñe vásiṣṭhaḥ

  7.33.13
    satré ha jātā́v iṣitā́ námobhiḥ
    kumbhé rétaḥ siṣicatuḥ samānám
    táto ha mā́na úd iyāya mádhyāt
    táto jātám ŕ̥ṣim āhur vásiṣṭham

  7.33.14
    ukthabhŕ̥taṁ sāmabhŕ̥tam bibharti
    grā́vāṇam bíbhrat prá vadāty ágre
    úpainam ādhvaṁ sumanasyámānāḥ-
    ā́ vo gachāti pratr̥do vásiṣṭhaḥ

  type a verse number (e.g. 3), or n to step through

7.33 › 9

7.33.9   —  tá ín niṇyáṁ hŕ̥dayasya praketaíḥ

  tá ín niṇyáṁ hŕ̥dayasya praketaíḥ
  sahásravalśam abhí sáṁ caranti
  yaména tatám paridhíṁ váyanto
  -apsarása úpa sedur vásiṣṭhāḥ

  [griffith]  They with perceptions of the heart in secret resort to that which spreads a thousand branches. The Apsaras brought hither the Vasisthas wearing the vesture spun for them by Yama.
  [geldner]  Sie dringen nach den Ahnungen ihres Herzens in das tausendfach verzweigte Geheimnis ein. Während die an dem von Yama aufgespannten Rahmen weiter weben, verehren die Vasistha´s die Apsarasen.
  17 words  ·  x to expand  ·  n/p next/prev

7.33.9 › chant

ta in ni̱ṇyaṁ hṛda̍yasya prake̱taiḥ sa̱hasra̍valśam a̱bhi saṁ ca̍ranti |

                 -                           -                   -
-  ○      ○   -     ○   ○   -     ●      ○      ○   -     -  ○      ○   -
      ○                        ●      -                -

ya̱mena̍ ta̱tam pa̍ri̱dhiṁ vaya̍nto 'psa̱rasa̱ upa̍ sedu̱r vasi̍ṣṭhāḥ ||

      -         -            ○                  -            ○
   ●        ○         ○   -  -   ●      -     -    ●      -      ●
-        -         -                 -     -          ○


7.33.9 › x

  1  té              sá- ~ tá-     case=NOM  gender=M  number=PL
  2  ít              ít            
  3  niṇyám          niṇyá-        gender=N  number=SG
  4  hŕ̥dayasya      hŕ̥daya-      case=GEN  gender=N  number=SG
  5  praketaíḥ       praketá-      case=INS  gender=M  number=PL
  6  sahásravalśam   sahásravalśa- gender=N  number=SG
  7  abhí            abhí          
  8  sám             sám           
  9  caranti         √carⁱ-        number=PL  person=3  mood=IND  tense=PRS  voice=ACT
  10  yaména          yamá-         case=INS  gender=M  number=SG
  11  tatám           √tan-         case=ACC  gender=M  number=SG  non-finite=PPP
  12  paridhím        paridhí-      case=ACC  gender=M  number=SG
  13  váyantaḥ        √u- 2         case=NOM  gender=M  number=PL  tense=PRS  voice=ACT
  14  apsarásaḥ       apsarás-      case=ACC  gender=F  number=PL
  15  úpa             úpa           
  16  seduḥ           √sad-         number=PL  person=3  mood=IND  tense=PRF  voice=ACT
  17  vásiṣṭhāḥ       vásiṣṭha-     case=NOM  gender=M  number=PL
  type a number to select a word (1–17)

7.33.9 › 4

  hŕ̥dayasya  →  hŕ̥daya-  (a-stem)  ·  case=GEN  gender=N  number=SG  ·  16 tokens
  par · conc · lem

7.33.9  [hŕ̥daya-] › def

  GRA #10727

  hŕdaya, n. [vgl. hŕd], (1) Herz im leiblichen Sinne; (2) Herz als Sitz der Empfindung, Liebe, Furcht u. s. w.
     -am (1) [6.53.8]  [10.34.9] -- (2) [10.10.13]  [10.95.17]
     -āt (1) [10.163.3]
     -asya (2) praketês [7.33.9] [Page1679]
     -e (1) [1.122.9]  [10.87.4]  [10.87.13]. -- (2) [6.9.6]
     -āni (2) [10.85.47] (sám añyantu … nō); [10.95.15] (sālāvṙkâṇām … etâ); [10.191.4]
     -ā (1) [6.53.5]  [6.53.7].
     -eṣu (2) [10.84.7] (bhiyam dádhānās).

  ─── nearby ──────────────────────────
    10724  hr̥tsuas
    10725  hr̥d
    10726  hr̥daṁsani
  → 10727  hr̥daya
    10728  hr̥dayāvidh
    10729  hr̥dayya
    10730  hr̥dispr̥ś


7.33.9  [hŕ̥daya-] › par

hŕ̥daya-  a-stem  ·  nominal stem  16 tokens
  ────────────────────────────────────────────────────────────────

            SG                      PL                    
  ────────────────────────────────────────────────────────────────
  NOM       —                       hŕ̥dayāni             
  ACC       —                       hŕ̥dayā(2)            
  GEN       hŕ̥dayasya              —                     
  ABL       hŕ̥dayāt                —                     
  LOC       hŕ̥daye(4)              hŕ̥dayeṣu             
  (other)   hŕ̥dayam(4)             hŕ̥dayāni(2)          


7.33.9  [hŕ̥daya-] › keep
  saved: inv1 → par: hŕ̥daya-

7.33.9  [hŕ̥daya-] › s

RV 7.33  14 verses

  7.33.1
    śvityáñco mā dakṣiṇatáskapardāḥ-
    dhiyaṁjinvā́so abhí hí pramandúḥ
    uttíṣṭhan voce pári barhíṣo nr̥̄́n
    ná me dūrā́d ávitave vásiṣṭhāḥ

  [ ... the hymn again ... ]

  7.33.14
    ukthabhŕ̥taṁ sāmabhŕ̥tam bibharti
    grā́vāṇam bíbhrat prá vadāty ágre
    úpainam ādhvaṁ sumanasyámānāḥ-
    ā́ vo gachāti pratr̥do vásiṣṭhaḥ


7.33 › keep
  saved: inv2 → RV 7.33

7.33 › inv

  inv1              par: hŕ̥daya-
  inv2              RV 7.33


7.33 › go inv1

hŕ̥daya-  a-stem  ·  nominal stem  16 tokens
  ────────────────────────────────────────────────────────────────

            SG                      PL                    
  ────────────────────────────────────────────────────────────────
  NOM       —                       hŕ̥dayāni             
  ACC       —                       hŕ̥dayā(2)            
  GEN       hŕ̥dayasya              —                     
  ABL       hŕ̥dayāt                —                     
  LOC       hŕ̥daye(4)              hŕ̥dayeṣu             
  (other)   hŕ̥dayam(4)             hŕ̥dayāni(2)          


7.33 › 
```

## Quick start

```sh
# clone with submodules
git clone --recurse-submodules <url> vedanture
cd vedanture

# build the derived data (takes ~5 min total)
python3 build_paradigms.py
python3 split_paradigms.py
python3 build_concordance.py
python3 build_gravity.py

# explore
python3 rv.py
```

## Commands

```
1.1           open hymn 1.1
1.1.3         go to verse
n / p         next / previous verse
s             back to current hymn
back / b      previous place in history

x             show word table
3             select word 3
par           paradigm
conc          concordance (this form)
lem           concordance (whole lemma)
def           Grassmann dictionary entry
chant         Vedic pitch accent notation
look          nearby lemmas · look 20 for more

keep <name>   save current place to inventory
drop <name>   remove from inventory
go <name>     navigate to saved place
inv           list inventory

find soma     fuzzy lemma search
h             help
q             quit
```

## Corpus submodules

The `corpus/` directory contains three submodules from the
[C-SALT project](https://github.com/cceh) (CC-licensed):

| Submodule | Contents |
|-----------|----------|
| `c-salt_vedaweb_tei` | Annotated Ṛgveda in TEI-P5 XML (317 MB) |
| `c-salt_sanskrit_data` | Sanskrit dictionaries: Grassmann, Monier-Williams, Apte, … |
| `c-salt_vedaweb_sources` | Source texts, translations, metadata |

## Other tools

- `paradigm.py` — standalone paradigm lookup
- `verse.py` — annotated verse display + concordance
- `docs/corpus.md` — TEI schema, feature encoding, corpus structure
- `docs/gravity.md` — design spec for the textual gravity / proximity system

## Chant notation

Vedic pitch accent is rendered as a 3-level staff (South Indian tradition):

```
top    ● ○ -   svarita (high)
mid    ● ○ -   udātta / pracaya (mid)
bottom ● ○ -   anudātta (low)

●  heavy by nature   ○  heavy by position   -  light
```

Requires `~/rgveda_audio/` with `rv_lines.txt` and `ghanapati.py`.

## Dependencies

```
lxml
```
