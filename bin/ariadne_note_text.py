"""What a note contributes to the embedding index: its chunks, and their hash.

Knows nothing about vectors, the cache, or the CLI.

The invariant every caller depends on: a note at or under CHUNK_THRESHOLD
yields exactly one chunk, byte-identical to `note_text()`. Most of a vault is
short notes about one idea, and splitting those only costs precision.
"""

import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ariadne_common

MAX_CHARS = 8000
PREVIEW_CHARS = 60
# Above this many characters a note is split; at or below it stays one vector.
# The threshold, not the chunk size, is the knob that matters -- 700 and 1500
# tied as chunk sizes, while chunking short notes is where the losses were.
CHUNK_THRESHOLD = 1500
CHUNK_WINDOW = 1500
CHUNK_OVERLAP = 200
# Past this many sections, pack them together instead of embedding each one.
# A note that is a list of short headings would otherwise become one vector per
# heading -- 163 of them in a real public vault -- and since `--similar` scores
# every chunk of the *target*, that one note would be a ~4.7 s query. Measured
# on 326 public notes against their author's wikilinks: MRR 0.225 -> 0.223,
# worst case 59 chunks -> 27. Packing *every* note costs 0.225 -> 0.216, which
# is why this is a cap and not the rule.
MAX_SECTIONS = 32
# Hard ceiling on vectors for one note, so the write side can never record a
# count the cache's own parse bound will reject -- which would invalidate the
# whole index and re-upload the vault on every run. It also bounds a query: a
# target's chunks are each scored against every note, at ~29 ms per chunk over
# 3,000 notes. The ceiling is in chunks, so what it means in characters depends
# on the note's shape: ~52 k for one long section, ~10 k for a note that spends
# its first 31 chunks on short ones. Past that the note is not indexed -- still
# further out than the 8,000 MAX_CHARS used to cut at.
MAX_CHUNKS = 40
# A heading opens a section; the heading line stays with the section it opens.
# `#` alone is the note's title, not a boundary.
HEADING_RE = re.compile(r"^#{2,6}[ \t]", re.MULTILINE)


def note_body(raw):
    """The prose of a note: frontmatter dropped, wikilinks flattened to their words.

    `[[Working Memory]]` is two words of meaning wrapped in punctuation, and
    embedding the punctuation spends the model's budget on brackets and slugs.

    The backlinks block goes too, and not only because a list of note names is
    noise in a vector: content_hash is taken over these chunks, so a block left
    in would re-embed the note every time its backlinks were refreshed.
    """
    authored = ariadne_common.strip_backlinks_block(raw)
    return ariadne_common.wikilink_display(ariadne_common.strip_frontmatter(authored)).strip()


def _headed(name, text):
    """One embeddable string: the note name, then the text it heads.

    Every chunk carries the name, so a section stays attached to the note it
    came from even when the model only ever sees that section.
    """
    return (f"{name}\n\n{text}" if text else name)[:MAX_CHARS]


def _sections(body):
    """`body` cut at its headings, ignoring any that sit inside a code fence.

    A fenced `## ` is sample text. Splitting there ends one chunk mid-fence and
    opens the next with orphaned code. An *unterminated* fence is not a fence to
    `FENCE_RE`, so headings after it still split -- same reading as
    ariadne_splittable, and no text is lost either way.
    """
    fenced = [m.span() for m in ariadne_common.FENCE_RE.finditer(body)]
    cuts = [0]
    for match in HEADING_RE.finditer(body):
        if not any(start <= match.start() < end for start, end in fenced):
            cuts.append(match.start())
    cuts.append(len(body))
    return [s for s in (body[a:b].strip() for a, b in zip(cuts, cuts[1:])) if s]


def _windows(section):
    """`section` in CHUNK_WINDOW-sized pieces, each repeating CHUNK_OVERLAP of the last,
    so an idea straddling a boundary is not lost from both sides.

    A remainder too short to stand alone is kept in the previous piece instead of
    becoming its own, so the *last* piece runs up to CHUNK_WINDOW + CHUNK_OVERLAP
    and a section shorter than that is never split at all. Chunks are averaged
    unweighted into the note's vector, so a 200-character tail that is mostly
    overlap would otherwise carry as much of the note's meaning as a full window.
    """
    step = CHUNK_WINDOW - CHUNK_OVERLAP
    pieces = []
    start = 0
    while True:
        if len(section) - (start + CHUNK_WINDOW) < CHUNK_OVERLAP:
            pieces.append(section[start:])
            return pieces
        pieces.append(section[start : start + CHUNK_WINDOW])
        start += step


def _packed(sections):
    """Consecutive sections joined up to CHUNK_WINDOW, so a note that is a list of
    short headings does not spend one vector per heading."""
    packed, buffered = [], ""
    for section in sections:
        if not buffered:
            buffered = section
        elif len(buffered) + 2 + len(section) <= CHUNK_WINDOW:
            buffered = f"{buffered}\n\n{section}"
        else:
            packed.append(buffered)
            buffered = section
    if buffered:
        packed.append(buffered)
    return packed


# A query's chunks are each scored against every note in the vault, so this
# bounds one interactive query rather than one note's stored size -- which is
# why it is far tighter than MAX_CHUNKS. At ~29 ms per chunk over 3,000 notes,
# eight keeps a passage query under a quarter of a second, and eight windows
# span ~10,600 characters, longer than any paragraph anyone selects on purpose.
MAX_QUERY_CHUNKS = 8
# A run of two or more letters -- any script, so a CJK title counts. What this
# separates is a name carrying *words* from one that is only digits and
# punctuation: `2026-09-05`, or a bare folgezettel id like `1a2b`.
WORDY_RE = re.compile(r"[^\W\d_]{2,}", re.UNICODE)


def informative_name(name):
    """Whether a note's name says anything, as opposed to being a date or an id.

    The distinction is load-bearing rather than cosmetic: prefixing a passage
    with its note's name is worth +2.7% / +1.8% MRR when the name is words, and
    costs -2.2% / -2.0% when it is a date. See `passage_chunks` for the method.
    """
    return bool(name) and bool(WORDY_RE.search(name))


def passage_chunks(text, name=None):
    """A lifted passage as the strings to embed for it.

    Cut the way a note is -- at its own headings, then windowed -- so a long
    selection is not silently truncated at the model's context, which is the
    defect `note_chunks()` removed for notes. A short one stays a single vector.

    `name` is the note the passage was lifted out of, and it is prefixed the way
    `note_chunks()` prefixes a note's own name **only when it carries words**.
    Measured over 522 source notes in four public corpora, two seeds: a real
    name is worth +2.7% and +1.8% MRR, positive on every corpus. The obvious
    reading is shape-matching -- documents are stored as `name\n\nbody`, so a
    query in that shape sits closer to how the index was built.

    A blank passage is the caller's problem, not this function's: it returns a
    single empty chunk rather than raising, and `--search` already refuses a
    blank phrase before reaching here.

    An *uninformative* name is not merely inert, which is why this is
    conditional rather than unconditional. Replacing each corpus title with a
    date-shaped string, changing nothing else, costs -2.2% and -2.0% pooled over
    the same two seeds -- and -3.8% / -3.6% on the largest corpus, every one of
    those intervals excluding zero. That is exactly the daily note this whole feature exists
    to serve -- `2026-09-05` says nothing about the passage, and date strings are
    highly similar to each other, which is the same effect that already defeats
    `--duplicates`' title gate.
    """
    # Normalized exactly as a document is: frontmatter dropped, `[[wikilinks]]`
    # flattened to the words a reader sees. The index is built that way, so a
    # raw selection would spend the model's budget on brackets and slugs the
    # documents do not have -- and the daily note this feature is for is
    # wikilink-dense. Same reasoning as note_chunks, applied to the query side.
    text = note_body(text)
    head = name if informative_name(name) else None
    if len(text) <= CHUNK_THRESHOLD:
        return [_headed(head, text) if head else text[:MAX_CHARS]]
    sections = _sections(text)
    # Packed against the cap that actually applies here. Gating on MAX_SECTIONS
    # like note_chunks does would be wrong: there the cap (MAX_CHUNKS, 40) is
    # larger than the gate (32), so no section is ever lost, while here the cap
    # is 8 -- so a selection of 9 to 32 short sections got no packing and had
    # everything past the eighth silently dropped.
    if len(sections) > MAX_QUERY_CHUNKS:
        sections = _packed(sections)
    chunks = [piece for section in sections for piece in _windows(section)]
    return [_headed(head, c) if head else c[:MAX_CHARS] for c in chunks[:MAX_QUERY_CHUNKS]]


def note_text(name, raw):
    """The whole note as one embeddable string -- what a short note still embeds as.

    Nothing in the tool calls this: `note_chunks()` is the entry point. It stays
    as the anchor for the invariant, which the tests assert against it directly.
    """
    return _headed(name, note_body(raw))


def note_chunks(name, raw):
    """The strings actually embedded for a note, in order.

    A short note yields one chunk identical to `note_text()`. A longer one is
    cut at its own `##` headings: a note's sections are where its separate ideas
    already are, so the unit comes from structure rather than a tuned length.

    Changing any of this changes every note's content hash, which is what forces
    the one-off re-index.
    """
    body = note_body(raw)
    whole = f"{name}\n\n{body}" if body else name
    if len(whole) <= CHUNK_THRESHOLD:
        return [whole[:MAX_CHARS]]

    sections = _sections(body)
    if len(sections) > MAX_SECTIONS:
        sections = _packed(sections)
    chunks = [piece for section in sections for piece in _windows(section)]
    # `or` is not dead: a note whose name alone clears the threshold has no body
    # to section, and every caller indexes chunks[0].
    return [_headed(name, c) for c in chunks[:MAX_CHUNKS]] or [whole[:MAX_CHARS]]


def content_hash(chunks):
    """Fingerprint of everything a note gets embedded as, boundaries included.

    Not of `note_text()`: that stops at MAX_CHARS, so two notes agreeing for 8000
    characters and diverging after would share a hash, and one would be served
    the other's vectors. The NUL between chunks means moving a boundary changes
    the hash even when the concatenated text does not.
    """
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:32]


def preview_of(text):
    """First non-empty body line, for picker rows. Assumes one `note_chunks()` chunk."""
    lines = text.split("\n\n", 1)
    body = lines[1] if len(lines) > 1 else ""
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            if len(stripped) > PREVIEW_CHARS:
                return stripped[:PREVIEW_CHARS] + "…"
            return stripped
    return ""
