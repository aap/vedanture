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

  inventory loaded (27 items — type inv to see)

› 2

RV 2  Gṛtsamada  ·  43 hymns

  ── hymns to Agni ─────────────────────────────────
     1.  2.1       Agni                              16v
     2.  2.2       Agni                              13v
     3.  2.3       Apri hymn                         11v
     4.  2.4       Agni                              9v
     5.  2.5       Agni                              8v
     6.  2.6       Agni                              8v
     7.  2.7       Agni                              6v
     8.  2.8       Agni                              6v
     9.  2.9       Agni                              6v
    10.  2.10      Agni                              6v
  ── hymns to Indra ────────────────────────────────
    11.  2.11      Indra                             21v
    12.  2.12      Indra                             15v
    13.  2.13      Indra                             13v
    14.  2.14      Indra                             12v
    15.  2.15      Indra                             10v
    16.  2.16      Indra                             9v
    17.  2.17      Indra                             9v
    18.  2.18      Indra                             9v
    19.  2.19      Indra                             9v
    20.  2.20      Indra                             9v
    21.  2.21      Indra                             6v
    22.  2.22      Indra                             4v
  ── hymns to Brahmanaspati ────────────────────────
    23.  2.23      Brahmanaspati                     19v
    24.  2.24      Brahmanaspati                     16v
    25.  2.25      Brahmanaspati                     5v
    26.  2.26      Brahmanaspati                     4v
  ── hymns to the Adityas ──────────────────────────
    27.  2.27      Adityas                           17v
    28.  2.28      Varuna                            11v
    29.  2.29      all the gods                      7v
  ── hymns to various gods ─────────────────────────
    30.  2.30      Indra and other gods              11v
    31.  2.31      all the gods                      7v
    32.  2.32      diverse gods                      8v
    33.  2.33      Rudra                             15v
    34.  2.34      the Maruts                        15v
    35.  2.35      Apam Napat                        15v
    36.  2.36      cycle of the gods                 6v
    37.  2.37      cycle of the gods                 6v
    38.  2.38      Savitri                           11v
    39.  2.39      Asvins                            8v
    40.  2.40      Soma and  Pusan                   6v
    41.  2.41      diverse gods                      21v
    42.  2.42      bird of omen                      3v
    43.  2.43      bird of omen                      3v


› 28
  loading…
RV 2.28  11 verses

  2.28.1
    idáṁ kavér ādityásya svarā́jo
    víśvāni sā́nty abhy àstu mahnā́
    áti yó mandró yajáthāya deváḥ
    sukīrtím bhikṣe váruṇasya bhū́reḥ

  2.28.2
    táva vraté subhágāsaḥ syāma
    svādhyò varuṇa tuṣṭuvā́ṁsaḥ
    upā́yana uṣásāṁ gómatīnām
    agnáyo ná járamāṇā ánu dyū́n

  2.28.3
    táva syāma puruvī́rasya śármann
    uruśáṁsasya varuṇa praṇetaḥ
    yūyáṁ naḥ putrā aditer adabdhāḥ-
    abhí kṣamadhvaṁ yújyāya devāḥ

  2.28.4
    prá sīm ādityó asr̥jad vidhartā́m̐
    r̥táṁ síndhavo váruṇasya yanti
    ná śrāmyanti ná ví mucanty eté
    váyo ná paptū raghuyā́ párijman

  2.28.5
    ví mác chrathāya raśanā́m ivā́gaḥ-
    r̥dhyā́ma te varuṇa khā́m r̥tásya
    mā́ tántuś chedi váyato dhíyam me
    mā́ mā́trā śāry apásaḥ purá r̥tóḥ

  2.28.6
    ápo sú myakṣa varuṇa bhiyásam mát
    sámrāḷ ŕ̥tāvó 'nu mā gr̥bhāya
    dā́meva vatsā́d ví mumugdhy áṁho
    nahí tvád āré nimíṣaś canéśe

  2.28.7
    mā́ no vadhaír varuṇa yé ta iṣṭā́v
    énaḥ kr̥ṇvántam asura bhrīṇánti
    mā́ jyótiṣaḥ pravasathā́ni ganma
    ví ṣū́ mŕ̥dhaḥ śiśratho jīváse naḥ

  2.28.8
    námaḥ purā́ te varuṇotá nūnám
    utā́paráṁ tuvijāta bravāma
    tvé hí kam párvate ná śritā́ni-
    ápracyutāni dūḷabha vratā́ni

  2.28.9
    pára r̥ṇā́ sāvīr ádha mátkr̥tāni
    mā́háṁ rājann anyákr̥tena bhojam
    ávyuṣṭā ín nú bhū́yasīr uṣā́saḥ-
    ā́ no jīvā́n varuṇa tā́su śādhi

  2.28.10
    yó me rājan yújyo vā sákhā vā
    svápne bhayám bhīráve máhyam ā́ha
    stenó vā yó dípsati no vŕ̥ko vā
    tváṁ tásmād varuṇa pāhy asmā́n

  2.28.11
    mā́hám maghóno varuṇa priyásya
    bhūridā́vna ā́ vidaṁ śū́nam āpéḥ
    mā́ rāyó rājan suyámād áva sthām
    br̥hád vadema vidáthe suvī́rāḥ

  type a verse number (e.g. 3), or n to step through

2.28 › 5

2.28.5   —  ví mác chrathāya raśanā́m ivā́gaḥ-

  ví mác chrathāya raśanā́m ivā́gaḥ-
  r̥dhyā́ma te varuṇa khā́m r̥tásya
  mā́ tántuś chedi váyato dhíyam me
  mā́ mā́trā śāry apásaḥ purá r̥tóḥ

  [graßmann]  Lös' ab von mir wie einen Strick die Sünde, wir wollen dir der Andacht Quell ergiessern Nicht reiss' der Faden, wenn Gebet ich webe, nicht vor der Zeit brech' ab das Mass des Wirkens.
  [geldner]   Löse die Sünde von mir wie einen Gurt ! Wir möchten dir den Born der Wahrheit recht machen. Der Faden soll nicht reißen, während ich meine Dichtung webe, noch soll der Maßstab des Werkmeisters vor der Zeit brechen.
  [griffith]  Loose me from sin as from a bond that binds me: may we swell, Varuna, thy spring of Order. Let not my thread, while I weave song, be severed, nor my work's sum, before the time, be shattered.
  23 words  ·  x to expand  ·  n/p next/prev

2.28.5 › chant

vi mac chra̍thāya raśa̱nām i̱vāga̍ ṛ̱dhyāma̍ te varuṇa̱ khām ṛ̱tasya̍ |

        -                       -        -                        -
-  ○       ●  -  -     ●     ●        ●     ●  -  -     ●     ○
                    -     -        ○                 -     -

mā tantu̍ś chedi̱ vaya̍to̱ dhiya̍m me̱ mā mātrā̍ śāry a̱pasa̍ḥ pu̱ra ṛ̱toḥ ||

       ○            -        ○             ●            ○
●  ○       ●     -        -  -      ●  ●   -  ●      -         -    ●
              -        ●         ●                -         -     -


2.28.5 › x

  1  ví          ví       
  2  mát         ahám     case=ABL  number=SG
  3  śrathāya    √śrathⁱ- number=SG  person=2  mood=IMP  tense=PRS  voice=ACT
  4  raśanā́m    raśanā́- case=ACC  gender=F  number=SG
  5  iva         iva      
  6  ā́gaḥ       ā́gas-   gender=N  number=SG
  7  r̥dhyā́ma   √r̥dh-   number=PL  person=1  mood=OPT  tense=AOR  voice=ACT
  8  te          tvám     number=SG
  9  varuṇa      váruṇa-  case=VOC  gender=M  number=SG
  10  khā́m       khā́-    case=ACC  gender=F  number=SG
  11  r̥tásya     r̥tá-    case=GEN  gender=N  number=SG
  12  mā́         mā́      
  13  tántuḥ      tántu-   case=NOM  gender=M  number=SG
  14  chedi       √chid-   number=SG  person=3  mood=INJ  tense=AOR  voice=PASS
  15  váyataḥ     √u- 2    tense=PRS  voice=ACT
  16  dhíyam      dhī́-    case=ACC  gender=F  number=SG
  17  me          ahám     number=SG
  18  mā́         mā́      
  19  mā́trā      mā́trā-  case=NOM  gender=F  number=SG
  20  śāri        √śr̥̄- 1 number=SG  person=3  mood=INJ  tense=AOR  voice=PASS
  21  apásaḥ      apás-    case=GEN  gender=M  number=SG
  22  purā́       purā́    
  23  r̥tóḥ       r̥tú-    case=ABL  gender=M  number=SG
  type a number to select a word (1–23)

2.28.5 › 14

  chedi  →  √chid-  ·  number=SG  person=3  mood=INJ  tense=AOR  voice=PASS  ·  5 tokens
  par · conc · lem · def · look
  nearby:  1. vaṭūrín-  2. arbhaká-  3. bharatá-  4. carítra-  5. parṇá-  6. mā́

2.28.5  [√chid-] › lem

  lemma √chid-  ·  5 occurrences

     1.  1.109.3    a   chedma         mā́ chedma raśmī́m̐r íti nā́dhamānāḥ
     2.  1.116.15   a   áchedi         carítraṁ hí vér ivā́chedi parṇám
     3.  1.133.2    c   chindhí        chindhí vaṭūríṇā padā́
     4.  2.28.5     c   chedi          mā́ tántuś chedi váyato dhíyam me
     5.  7.33.6     b   párichinnāḥ    párichinnā bharatā́ arbhakā́saḥ


2.28.5  [√chid-] › def

chid  GRA #3365
  corpus:  √ chid-

  chid [Cu. 295], abschneiden (Fuss, Flügel, A.), abreissen, zerreissen (Faden, Zügel, A.), zerstossen (den Kopf, A., mit dem Fusse, I.). -- Mit pári,  ringsum beschneiden [A.].
      Stamm chind (stark chinad):
     -dhí [für -ddhí 2. s. Impv.] çīrṣâ padâ [1.133.2]
      Aorist áched:
     -di [3. s. pass.] carítram vés iva parṇám [1.116.15]
       ched:
     -dma mâ raçmîn [1.109.3]
     -di [3. s. pass.] mâ tántus … váyatas dhíyam me [2.28.5]
      Part. Pass. chidyamāna
     in á-chidyamāna.
      Part. II. chinna:
     -ās pári: daṇḍâs iva goájanāsas [7.33.6]
      Verbale chíd ( zerbrechend )
     enthalten in úkha-chíd. [Page463]

  ─── nearby ──────────────────────────
      →    3365  chid
    1.    3355  chanda                 11.    3366  chidra
    2.    3356  chandas                12.    3367  chubuka
    3.    3357  chandasya              13.    3368  jaṁhas
    4.    3358  chandaḥstubh           14.    3369  jakṣ
    5.    3359  chandu                 15.    3370  jakṣ
    6.    3360  chandia                16.    3371  jagat
    7.    3361  chardiṣpā              17.    3372  jagatpā
    8.    3362  chardis                18.    3373  jaguri
    9.    3363  chāga                  19.    3374  jagdha
   10.    3364  chāyā                  20.    3375  jagmi

  ─── see also ─────────────────────────
   21.   Impv
   22.   pass


2.28.5  [√chid-] › par

√chid-  root  5 tokens
  ────────────────────────────────────────────────────────────────

  present imperative active
          SG                      
  2       chindhí                 

  aorist indicative passive
          SG                      
  3       áchedi                  

  aorist injunctive active
          PL                      
  1       chedma                  

  aorist injunctive passive
          SG                      
  3       chedi                   

  
          PL                      
  ?       párichinnāḥ             


2.28.5  [√chid-] › inv

  inv1              par: hŕ̥daya-
  inv4              def: hī́ḍ-
  agni1             RV 1.1
  agni2             RV 1.12
  agni3             RV 7.1
  agni4             RV 4.1
  agni5             RV 10.1
  agni6             RV 6.1
  soma1             RV 9.1
  soma2             RV 9.2
  soma3             RV 9.96
  soma4             RV 9.113
  vas1              RV 7.18
  vas2              RV 7.33
  varuna1           RV 7.86
  sarasvati1        RV 7.95
  sarasvati2        RV 7.96
  frog              RV 7.103
  yatu              RV 7.104
  ushas1            RV 4.51
  ushas2            RV 1.92
  devi              RV 10.125
  ratri             RV 10.127
  samanam           RV 10.191
  mitra             RV 3.59
  surya             RV 1.115
  indra1            RV 1.32


2.28.5  [√chid-] › go devi
  loading…
RV 10.125  8 verses

  10.125.1
    aháṁ rudrébhir vásubhiś carāmi-
    ahám ādityaír utá viśvádevaiḥ
    ahám mitrā́váruṇobhā́ bibharmi-
    ahám indrāgnī́ ahám aśvínobhā́

  10.125.2
    aháṁ sómam āhanásam bibharmi-
    aháṁ tváṣṭāram utá pūṣáṇam bhágam
    aháṁ dadhāmi dráviṇaṁ havíṣmate
    suprāvyè yájamānāya sunvaté

  10.125.3
    aháṁ rā́ṣṭrī saṁgámanī vásūnāṁ
    cikitúṣī prathamā́ yajñíyānām
    tā́m mā devā́ vy àdadhuḥ purutrā́
    bhū́risthātrām bhū́ry āveśáyantīm

  10.125.4
    máyā só ánnam atti yó vipáśyati
    yáḥ prā́ṇiti yá īṁ śr̥ṇóty uktám
    amantávo mā́ṁ tá úpa kṣiyanti
    śrudhí śruta śraddhiváṁ te vadāmi

  10.125.5
    ahám evá svayám idáṁ vadāmi
    júṣṭaṁ devébhir utá mā́nuṣebhiḥ
    yáṁ kāmáye táṁ-tam ugráṁ kr̥ṇomi
    tám brahmā́ṇaṁ tám ŕ̥ṣiṁ táṁ sumedhā́m

  10.125.6
    aháṁ rudrā́ya dhánur ā́ tanomi
    brahmadvíṣe śárave hántavā́ u
    aháṁ jánāya samádaṁ kr̥ṇomi-
    aháṁ dyā́vāpr̥thivī́ ā́ viveśa

  10.125.7
    aháṁ suve pitáram asya mūrdhán
    máma yónir apsv àntáḥ samudré
    táto ví tiṣṭhe bhúvanā́nu víśvā-
    -utā́mū́ṁ dyā́ṁ varṣmáṇópa spr̥śāmi

  10.125.8
    ahám evá vā́ta iva prá vāmi-
    ārábhamāṇā bhúvanāni víśvā
    paró divā́ pará enā́ pr̥thivyā́
    -etā́vatī mahinā́ sám babhūva

  type a verse number (e.g. 3), or n to step through

10.125 › 
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
7.            open maṇḍala index
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
