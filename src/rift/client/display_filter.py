"""Minimal readability filter for the raw GS4/DR XML-tagged stream.

NOT the real protocol parser - that is the future job of the `protocol` package, with real tag semantics, structured events, and proper handling of things like vitals/room state. This exists only because the raw dump in client v1 is functionally unusable for actual play (confirmed against a real captured session, 2026-09-07): most lines are UI-panel scaffolding (dialogData, openDialog) that a real front-end renders as GUI widgets, never meant to be read as transcript text.

Deliberately dumb: no real XML parsing, no handling of tags split across
reads, no semantic understanding. A handful of tags have their entire
content dropped (verified noise or duplicated elsewhere); every other tag
is stripped down to its inner text via one generic regex, so unknown tag
types degrade safely (text kept) instead of needing constant updates.
"""

from __future__ import annotations

import re

# Verified against real session captures: dialogData/openDialog are pure
# UI-widget definitions (vitals bars, combat buttons, injury panels) with
# no narrative content; the room desc/objs text belonging to compDef is
# duplicated by the plain, <style>-tagged narrative that follows shortly
# after, and its "room players" variant is consistently empty. spell/
# left/right are current-state notification fields (prepared spell, hand
# contents) that get re-sent whenever that state changes, not narrative
# text - their bare values ("None", "Empty") are meaningless without the
# labels only a real structured-event model (the future `protocol`
# package) can supply; concatenated as plain text they just read as
# garbage (confirmed by the user, 2026-09-07). prompt is the "> "
# input-ready marker sent by the game, resent on its own periodic timer
# (the "time" attribute), not once per player action - confirmed live,
# 2026-09-07, appearing after nearly every other component in a capture,
# producing runs of near-empty "> " lines. Most front ends squelch this
# as background signal and never render it as transcript text at all
# (per the user, 2026-09-07) - this client has no use for it either,
# since it has its own dedicated input box rather than a command-echo
# convention that would need the prompt as a visual cue. The "time"
# value itself is not lost: the raw session log still captures it in
# full for whenever a real round-timer becomes `protocol`-package work -
# display_filter.py stays a dumb text-stripper, not a state tracker (see
# docs/decisions.md). Drop tag and content for all of these.
_DROP_WITH_CONTENT = ("dialogData", "openDialog", "compDef", "spell", "left", "right", "prompt")

# TEMPORARY, evidence-based suppression (2026-09-07): the "inv" pushStream
# block (the full worn-items listing) gets rebroadcast in full on many
# commands unrelated to inventory (e.g. "ready weapon", "stow weapon") -
# confirmed via a real session where it appeared 4 times in a few minutes
# of play. Showing it only when actually requested needs to correlate the
# outgoing command with the response, which is real `protocol`/`engine`
# work this stateless filter cannot do - so for now it is dropped
# unconditionally, accepting that the output of an explicit "inventory"
# command is also hidden until a real processing mechanism replaces this.
_DROP_STREAM_IDS = ("inv",)

# TEMPORARY, evidence-based suppression (2026-09-07): unlike the "room
# objs"/"room players" belonging to compDef (dropped above as duplicated
# by the plain narrative that follows), the earlier assumption that
# <component id="room objs"/"room players"> content was unique and must
# be kept was wrong. A real session showed it resent standalone - after a
# prompt push, after a combat dialogData update, after typing "exit" -
# with no accompanying room name/description, purely because an NPC in
# the room moved. This is the same mechanism as the dialogData/openDialog
# panels above: real Wrayth has a dedicated "current room" GUI panel that
# these updates keep live independent of what the player is currently
# looking at, the same way combat/vitals panels get their own
# independent updates - it is not narrative text pushed to a transcript.
# The genuine full room presentation (on room entry or "look") never uses
# this <component> wrapper at all; it sends the room name/description/
# population/exits as plain narrative text framed by self-closing
# <style .../> markers, which this filter already passes through
# untouched. So dropping the content of this wrapper unconditionally
# removes only the redundant standalone panel-refresh broadcasts, never
# the real room display. Long-term, the right home for this data is a
# structured "current room" state in the future `protocol` package
# (consumed, not discarded) rather than a permanent drop - see
# docs/decisions.md.
_DROP_COMPONENT_IDS = ("room objs", "room players")

_TAG_WITH_CONTENT_RE = [
    re.compile(rf"<{tag}[^>]*>.*?</{tag}>", re.DOTALL) for tag in _DROP_WITH_CONTENT
]
_COMPONENT_CLOSE_RE = re.compile(r"</component>")
_COMPONENT_OPEN_RE = {
    component_id: re.compile(rf"<component id=['\"]{re.escape(component_id)}['\"][^>]*>")
    for component_id in _DROP_COMPONENT_IDS
}
_COMPONENT_BLOCK_RE = [
    re.compile(
        rf"<component id=['\"]{re.escape(component_id)}['\"][^>]*>.*?</component>",
        re.DOTALL,
    )
    for component_id in _DROP_COMPONENT_IDS
]
_POP_STREAM_FOR_ID_RE = {
    # A popStream closes a specific pushStream if it is either bare (no id
    # attribute - the common real form, confirmed live 2026-09-07) or its
    # id explicitly matches. A popStream naming some *other* id (e.g. the
    # close belonging to the "room" stream itself) must never be treated
    # as closing this one, even though it shares the same generic tag
    # name - confirmed as a real, observed bug 2026-09-07: an unrelated
    # `<popStream id="room"/>` sitting in the same buffer as a still-open
    # `inv` pushStream (both awaiting release together) got miscounted as
    # closing "inv", releasing an inventory listing that was not dropped.
    stream_id: re.compile(rf"<popStream(?:\s*/>|\s+id=['\"]{stream_id}['\"][^>]*/>)")
    for stream_id in _DROP_STREAM_IDS
}
_STREAM_BLOCK_RE = [
    re.compile(
        rf"<pushStream id=['\"]{stream_id}['\"][^>]*/>.*?{_POP_STREAM_FOR_ID_RE[stream_id].pattern}",
        re.DOTALL,
    )
    for stream_id in _DROP_STREAM_IDS
]
_ANY_TAG_RE = re.compile(r"<[^>]*>")
# Whitespace (spaces/tabs) left stranded on its own line - typically the
# literal gap between two adjacent tags that both got stripped - confirmed
# live, 2026-09-07, showing up as a lone " " line in the display. Folded
# into a true blank line before the blank-line collapse below, so it is
# treated the same as any other blank line rather than surviving as its
# own not-quite-empty line.
_WHITESPACE_ONLY_LINE_RE = re.compile(r"^[ \t]+$", re.MULTILINE)
_BLANK_LINES_RE = re.compile(r"\n{3,}")

_ENTITIES = {
    "&gt;": ">",
    "&lt;": "<",
    "&amp;": "&",
    "&apos;": "'",
    "&quot;": '"',
}


def _normalize_newlines(text: str) -> str:
    """Collapses CRLF to bare LF.

    The real game stream uses CRLF line endings (confirmed live,
    2026-09-07, via a byte-level dump of a captured session), but every
    newline-counting piece of this filter (_BLANK_LINES_RE, the ^/$
    anchors in _WHITESPACE_ONLY_LINE_RE, and the cross-chunk bookkeeping
    in StreamingDisplayFilter) only recognizes a bare "\\n" as a line
    terminator. A run of "\\r\\n\\r\\n\\r\\n..." - which renders as many
    blank lines - never matches any of those bare-"\\n" patterns, since
    each "\\n" has an "\\r" immediately before it rather than another
    "\\n"; every blank-line collapse in this module was silently inert
    against the live stream until this normalization was added. Reading a
    captured log file with the default text-mode universal-newline
    translation in Python masked this during earlier testing, since that
    translation already turns CRLF into LF before this code ever sees
    it - the real GameSocket.read_chunk() decodes raw socket bytes
    directly and does no such translation."""
    return text.replace("\r\n", "\n")


def _strip_tags_and_entities(text: str) -> str:
    for pattern in _STREAM_BLOCK_RE:
        text = pattern.sub("", text)
    for pattern in _TAG_WITH_CONTENT_RE:
        text = pattern.sub("", text)
    for pattern in _COMPONENT_BLOCK_RE:
        text = pattern.sub("", text)
    text = _ANY_TAG_RE.sub("", text)
    for entity, replacement in _ENTITIES.items():
        text = text.replace(entity, replacement)
    return text


def strip_display_noise(text: str) -> str:
    text = _normalize_newlines(text)
    text = _strip_tags_and_entities(text)
    text = _WHITESPACE_ONLY_LINE_RE.sub("", text)
    return _BLANK_LINES_RE.sub("\n\n", text)


_OPEN_TAG_RE = {tag: re.compile(rf"<{tag}(?:\s[^>]*)?>") for tag in _DROP_WITH_CONTENT}
_CLOSE_TAG_RE = {tag: re.compile(rf"</{tag}>") for tag in _DROP_WITH_CONTENT}
_PUSH_STREAM_RE = {
    stream_id: re.compile(rf"<pushStream id=['\"]{stream_id}['\"][^>]*/>")
    for stream_id in _DROP_STREAM_IDS
}


def _first_unclosed_position(open_positions: list[int], close_positions: list[int]) -> int | None:
    """Walks open/close marker positions for one tracked tag or stream id
    in chronological order and returns the buffer position of the
    earliest open marker still unmatched once every close has consumed
    the earliest still-open marker at or before it - or None if all
    opens are matched.

    A close that appears before any open for this tag/stream is ignored
    rather than counted against a push that has not happened yet.
    Needed because a *bare* closing marker (no id, or a generic
    `</tag>`) left over from an earlier, already-finished, unrelated
    occurrence can otherwise sit in the same buffer as a later, still-
    open push and get miscounted as already closing it - confirmed
    live, 2026-09-07: a leftover bare `<popStream/>` positioned before a
    later `<pushStream id="inv"/>` in the same buffer made the naive
    "total opens vs. total closes" count look balanced, releasing that
    inventory listing without dropping it. This does not correlate a
    close back to a *specific* id beyond what the caller already
    filtered for - it only enforces chronological order, which holds
    for the simple, non-interleaved push/pop sequences seen in practice;
    a real streaming XML parser (the future `protocol` package) would
    track this properly."""
    events = sorted([(pos, 0) for pos in open_positions] + [(pos, 1) for pos in close_positions])
    open_stack: list[int] = []
    for pos, kind in events:
        if kind == 0:
            open_stack.append(pos)
        elif open_stack:
            open_stack.pop(0)
    return open_stack[0] if open_stack else None


def _earliest_unclosed_drop_tag(buffer: str) -> int:
    """Index of the earliest still-open DROP_WITH_CONTENT/DROP_STREAM_IDS/
    DROP_COMPONENT_IDS marker in buffer, or len(buffer) if everything so
    far is balanced."""
    earliest = len(buffer)
    for tag in _DROP_WITH_CONTENT:
        opens = [m.start() for m in _OPEN_TAG_RE[tag].finditer(buffer) if not m.group(0).endswith("/>")]
        closes = [m.start() for m in _CLOSE_TAG_RE[tag].finditer(buffer)]
        pos = _first_unclosed_position(opens, closes)
        if pos is not None:
            earliest = min(earliest, pos)
    for stream_id in _DROP_STREAM_IDS:
        opens = [m.start() for m in _PUSH_STREAM_RE[stream_id].finditer(buffer)]
        closes = [m.start() for m in _POP_STREAM_FOR_ID_RE[stream_id].finditer(buffer)]
        pos = _first_unclosed_position(opens, closes)
        if pos is not None:
            earliest = min(earliest, pos)
    for component_id in _DROP_COMPONENT_IDS:
        opens = [m.start() for m in _COMPONENT_OPEN_RE[component_id].finditer(buffer)]
        closes = [m.start() for m in _COMPONENT_CLOSE_RE.finditer(buffer)]
        pos = _first_unclosed_position(opens, closes)
        if pos is not None:
            earliest = min(earliest, pos)
    return earliest


def _hold_back_dangling_tag(buffer: str, cutoff: int) -> int:
    """Reduces cutoff further if the portion about to be released ends
    with a tag that started (a bare "<") but never got its closing ">" -
    *any* tag, not just the drop-worthy ones above. Confirmed live,
    2026-09-07: a `<container ...>` tag (not itself drop-worthy, so
    untracked by the counting above) split across two reads leaked its
    attribute fragments as literal text, since the generic tag-stripping
    regex in strip_display_noise() only matches a tag that is fully
    present."""
    candidate = buffer[:cutoff]
    last_open = candidate.rfind("<")
    if last_open != -1 and ">" not in candidate[last_open:]:
        return last_open
    return cutoff


def _hold_back_dangling_entity(buffer: str, cutoff: int) -> int:
    """Reduces cutoff further if the portion about to be released ends
    with an entity reference that started (a bare "&") but never got its
    closing ";". Confirmed live, 2026-09-07, via byte-by-byte chunking:
    "&gt;" split as "&g" | "t;" left both halves unmatched by the literal
    entity.replace() calls in _strip_tags_and_entities(), so the raw
    "&gt;" leaked through unescaped instead of becoming ">"."""
    candidate = buffer[:cutoff]
    last_amp = candidate.rfind("&")
    if last_amp != -1 and ";" not in candidate[last_amp:]:
        return last_amp
    return cutoff


def _hold_back_trailing_cr(buffer: str, cutoff: int) -> int:
    """Reduces cutoff by one if the portion about to be released ends
    with a bare, unresolved "\\r". After _normalize_newlines() collapses
    every complete "\\r\\n" pair to "\\n", a trailing "\\r" here means its
    paired "\\n" simply has not arrived yet (split across a chunk
    boundary) - holding it back lets the next feed() call complete the
    pair and normalize it correctly, instead of releasing a bare "\\r"
    as a literal character."""
    if buffer[:cutoff].endswith("\r"):
        return cutoff - 1
    return cutoff


_CLOSING_OR_SELF_CLOSING_TAG_RE = re.compile(r"</[^>]*>|<[^>]*/>")


def _hold_back_risky_trailing_line(buffer: str, cutoff: int) -> int:
    """Reduces cutoff further if the not-yet-newline-terminated tail of
    the portion about to be released would reduce to nothing but
    whitespace once tags/entities are stripped from it in isolation.

    Needed because _WHITESPACE_ONLY_LINE_RE matches a whole "line" via
    ^/$ anchors: a still-open line that currently *looks* blank (e.g. a
    leading indent followed by an `<a ...>` link wrapper whose inner
    text - the actual word - has not arrived yet, or even just a lone
    space between two words split across a chunk boundary) is
    indistinguishable, in isolation, from a genuinely blank line.
    Confirmed live, 2026-09-07: byte-by-byte chunking turned "  <a
    ...>Heroism</a>" into a leaked blank line eating the indent before
    "Heroism" arrived, and turned "Please wait" into "Pleasewait" by
    treating the single separating space as its own "blank" chunk.

    Exception: a tail made up *entirely* of complete closing or
    self-closing tags (e.g. the `<popStream/>` that finishes off an
    already-balanced drop-block spanning back before the last newline)
    is never risky, even if it strips to nothing - such a tag cannot
    gain more inline content, and holding it back anyway was itself a
    confirmed bug, 2026-09-07: doing so split a `<popStream/>` from its
    matching `<pushStream>` earlier in the same buffer, so
    `_STREAM_BLOCK_RE` never saw both halves together and the whole
    inventory listing leaked instead of being dropped. Any leftover
    character in the tail not covered by such a tag - stray whitespace,
    or a still-open tag - keeps the tail in play for the blank check.

    Only the tail after the last newline is at risk - anything before it
    is already a complete, safely-collapsible line."""
    candidate = buffer[:cutoff]
    if not candidate or candidate.endswith("\n"):
        return cutoff
    tail = candidate[candidate.rfind("\n") + 1 :]
    if _CLOSING_OR_SELF_CLOSING_TAG_RE.sub("", tail) == "":
        return cutoff
    if _strip_tags_and_entities(tail).strip(" \t") == "":
        return cutoff - len(tail)
    return cutoff


class StreamingDisplayFilter:
    """Buffers incoming chunks so a drop-worthy block spanning multiple
    reads (e.g. a large dialogData/pushStream block split across two TCP
    reads) gets held back and dropped correctly, instead of leaking a
    dangling fragment into the display - confirmed as a real, observed
    bug 2026-09-07 (strip_display_noise() alone assumes a complete tag
    arrives within a single call, true most of the time but not always
    for large bursts). Stateful; one instance per connection."""

    def __init__(self):
        self._buffer = ""
        # Newlines already at the end of everything emitted so far -
        # needed because strip_display_noise() only collapses blank-line
        # runs *within* the text of one call, not across the boundary
        # between two separately-filtered chunks. A large dropped block
        # (or a run of near-empty <prompt> pushes) spanning several reads left
        # a visible cascade of blank lines and repeated "> " prompts,
        # each individually "collapsed" but stacking up once appended
        # one after another - confirmed live, 2026-09-07.
        self._trailing_newlines = 0

    def feed(self, chunk: str) -> str:
        self._buffer += chunk
        # Normalized here (not just inside strip_display_noise) so every
        # cutoff/holdback computation below - all of which reason about
        # bare "\n" - sees the same normalized text the eventually-
        # released "ready" portion will be processed with.
        self._buffer = _normalize_newlines(self._buffer)
        cutoff = _earliest_unclosed_drop_tag(self._buffer)
        cutoff = _hold_back_dangling_tag(self._buffer, cutoff)
        cutoff = _hold_back_dangling_entity(self._buffer, cutoff)
        cutoff = _hold_back_trailing_cr(self._buffer, cutoff)
        cutoff = _hold_back_risky_trailing_line(self._buffer, cutoff)
        ready, self._buffer = self._buffer[:cutoff], self._buffer[cutoff:]
        return self._collapse_across_chunks(strip_display_noise(ready))

    def flush(self) -> str:
        """Call when the connection ends - processes anything still held
        back rather than silently dropping a truly incomplete trailing
        block."""
        remaining, self._buffer = self._buffer, ""
        return self._collapse_across_chunks(strip_display_noise(remaining))

    def _collapse_across_chunks(self, text: str) -> str:
        if not text:
            return text

        leading_count = len(text) - len(text.lstrip("\n"))
        remainder = text[leading_count:]
        allowed = max(0, 2 - self._trailing_newlines)
        kept_leading = min(leading_count, allowed)

        if not remainder:
            # Entirely newlines - just extending an existing blank run,
            # capped at the amount already allowed.
            self._trailing_newlines += kept_leading
            return "\n" * kept_leading

        result = "\n" * kept_leading + remainder
        self._trailing_newlines = len(result) - len(result.rstrip("\n"))
        return result
