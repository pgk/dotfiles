"""Shared vault-walking, name-index, and link-parsing helpers for the ariadne-* CLI tools."""

import fnmatch
import os
import re
import sys

# A ``` block holds code, not prose: a `## ` line inside one is sample text, not
# a section of the note. Shared so the two tools that must not be fooled by it
# -- splittable detection and chunking -- cannot drift apart.
FENCE_RE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)")
# The block :AriadneBacklinks writes into a note. Its content is derived from the
# vault's own links, so every tool here strips it before reading -- see
# strip_backlinks_block. The markers wrap the heading as well as the rows,
# because ariadne_splittable counts `##` headings and one in every note would
# drag notes toward its "long enough to split" gate.
BACKLINKS_OPEN = "<!-- ariadne:backlinks -->"
BACKLINKS_CLOSE = "<!-- /ariadne:backlinks -->"
# `vim.trim`'s character set, which the editor side cannot cheaply widen: its
# `%s` is byte-wise ASCII. See _block_spans.
BACKLINKS_TRIM = " \t\n\r\v\f"
# The whole span, brackets included, for rewriting rather than harvesting links.
WIKILINK_SPAN_RE = re.compile(r"!?\[\[([^\[\]]*)\]\]")


def printable(text):
    """Strip control characters from note- or server-derived text before it reaches a terminal."""
    return "".join(ch if ch.isprintable() else " " for ch in str(text))


def require_vault(vault):
    """Resolve the vault path, refusing to invent one.

    None of the ariadne-* tools carry an implicit ~/notes default. A mistyped or
    option-swallowed argument must never resolve to the user's real vault, so
    the path has to be named — as an argument or via $NOTES_VAULT. Call this
    before the vault is read, so a bad invocation costs nothing.
    """
    if vault and vault.strip():
        return vault
    from_env = os.environ.get("NOTES_VAULT", "").strip()
    if from_env:
        return from_env
    raise ValueError("a VAULT path is required — pass it as an argument or set $NOTES_VAULT")


def matched_excludes(rel, patterns):
    """Which patterns exclude this vault-relative path.

    A pattern is tested against the path *and* every directory above it, so
    `--exclude journal` excludes the whole subtree rather than nothing — matching
    only whole relative paths meant a bare directory name silently excluded no
    files at all. Matching is case-insensitive because the vault normally lives on
    a case-insensitive filesystem, where `Journal` and `journal` are the same
    directory and a capitalised pattern would otherwise miss it.

    This is the only thing keeping a subtree out of ariadne-similar's upload, so it
    fails loudly (see the warning in iter_markdown_files) rather than silently.
    """
    targets = [rel]
    parent = os.path.dirname(rel)
    while parent:
        targets.append(parent)
        parent = os.path.dirname(parent)
    lowered = [t.lower() for t in targets]
    return {
        pattern
        for pattern in patterns
        if any(fnmatch.fnmatchcase(t, pattern.rstrip("/").lower()) for t in lowered)
    }


def iter_markdown_files(vault, excludes):
    vault_real = os.path.realpath(vault)
    used = set()
    for root, dirs, files in os.walk(vault):
        keep = []
        for name in sorted(dirs):
            if name.startswith("."):
                continue
            hit = matched_excludes(os.path.relpath(os.path.join(root, name), vault), excludes)
            if hit:
                # Pruned, not just filtered: an excluded subtree is never walked.
                used |= hit
                continue
            keep.append(name)
        dirs[:] = keep
        for name in sorted(files):
            if not name.endswith(".md"):
                continue
            path = os.path.join(root, name)
            if not os.path.realpath(path).startswith(vault_real + os.sep):
                continue
            hit = matched_excludes(os.path.relpath(path, vault), excludes)
            if hit:
                used |= hit
                continue
            yield path
    for pattern in excludes:
        if pattern not in used:
            print(f"warning: --exclude {printable(pattern)} matched nothing", file=sys.stderr)


def _fenced_lines(lines):
    """Line indices inside a closed ``` fence — where a marker is an example, not a marker.

    A note documenting this feature quotes the markers, and a quoted *complete*
    block was taken as the live one. `backlinks.fenced` is the same walk. An
    unterminated fence is not a fence, the stance FENCE_RE already takes, so a
    stray ``` cannot hide the rest of a note's markers.
    """
    ticks = [i for i, line in enumerate(lines) if line.strip(BACKLINKS_TRIM).startswith("```")]
    inside = set()
    for opened, closed in zip(ticks[0::2], ticks[1::2]):
        inside.update(range(opened, closed + 1))
    return inside


def _block_spans(lines):
    """Every backlinks block, as inclusive (first, last) line indices.

    A block is a line that is exactly the opening marker, a body containing no
    further opening marker, and a line that is exactly the closing marker. This
    is `backlinks.spans` in the editor, deliberately line for line rather than a
    regex: the two are the two answers to "which links did the user write?", and
    a grammar they disagree on is a mirror on one side and not the other. It was
    a regex, and they disagreed about unspaced markers, trailing text on a marker
    line, and CRLF. `backlinks-block.fixture` now pins them to one artefact.

    A second opening marker restarts the block rather than nesting inside it, so
    an unpaired marker earlier in a note cannot pair with a real block's closer
    and swallow the prose between. An unterminated marker is left alone, as
    strip_frontmatter leaves an unterminated `---`.
    """
    found, open_at = [], None
    fenced = _fenced_lines(lines)
    for i, line in enumerate(lines):
        # BACKLINKS_TRIM, not a bare .strip(): that is the full Unicode
        # whitespace class, a strict superset of `vim.trim`'s, so a marker
        # preceded by a NBSP was a block to Python and not to the editor -- the
        # graph ignored the block while the editor read its rows back as authored
        # links and wrote the mirror. Python is the permissive side in every such
        # case, which is why this is the end that narrows.
        stripped = "" if i in fenced else line.strip(BACKLINKS_TRIM)
        if stripped == BACKLINKS_OPEN:
            open_at = i
        elif stripped == BACKLINKS_CLOSE and open_at is not None:
            found.append((open_at, i))
            open_at = None
    return found


def strip_backlinks_block(text):
    """Drop the `<!-- ariadne:backlinks -->` block: it is derived text, not written text.

    :AriadneBacklinks materialises what already links to a note. Reading those
    links back would mirror every link into its own source -- A links to B, so
    B's block names A, so A's block names B -- and each note's block would fill
    up with the notes it links to. Stripping is what keeps the block a report of
    the graph rather than part of it.

    The graph itself is unaffected either way: adjacency_from_links records both
    directions, so a backlink is already an edge. What the strip protects is
    everything that reads a note *directionally* or as prose -- splittable's
    out-degree and heading count, the embedded text, and the editor's own
    backlink scan.

    Every block goes, not just the first: a note that has ended up with two would
    otherwise have the other read back as authored links, which is the mirror.
    """
    lines = text.split("\n")
    spans = _block_spans(lines)
    if not spans:
        return text
    dropped = set()
    for first, last in spans:
        dropped.update(range(first, last + 1))
    return "\n".join(line for i, line in enumerate(lines) if i not in dropped)


def strip_frontmatter(text):
    """Drop a leading YAML frontmatter block (`---`-delimited); unterminated is left alone."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    rest = text[end + 4 :]
    return rest.split("\n", 1)[1] if "\n" in rest else ""


def note_mtimes(files):
    """{path: mtime}, warning once per note that cannot be stat'd."""
    mtimes = {}
    for path in files:
        try:
            mtimes[path] = os.path.getmtime(path)
        except OSError as exc:
            print(
                f"warning: cannot stat {printable(path)}: {printable(exc)}",
                file=sys.stderr,
            )
    return mtimes


def build_name_index(files):
    index = {}
    for path in files:
        stem = os.path.splitext(os.path.basename(path))[0].lower()
        if stem in index:
            print(
                f"warning: duplicate note name '{printable(stem)}', keeping {printable(index[stem])}",
                file=sys.stderr,
            )
            continue
        index[stem] = path
    return index


def extract_links(text):
    """Every note this text links to, as raw link targets -- authored links only.

    The strip happens here rather than at each caller so that no caller can
    forget it; see strip_backlinks_block for what forgetting would cost. Callers
    that need the block gone from *prose* as well (ariadne_note_text,
    ariadne_splittable) strip it themselves before their own reading.
    """
    links = []
    for raw in WIKILINK_RE.findall(strip_backlinks_block(text)):
        target = raw.split("#", 1)[0].strip()
        target = os.path.basename(target.replace("\\", "/"))
        if target:
            links.append(target)
    return links


def wikilink_display(text):
    """Rewrite every `[[wikilink]]` to the words a reader actually sees.

    `[[a|alias]]` becomes `alias`, `[[a#heading]]` becomes `a`, `[[dir/a]]`
    becomes `a`, `[[#heading]]` becomes `heading`, and a `![[embed]]` loses its
    `!` along with the brackets. Meant for anything that reads note prose as
    prose — embedding input above all, where a heavily linked note otherwise
    spends its budget on brackets and slugs instead of words.
    """

    def displayed(match):
        target, _, alias = match.group(1).partition("|")
        alias = alias.strip()
        if alias:
            return alias
        head, _, anchor = target.partition("#")
        return os.path.basename(head.replace("\\", "/")).strip() or anchor.strip()

    return WIKILINK_SPAN_RE.sub(displayed, text)


def resolve_link(link_text, name_index):
    if link_text.lower().endswith(".md"):
        link_text = link_text[:-3]
    return name_index.get(link_text.lower())
