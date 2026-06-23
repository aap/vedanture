"""
ghanapati — Vedic pitch accent (svara) for romanised Saṃhitā text.

Self-contained and stdlib-only, so it can be reused outside this project.
Turns an accented IAST line into per-syllable (segment, tone, length) tuples
and, optionally, a three-row ASCII pitch staff.

    from ghanapati import processline, render_ascii
    num, text, sounds, tones = processline("1.001.01a  a̱gnim ī̍ḻe ...")
    print(render_ascii(tones, label=text))

Input accent marks recognised:
    U+0331  combining macron below          → anudātta (low)
    U+030D  combining vertical line above    → svarita  (high)

Tone codes produced:
    `   short svarita (high)        /   rising svarita (mid→high)
    -   udātta / pracaya (mid)      _   anudātta (low)        `_ , _`_  combos
Length codes produced:
    =   heavy by nature (long vowel)   —  heavy by position   .  light
"""

import unicodedata as _ud

__all__ = ["processline", "shakehead", "render_ascii",
           "transliterate", "syllabify"]


def isvowel(s):
    return s in ['a', 'ā', 'i', 'ī', 'u', 'ū', 'e', 'o', 'E', 'O', 'ṛ', 'ṝ', 'ḷ']

def islong(s):
    return s in ['ā', 'ī', 'ū', 'e', 'o', 'E', 'O', 'ṝ']

def isnasal(s):
    return s in ['ṁ', 'ṃ', 'ṅ', 'ñ', 'n', 'ṇ', 'm']


def transliterate(text):
    """Fold digraphs to single capitals and accent marks to ` / _ ."""
    text = text.replace('ai', 'E').replace('au', 'O') \
               .replace('kh', 'K').replace('gh', 'G') \
               .replace('ch', 'C').replace('jh', 'J') \
               .replace('th', 'T').replace('dh', 'D') \
               .replace('ṭh', 'Ṭ').replace('ḍh', 'Ḍ') \
               .replace('ph', 'P').replace('bh', 'B') \
               .replace("'", '')
    # the combining tone marks don't replace cleanly in bulk, so map per char
    out = ''
    for s in text:
        if s == '̱':      # U+0331 — anudātta
            s = '_'
        elif s == '̍':    # U+030D — svarita
            s = '`'
        out += s
    return out


def fixtone(tone):
    if tone[-2:] == '_`':
        return tone[:-2] + '`_'
    if tone == '':
        return '-'
    return tone


def syllabify(sounds):
    """Split a transliterated, accent-coded string into (tone, syllable) pairs.

    Not phonologically rigorous, but good enough for pitch placement.
    """
    syls = []
    syl = ""
    tone = ''
    gotvowel = False
    cons = ''
    for s in sounds:
        if s in ['_', '`']:
            tone += s
        elif isvowel(s):
            if gotvowel:
                syls.append((tone, syl))
                tone = ''
                syl = ''
            syl += cons
            cons = ''
            syl += s
            gotvowel = True
        else:
            syl += cons
            cons = s
    syls.append((tone, syl + cons))
    return syls


def processsyl(syl):
    """(tone, segment) → (segment, tone, length)."""
    tone = fixtone(syl[0])
    seg = syl[1]
    length = '.'
    if not isvowel(seg[-1]):
        length = '—'
    for s in seg:
        if islong(s):
            length = '='
    for v, n in zip(seg, (seg + '.')[1:]):
        if tone == '`' and (islong(v) or isvowel(v) and isnasal(n)):
            tone = '/'
    return (seg, tone, length)


def shakehead(sounds):
    """Transliterated string → [(segment, tone, length), ...]."""
    syls = syllabify(sounds)
    return [processsyl(syl) for syl in syls]


def processline(line):
    """"<num> <accented text>" → (num, text, sounds, tones)."""
    num, text = line.split(None, 1)
    sounds = transliterate(text).replace('|', '').replace(' ', '')
    return (num, text, sounds, shakehead(sounds))


def render_ascii(tones, label=""):
    """Render syllables as a 3-row pitch staff.

    Pitch levels (South Indian Vedic chanting tradition):
      top row    — svarita          : high
      middle row — udātta / pracaya : mid
      bottom row — anudātta         : low

    Note symbols encode syllable weight:
      ●  heavy by nature  (long vowel)
      ○  heavy by position (closed syllable)
      -  light

    Rising svarita (/) places the weight symbol at top and - at mid,
    showing the ascent from mid to high.
    """
    W = {'=': '●', '—': '○', '.': '-'}   # weight → symbol

    def dw(s):
        return sum(1 for c in s if _ud.category(c)[0] != 'M')

    def marks(tone, length):
        """Return (top, mid, bot) for this tone+length combination."""
        n = W[length]
        if tone == '`':    return (n,   ' ', ' ')   # short svarita — high
        if tone == '/':    return (n,   '-', ' ')   # rising svarita — mid→high
        if tone == '-':    return (' ',  n,  ' ')   # udātta/pracaya — mid
        if tone == '_':    return (' ', ' ',  n)    # anudātta — low
        if tone == '`_':   return (n,   ' ',  n)    # svarita then anudātta
        if tone == '_`_':  return (n,   ' ',  n)    # anudātta–svarita–anudātta
        return (' ', n, ' ')                         # fallback: mid

    cols = []
    for seg, tone, length in tones:
        t, m, b = marks(tone, length)
        w = dw(seg) + 1
        cols.append((seg, t, m, b, w))

    def build(pick):
        out = ''
        for seg, t, m, b, w in cols:
            ch = (t, m, b)[pick]
            out += ch + ' ' * (w - dw(ch))
        return out.rstrip()

    out = []
    if label:
        out += [label, '']
    out += [build(0), build(1), build(2)]
    return '\n'.join(out)
