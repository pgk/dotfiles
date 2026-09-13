#!/usr/bin/env python3

"""Tests for bin/ariadne_note_text -- what a note becomes before it is embedded.

Pure text in, text out: no vault, no embedding server, no cache.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ariadne_note_text


class NoteTextTests(unittest.TestCase):
    def test_backlinks_block_is_not_embedded(self):
        raw = (
            "The body.\n\n"
            "<!-- ariadne:backlinks -->\n## Backlinks\n\n- [[hub]]\n"
            "<!-- /ariadne:backlinks -->\n"
        )
        self.assertEqual(ariadne_note_text.note_text("n", raw), "n\n\nThe body.")

    def test_refreshing_backlinks_does_not_change_the_content_hash(self):
        # content_hash drives re-indexing, so a block left in the text would
        # re-embed and re-upload the note every time its backlinks were written.
        body = "The body.\n"
        blocked = body + "\n<!-- ariadne:backlinks -->\n- [[hub]]\n<!-- /ariadne:backlinks -->\n"
        self.assertEqual(
            ariadne_note_text.content_hash(ariadne_note_text.note_chunks("n", body)),
            ariadne_note_text.content_hash(ariadne_note_text.note_chunks("n", blocked)),
        )


    def test_frontmatter_is_stripped_and_name_prepended(self):
        text = ariadne_note_text.note_text("my-note", "---\ntitle: X\ntags:\n  - a\n---\nThe body.\n")
        self.assertEqual(text, "my-note\n\nThe body.")

    def test_note_without_frontmatter_keeps_its_body(self):
        self.assertEqual(ariadne_note_text.note_text("n", "Just text.\n"), "n\n\nJust text.")

    def test_frontmatter_only_note_yields_just_the_name(self):
        self.assertEqual(ariadne_note_text.note_text("n", "---\ntitle: X\n---\n"), "n")

    def test_unterminated_frontmatter_is_left_alone(self):
        self.assertEqual(ariadne_note_text.note_text("n", "---\ntitle: X\n"), "n\n\n---\ntitle: X")

    def test_wikilinks_embed_as_the_words_a_reader_sees(self):
        """Brackets and slugs would otherwise spend the embedding budget."""
        text = ariadne_note_text.note_text("n", "Builds on [[Working Memory]] and ![[dir/chunking|chunk size]].")
        self.assertEqual(text, "n\n\nBuilds on Working Memory and chunk size.")

    def test_hash_ignores_a_link_being_rewritten_to_the_same_words(self):
        a = ariadne_note_text.note_chunks("n", "Builds on [[Working Memory]].")
        b = ariadne_note_text.note_chunks("n", "Builds on [[working-memory|Working Memory]].")
        self.assertEqual(ariadne_note_text.content_hash(a), ariadne_note_text.content_hash(b))

    def test_long_note_is_truncated(self):
        text = ariadne_note_text.note_text("n", "x" * (ariadne_note_text.MAX_CHARS * 2))
        self.assertEqual(len(text), ariadne_note_text.MAX_CHARS)

    def test_hash_ignores_frontmatter_only_edits(self):
        a = ariadne_note_text.note_chunks("n", "---\ntags: [one]\n---\nBody.\n")
        b = ariadne_note_text.note_chunks("n", "---\ntags: [two]\n---\nBody.\n")
        self.assertEqual(ariadne_note_text.content_hash(a), ariadne_note_text.content_hash(b))

    def test_hash_changes_when_body_changes(self):
        a = ariadne_note_text.note_chunks("n", "Body one.")
        b = ariadne_note_text.note_chunks("n", "Body two.")
        self.assertNotEqual(ariadne_note_text.content_hash(a), ariadne_note_text.content_hash(b))

    def test_hash_separates_the_chunks_it_covers(self):
        """Concatenating chunks would let a moved boundary keep the same hash."""
        self.assertNotEqual(
            ariadne_note_text.content_hash(["ab", "c"]), ariadne_note_text.content_hash(["a", "bc"])
        )

    def test_hash_sees_past_the_truncation_point(self):
        """note_text() stops at MAX_CHARS; two notes agreeing that far are still different notes."""
        filler = "x" * ariadne_note_text.MAX_CHARS
        a = ariadne_note_text.note_chunks("n", f"## s\n{filler}\n\n## t\nalpha")
        b = ariadne_note_text.note_chunks("n", f"## s\n{filler}\n\n## t\nbeta")
        self.assertNotEqual(ariadne_note_text.content_hash(a), ariadne_note_text.content_hash(b))

    def test_preview_skips_headings_and_blank_lines(self):
        text = ariadne_note_text.note_text("n", "# Heading\n\n\nReal first line.\n")
        self.assertEqual(ariadne_note_text.preview_of(text), "Real first line.")


class NoteChunksTests(unittest.TestCase):
    """Only long notes split; a short one must embed exactly as it always has."""

    def test_a_short_note_is_one_chunk_identical_to_note_text(self):
        raw = "## First\n\nShort.\n\n## Second\n\nAlso short.\n"
        self.assertLessEqual(len(raw), ariadne_note_text.CHUNK_THRESHOLD)
        self.assertEqual(
            ariadne_note_text.note_chunks("n", raw), [ariadne_note_text.note_text("n", raw)]
        )

    def test_a_note_exactly_at_the_threshold_is_not_split(self):
        """Two sections, so 'one chunk' cannot be confused with 'split into one piece'."""
        name = "n"
        head = "## a\n"
        tail = "\n\n## b\nyy"
        filler = "x" * (ariadne_note_text.CHUNK_THRESHOLD - len(name) - 2 - len(head) - len(tail))
        body = head + filler + tail
        chunks = ariadne_note_text.note_chunks(name, body)
        self.assertEqual(len(ariadne_note_text.note_text(name, body)), ariadne_note_text.CHUNK_THRESHOLD)
        self.assertEqual(chunks, [ariadne_note_text.note_text(name, body)])

    def test_one_character_over_the_threshold_does_split(self):
        name = "n"
        head = "## a\n"
        tail = "\n\n## b\nyy"
        filler = "x" * (ariadne_note_text.CHUNK_THRESHOLD - len(name) - 1 - len(head) - len(tail))
        chunks = ariadne_note_text.note_chunks(name, head + filler + tail)
        self.assertEqual(len(chunks), 2)

    def test_a_long_note_splits_at_its_own_section_headings(self):
        body = "## Alpha\n" + "a" * 900 + "\n\n## Beta\n" + "b" * 900 + "\n"
        chunks = ariadne_note_text.note_chunks("n", body)
        self.assertEqual(len(chunks), 2)
        self.assertTrue(all(c.startswith("n\n\n") for c in chunks))
        self.assertIn("## Alpha", chunks[0])
        self.assertIn("## Beta", chunks[1])
        self.assertNotIn("## Beta", chunks[0])

    def test_a_single_hash_is_a_title_not_a_section_boundary(self):
        """Over the threshold so it reaches the splitter, but inside one window, so the
        chunk count can only be 2 if `#` is wrongly treated as a boundary."""
        name = "a-long-note-name-so-the-whole-note-clears-the-threshold"
        head, mid = "# Title\n", "\n\n# Another\n"
        filler = (ariadne_note_text.CHUNK_WINDOW - len(head) - len(mid)) // 2
        body = head + "a " * (filler // 2) + mid + "b " * (filler // 2)
        self.assertGreater(len(name) + 2 + len(body), ariadne_note_text.CHUNK_THRESHOLD)
        self.assertLessEqual(len(body), ariadne_note_text.CHUNK_WINDOW)
        self.assertEqual(len(ariadne_note_text.note_chunks(name, body)), 1)

    def test_a_heading_after_a_tab_is_still_a_boundary(self):
        body = "##\tAlpha\n" + "a " * 400 + "\n\n##\tBeta\n" + "b " * 400
        self.assertEqual(len(ariadne_note_text.note_chunks("n", body)), 2)

    def test_a_heading_inside_a_code_fence_is_sample_text(self):
        """Splitting there would end one chunk mid-fence and orphan the code in the next."""
        fenced = "```markdown\n## Example\n" + "code line\n" * 60 + "```"
        body = "Prose about markdown. " * 30 + "\n\n" + fenced + "\n\n## Real Section\n" + "b " * 400
        chunks = ariadne_note_text.note_chunks("n", body)
        self.assertEqual(len(chunks), 2)
        self.assertIn("## Example", chunks[0])
        self.assertIn("```", chunks[0].split("## Example", 1)[1])
        self.assertIn("## Real Section", chunks[1])

    def test_an_oversized_section_is_windowed_with_overlap(self):
        section = "z" * 4300
        chunks = ariadne_note_text.note_chunks("n", "## Only\n" + section)
        self.assertGreater(len(chunks), 2)
        window, overlap = ariadne_note_text.CHUNK_WINDOW, ariadne_note_text.CHUNK_OVERLAP
        bodies = [c.split("\n\n", 1)[1] for c in chunks]
        # Every piece but the last is exactly a window; the last absorbs a short
        # remainder, so it runs up to window + overlap.
        self.assertTrue(all(len(b) == window for b in bodies[:-1]))
        self.assertLessEqual(len(bodies[-1]), window + overlap)
        self.assertEqual(bodies[1][:overlap], bodies[0][window - overlap :])

    def test_windowing_reconstructs_the_section_exactly(self):
        """Non-repeating filler, and exact reconstruction -- a periodic filler would
        match anywhere and let a dropped tail pass."""
        section = ("## Only\n" + "".join(f"{i:05d} " for i in range(900))).strip()
        chunks = ariadne_note_text.note_chunks("n", section)
        bodies = [c.split("\n\n", 1)[1] for c in chunks]
        overlap = ariadne_note_text.CHUNK_OVERLAP
        self.assertGreater(len(bodies), 3)
        self.assertEqual(bodies[0] + "".join(b[overlap:] for b in bodies[1:]), section)

    def test_a_remainder_too_short_to_stand_alone_stays_in_the_previous_window(self):
        """An almost-all-overlap tail would carry as much of the centroid as a full window."""
        window, overlap = ariadne_note_text.CHUNK_WINDOW, ariadne_note_text.CHUNK_OVERLAP
        chunks = ariadne_note_text.note_chunks("n", "## Only\n" + "z" * (window + overlap - 20))
        self.assertEqual(len(chunks), 1)
        for extra in (overlap, overlap + 400):
            bodies = [
                c.split("\n\n", 1)[1]
                for c in ariadne_note_text.note_chunks("n", "## Only\n" + "z" * (window + extra))
            ]
            self.assertEqual(len(bodies), 2)
            self.assertGreaterEqual(len(bodies[1]) - overlap, overlap)

    def test_no_note_exceeds_the_cache_vector_limit(self):
        """save_cache refuses an over-cap note; the chunker is what keeps that unreachable."""
        chunks = ariadne_note_text.note_chunks("n", "## s\n" + "x" * 4_000_000)
        self.assertEqual(len(chunks), ariadne_note_text.MAX_CHUNKS)

    def test_a_long_note_is_no_longer_truncated_away(self):
        """The whole point: past MAX_CHARS the baseline embedded nothing at all."""
        body = "## Early\n" + "e" * ariadne_note_text.MAX_CHARS + "\n\n## Late\n" + "distinctive tail\n"
        chunks = ariadne_note_text.note_chunks("n", body)
        self.assertNotIn("distinctive tail", ariadne_note_text.note_text("n", body))
        self.assertTrue(any("distinctive tail" in c for c in chunks))

    def test_every_chunk_stays_within_the_model_budget(self):
        chunks = ariadne_note_text.note_chunks("n", "## s\n" + "x" * 30000)
        self.assertTrue(all(len(c) <= ariadne_note_text.MAX_CHARS for c in chunks))

    def test_a_bodyless_note_is_still_one_chunk(self):
        self.assertEqual(ariadne_note_text.note_chunks("n", "---\ntitle: X\n---\n"), ["n"])


class EmbeddedNameTests(unittest.TestCase):
    """A Folgezettel id in front of a name is the note's address, not its subject.

    Measured on a 173-note public wikilink corpus, the id costs MRR at every
    level of alignment between the id tree and the link graph: -2.2% relative
    when the tree mirrors the links exactly, -5.5% when it has drifted, with
    every interval below full alignment excluding zero; bin/CLAUDE.md carries the
    table. `branch.lua` puts an id on every note it creates, so this is the
    common shape, not an edge case.
    """

    def test_an_id_is_dropped_from_the_name_a_note_embeds(self):
        chunks = ariadne_note_text.note_chunks("1a2b Working Memory", "the idea itself")
        self.assertEqual(chunks, ["Working Memory\n\nthe idea itself"])

    def test_the_whole_folgezettel_grammar_is_recognised(self):
        for name in ("1 X", "12 X", "1a X", "1a1 X", "1a1a X", "1ab2c X"):
            with self.subTest(name=name):
                self.assertEqual(ariadne_note_text.embedded_name(name), "X")

    def test_a_name_that_does_not_open_with_an_id_is_untouched(self):
        """`1a-2` is not an alternating sequence, `1A2B` is not lowercase and an
        id starts with digits -- the same reading as folgezettel.lua's segments(),
        which is what branch.lua allocates against."""
        for name in ("Working Memory", "2026-09-05 Monday", "1a-2 X", "1A2B X", "a1 X"):
            with self.subTest(name=name):
                self.assertEqual(ariadne_note_text.embedded_name(name), name)

    def test_a_name_that_is_only_an_id_keeps_it(self):
        """Stripping would leave nothing to embed, and the empty string is a
        worse thing to put in the index than an uninformative name."""
        self.assertEqual(ariadne_note_text.embedded_name("1a2b"), "1a2b")
        self.assertEqual(ariadne_note_text.note_chunks("1a2b", "---\ntitle: X\n---\n"), ["1a2b"])

    def test_every_chunk_of_a_long_note_drops_the_id(self):
        chunks = ariadne_note_text.note_chunks("1a2b Working Memory", "word " * 900)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(c.startswith("Working Memory\n\n") for c in chunks))

    def test_the_query_end_strips_the_same_id_as_the_document_end(self):
        """`--search --from` has to ask in the shape the index was built in, so
        the two ends strip together or the feature quietly regresses."""
        body = "the idea itself, see [[Working Memory|memory]]"
        self.assertEqual(
            ariadne_note_text.passage_chunks(body, "1a2b Working Memory"),
            ariadne_note_text.note_chunks("1a2b Working Memory", body),
        )

    def test_a_passage_carries_the_title_without_the_id(self):
        self.assertEqual(
            ariadne_note_text.passage_chunks("the idea itself", "1a2b Working Memory"),
            ["Working Memory\n\nthe idea itself"],
        )

    def test_note_text_strips_the_id_too(self):
        """note_text is the anchor the one-chunk invariant is asserted against,
        so a strip that reached note_chunks alone would make that invariant false
        while every suite stayed green."""
        self.assertEqual(
            ariadne_note_text.note_chunks("1a2b Working Memory", "the idea itself"),
            [ariadne_note_text.note_text("1a2b Working Memory", "the idea itself")],
        )

    def test_a_bare_id_is_kept_by_the_document_end_and_withheld_by_the_query_end(self):
        """The one place the two ends deliberately disagree, pinned so a future
        "fix" cannot quietly align them. `note_chunks` heads a chunk
        unconditionally -- a document is stored as `name\n\nbody` -- while the
        query end drops a name that says nothing. Neither side has anything
        better to use for a note called only `1a2b`."""
        body = "the idea itself"
        self.assertEqual(ariadne_note_text.note_chunks("1a2b", body), ["1a2b\n\nthe idea itself"])
        self.assertEqual(ariadne_note_text.passage_chunks(body, "1a2b"), [body])

    def test_an_id_does_not_change_the_content_hash_of_the_title(self):
        """The one-off re-index this forces is the whole cost of the change; a
        note whose name was already bare must not be re-embedded for nothing."""
        self.assertEqual(
            ariadne_note_text.content_hash(ariadne_note_text.note_chunks("1a2b Garden Log", "b")),
            ariadne_note_text.content_hash(ariadne_note_text.note_chunks("Garden Log", "b")),
        )


class PassageChunksTests(unittest.TestCase):
    """A lifted selection, chunked as a query rather than stored as a note."""

    def test_a_short_passage_stays_one_chunk_and_is_unchanged(self):
        self.assertEqual(ariadne_note_text.passage_chunks("one idea, briefly put"),
                         ["one idea, briefly put"])

    def test_surrounding_whitespace_is_dropped(self):
        """A visual selection routinely carries a trailing newline."""
        self.assertEqual(ariadne_note_text.passage_chunks("  an idea\n\n"), ["an idea"])

    def test_with_no_name_nothing_is_prefixed(self):
        body = "the idea itself"
        self.assertEqual(ariadne_note_text.passage_chunks(body), [body])

    def test_a_name_that_carries_words_is_prefixed_as_a_stored_chunk_would_be(self):
        """Matching how documents are stored is the whole reason it helps.

        The body carries a wikilink on purpose: without one this asserted a broad
        equivalence while only exercising the single case where the two agree."""
        body = "the idea itself, see [[Working Memory|memory]]"
        self.assertEqual(
            ariadne_note_text.passage_chunks(body, "Working Memory"),
            ariadne_note_text.note_chunks("Working Memory", body),
        )

    def test_a_date_shaped_name_is_left_off(self):
        """The case this is conditional for: a daily note's title says nothing,
        and prefixing it measurably costs accuracy rather than merely not helping."""
        body = "the idea itself"
        self.assertEqual(ariadne_note_text.passage_chunks(body, "2026-09-05"), [body])

    def test_a_bare_folgezettel_id_is_left_off(self):
        body = "the idea itself"
        self.assertEqual(ariadne_note_text.passage_chunks(body, "1a2b"), [body])

    def test_informative_name_splits_words_from_dates_and_ids(self):
        for name in ("Working Memory", "db", "2026-09-05 Monday", "작업 기억", "a-note"):
            with self.subTest(name=name):
                self.assertTrue(ariadne_note_text.informative_name(name))
        for name in ("2026-09-05", "20260905", "1a2b", "1abc", "12ab", "", "12.3.4", "0081", None):
            with self.subTest(name=name):
                self.assertFalse(ariadne_note_text.informative_name(name))

    def test_every_chunk_of_a_long_passage_carries_the_name(self):
        """`note_chunks` puts the name on every chunk, and the query is scored on
        whichever chunk matches best -- so one bare chunk would be shape-mismatched."""
        chunks = ariadne_note_text.passage_chunks("word " * 900, "Working Memory")
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(c.startswith("Working Memory\n\n") for c in chunks))

    def test_a_long_passage_is_split_rather_than_truncated(self):
        text = "word " * 900  # 4500 chars, well past CHUNK_THRESHOLD
        chunks = ariadne_note_text.passage_chunks(text)
        self.assertGreater(len(chunks), 1)
        # Nothing is lost off the end: the tail survives into the last chunk.
        self.assertTrue(chunks[-1].endswith("word"))

    def test_a_passage_is_cut_at_its_own_headings(self):
        first, second = "alpha " * 260, "beta " * 260
        chunks = ariadne_note_text.passage_chunks(f"## One\n\n{first}\n\n## Two\n\n{second}")
        self.assertTrue(chunks[0].startswith("## One"))
        self.assertTrue(any(c.startswith("## Two") for c in chunks))

    def test_the_chunk_count_is_capped_for_a_query(self):
        """Unbounded chunks would mean an unbounded query, not just a big note."""
        chunks = ariadne_note_text.passage_chunks("word " * 20000)
        self.assertEqual(len(chunks), ariadne_note_text.MAX_QUERY_CHUNKS)

    def test_a_passage_just_over_the_cap_in_sections_is_packed_not_truncated(self):
        """The boundary of the bug above: MAX_QUERY_CHUNKS + 1 sections."""
        n = ariadne_note_text.MAX_QUERY_CHUNKS + 1
        text = "".join(f"## S{i}\n\n{'filler words ' * 8}\n\n" for i in range(n))
        self.assertIn(f"S{n - 1}", " ".join(ariadne_note_text.passage_chunks(text)))

    def test_a_heading_dense_passage_keeps_its_tail(self):
        """The cap is 8 while note_chunks' gate is 32, so sections must be packed
        against THIS cap -- otherwise a selection of 9 to 32 short sections had
        everything past the eighth silently dropped."""
        text = "".join(f"## Section {i}\n\n{'body words here ' * 7}\n\n" for i in range(20))
        chunks = ariadne_note_text.passage_chunks(text)
        self.assertLessEqual(len(chunks), ariadne_note_text.MAX_QUERY_CHUNKS)
        self.assertIn("Section 19", " ".join(chunks))
        kept = sum(len(c) for c in chunks)
        self.assertGreater(kept, 0.95 * len(text))

    def test_a_passage_is_normalized_the_way_a_document_is(self):
        """Documents are indexed with wikilinks flattened; a query embedding the
        raw brackets would be scored against an index that has none."""
        body = "Mulch holds moisture, see [[Working Memory|memory]]."
        self.assertEqual(
            ariadne_note_text.passage_chunks(body, "Garden Log"),
            ariadne_note_text.note_chunks("Garden Log", body),
        )
        self.assertNotIn("[[", ariadne_note_text.passage_chunks(body)[0])

    def test_frontmatter_lifted_with_a_selection_is_dropped(self):
        text = "---\ntags: [a]\n---\n\nthe idea itself"
        self.assertEqual(ariadne_note_text.passage_chunks(text), ["the idea itself"])


class SectionCapTests(unittest.TestCase):
    """A note that is a list of short headings must not become one vector each."""

    def note_of_sections(self, count, length=40):
        return "".join(f"## Section {i}\n{'x' * length}\n\n" for i in range(count))

    def test_under_the_cap_every_section_is_its_own_chunk(self):
        raw = self.note_of_sections(ariadne_note_text.MAX_SECTIONS)
        chunks = ariadne_note_text.note_chunks("n", raw)
        self.assertEqual(len(chunks), ariadne_note_text.MAX_SECTIONS)

    def test_over_the_cap_sections_are_packed_up_to_the_window(self):
        raw = self.note_of_sections(ariadne_note_text.MAX_SECTIONS + 1)
        chunks = ariadne_note_text.note_chunks("n", raw)
        self.assertLess(len(chunks), ariadne_note_text.MAX_SECTIONS)
        bodies = [c.split("\n\n", 1)[1] for c in chunks]
        self.assertTrue(all(len(b) <= ariadne_note_text.CHUNK_WINDOW for b in bodies))

    def test_packing_keeps_every_section(self):
        raw = self.note_of_sections(200)
        joined = "\n\n".join(ariadne_note_text.note_chunks("n", raw))
        for i in range(200):
            self.assertIn(f"## Section {i}\n", joined)

    def test_a_pathological_note_stays_within_a_sane_chunk_count(self):
        """163 sections is a real note in a public vault; unpacked it was a ~4.7 s query."""
        chunks = ariadne_note_text.note_chunks("n", self.note_of_sections(500))
        self.assertLess(len(chunks), 40)

    def test_long_sections_are_not_packed_together(self):
        """Packing only helps notes shredded into tiny chunks; long sections stay apart."""
        raw = "".join(f"## Section {i}\n{'x' * 1400}\n\n" for i in range(ariadne_note_text.MAX_SECTIONS + 1))
        chunks = ariadne_note_text.note_chunks("n", raw)
        self.assertEqual(len(chunks), ariadne_note_text.MAX_SECTIONS + 1)


if __name__ == "__main__":
    unittest.main()
