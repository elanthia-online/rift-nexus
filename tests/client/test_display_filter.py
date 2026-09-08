from rift.client.display_filter import StreamingDisplayFilter, strip_display_noise


def test_drops_dialog_data_entirely():
    text = "<dialogData id='minivitals'><progressBar id='stamina' value='0'/></dialogData>after"
    assert strip_display_noise(text) == "after"


def test_drops_spell_left_right_status_fields_entirely():
    # Regression: these are current-state notification fields (prepared
    # spell, hand contents), not narrative text - concatenating their bare
    # values ("None", "Empty") reads as garbage. Confirmed via two real
    # session captures, 2026-09-07.
    text = "<spell>None</spell><left>Empty</left><right>Empty</right>after"
    assert strip_display_noise(text) == "after"

    text = '<right exist="99575774" noun="staff">rune staff</right>after'
    assert strip_display_noise(text) == "after"


def test_drops_inv_stream_block_entirely():
    # Temporary suppression: the worn-items listing gets rebroadcast in
    # full on unrelated commands (e.g. "ready weapon") - confirmed via a
    # real session, 2026-09-07, showing it 4 times in a few minutes.
    text = (
        "before"
        "<clearStream id='inv' ifClosed=''/><pushStream id='inv'/>"
        "Your worn items are:\n  a leather cap\n"
        "<popStream/>"
        "after"
    )
    assert strip_display_noise(text) == "beforeafter"


def test_keeps_other_stream_ids_unlike_inv():
    text = "<pushStream id='bounty'/>You have a bounty task.<popStream id='bounty'/>"
    assert strip_display_noise(text) == "You have a bounty task."


def test_drops_open_dialog_entirely():
    text = "<openDialog type='dynamic' id='combat'><dialogData id='combat'/></openDialog>after"
    assert strip_display_noise(text) == "after"


def test_drops_comp_def_entirely():
    text = "<compDef id='room desc'>A quiet clearing.</compDef>after"
    assert strip_display_noise(text) == "after"


def test_drops_empty_comp_def():
    text = "<compDef id='room players'></compDef>after"
    assert strip_display_noise(text) == "after"


def test_unwraps_anchor_and_command_link_tags_keeping_inner_text():
    text = 'You see a <a exist="123" noun="statue">grey marble statue</a>.'
    assert strip_display_noise(text) == "You see a grey marble statue."
    text = "Use <d>WHO HELP</d> for more options."
    assert strip_display_noise(text) == "Use WHO HELP for more options."


def test_keeps_component_inner_text_for_ids_not_on_the_drop_list():
    # component (not compDef) is kept in general - only the specific ids
    # in _DROP_COMPONENT_IDS get dropped (see the test below).
    text = "<component id='something else'>Also here: <a exist=\"1\" noun=\"Bob\">Bob</a></component>"
    assert strip_display_noise(text) == "Also here: Bob"


def test_drops_room_objs_and_room_players_components_entirely():
    # Regression, confirmed live 2026-09-07: an earlier assumption that
    # <component id="room objs"/"room players"> carried unique,
    # non-duplicated room-population data was wrong. A real session
    # showed it resent standalone (after a prompt push, after a combat
    # dialogData update, after typing "exit") purely because an NPC in
    # the room moved, with no accompanying room name/description - the
    # genuine full room display (on room entry or "look") never uses
    # this wrapper at all, sending the same information as plain
    # narrative text framed by <style .../> markers instead.
    text = "before<component id='room objs'>You also see a cat.</component>after"
    assert strip_display_noise(text) == "beforeafter"
    text = "before<component id='room players'>Also here: Bob</component>after"
    assert strip_display_noise(text) == "beforeafter"


def test_strips_self_closing_noise_tags():
    text = '<mode id="GAME"/>hello<indicator id="IconKNEELING" visible="n"/>'
    assert strip_display_noise(text) == "hello"


def test_unescapes_html_entities():
    assert strip_display_noise("Bigger &gt; smaller") == "Bigger > smaller"
    assert strip_display_noise("Tom &amp; Jerry") == "Tom & Jerry"


def test_drops_prompt_tag_and_content_entirely():
    # Regression, confirmed live 2026-09-07: <prompt time="..."> is the
    # "> " input-ready marker sent by the game, resent on its own periodic
    # timer rather than once per player action - a burst of these produced
    # runs of near-empty "> " lines. Most front ends squelch this as
    # background signal rather than transcript text (per the user,
    # 2026-09-07); this client has no command-echo convention that would
    # need it displayed either, since it uses a separate input box.
    text = "before<prompt time='1'>&gt;</prompt>after"
    assert strip_display_noise(text) == "beforeafter"


def test_collapses_excess_blank_lines():
    text = "line one\n\n\n\n\nline two"
    assert strip_display_noise(text) == "line one\n\nline two"


def test_folds_whitespace_only_lines_into_blank_lines():
    # Regression: a lone space/tab left on its own line (the literal gap
    # between two now-stripped tags) survived as a visible not-quite-empty
    # line - confirmed live, 2026-09-07.
    text = "line one\n \nline two"
    assert strip_display_noise(text) == "line one\n\nline two"

    text = "line one\n\t \nline two"
    assert strip_display_noise(text) == "line one\n\nline two"


def test_preserves_plain_narrative_text_unchanged():
    text = "Obvious paths: north, south, west"
    assert strip_display_noise(text) == text


def test_streaming_filter_holds_back_dialog_data_split_across_chunks():
    # Regression, confirmed live 2026-09-07: a dialogData block spanning
    # two separate TCP reads leaked a well-formed inner tag as literal
    # text, because each chunk was filtered independently and neither
    # half contained both the opening and closing dialogData tags.
    filt = StreamingDisplayFilter()
    chunk_a = "before<dialogData id='combat'><upDownEditBox min='-60' />"
    chunk_b = "<cmdButton id='cmdQuickstrike' tooltip='Go' /></dialogData>after"

    out_a = filt.feed(chunk_a)
    assert out_a == "before"  # held back everything from <dialogData onward

    out_b = filt.feed(chunk_b)
    assert out_b == "after"  # now-complete block dropped, nothing leaked


def test_streaming_filter_passes_through_normal_chunks_immediately():
    filt = StreamingDisplayFilter()
    assert filt.feed("Obvious paths: north, south") == "Obvious paths: north, south"
    assert filt.feed(", west\n") == ", west\n"


def test_streaming_filter_flush_processes_a_truly_incomplete_trailing_block():
    filt = StreamingDisplayFilter()
    out = filt.feed("hello<dialogData id='x'>never closes")
    assert out == "hello"
    # No closing tag ever arrives - flush() does its best via the plain
    # filter, which can only strip the lone opening tag, not "drop with
    # content" a block that never actually closed.
    assert filt.flush() == "never closes"


def test_streaming_filter_collapses_blank_lines_across_chunk_boundaries():
    # Regression, confirmed live 2026-09-07: strip_display_noise() only
    # collapses blank-line runs *within* the text of one call. A large dropped
    # block (or a run of near-empty <prompt> pushes) split across several
    # reads left each chunk "locally collapsed" to <=2 newlines, but they
    # stacked up once appended one after another in the display.
    filt = StreamingDisplayFilter()
    first = filt.feed("real text\n\n<dialogData id='a'></dialogData>\n\n")
    second = filt.feed("<dialogData id='b'></dialogData>\n\n")
    third = filt.feed("more text")

    combined = first + second + third
    assert "\n\n\n" not in combined
    assert combined == "real text\n\nmore text"


def test_streaming_filter_holds_back_dangling_generic_tag_split_across_chunks():
    # Regression, confirmed live 2026-09-07: a tag that is not one of the
    # tracked drop-with-content tags (e.g. <container>) split mid-attribute
    # across two reads leaked its attribute fragment as literal text,
    # because the generic tag-stripping regex in strip_display_noise()
    # only matches a tag that is fully present within a single call.
    filt = StreamingDisplayFilter()
    chunk_a = "before<container id='stow' targe"
    chunk_b = "t='#123' resident='true'/>after"

    assert filt.feed(chunk_a) == "before"
    assert filt.feed(chunk_b) == "after"


def test_streaming_filter_holds_back_lone_space_split_across_chunks():
    # Regression, confirmed live 2026-09-07 via byte-by-byte chunking: a
    # single space between two words, released alone because it happened
    # to land at a chunk boundary, looked like a whole whitespace-only
    # line in isolation and was wrongly deleted - turning "Please wait"
    # into "Pleasewait".
    filt = StreamingDisplayFilter()
    out = filt.feed("Please") + filt.feed(" ") + filt.feed("wait")
    assert out == "Please wait"


def test_streaming_filter_holds_back_leading_indent_before_split_link_tag():
    # Regression, confirmed live 2026-09-07: a leading indent released
    # together with a fully-formed <a ...> opening tag (its closing </a>
    # and inner text not yet arrived) stripped to a false blank line,
    # eating the indent before the tag inner text ("Heroism") arrived in
    # a later chunk.
    filt = StreamingDisplayFilter()
    chunk_a = "  <a exist=\"1\" noun=\"215\">"
    chunk_b = "Heroism</a>"

    assert filt.feed(chunk_a) == ""
    assert filt.feed(chunk_b) == "  Heroism"


def test_streaming_filter_does_not_hold_back_closing_tag_of_resolved_block():
    # Regression, confirmed live 2026-09-07: an attempted fix for the
    # leading-indent case above over-applied and also held back a lone
    # <popStream/> that was itself the closing half of an already-open
    # pushStream earlier in the same buffer - splitting it out meant
    # _STREAM_BLOCK_RE never saw both tags together, so the whole
    # (supposed to be dropped) inventory listing leaked instead.
    filt = StreamingDisplayFilter()
    chunk_a = "before<pushStream id='inv'/>Your worn items are:\n  a cap\n"
    chunk_b = "<popStream/>after"

    out_a = filt.feed(chunk_a)
    out_b = filt.feed(chunk_b)
    assert out_a + out_b == "beforeafter"


def test_streaming_filter_recombines_entity_split_across_chunks():
    # Regression, confirmed live 2026-09-07 via byte-by-byte chunking:
    # "&gt;" split as "&g" | "t;" left both halves unmatched by the
    # literal entity replace(), so the raw "&gt;" leaked through instead
    # of becoming ">".
    filt = StreamingDisplayFilter()
    out = filt.feed("before&g") + filt.feed("t;after")
    assert out == "before>after"


def test_pop_stream_with_different_id_does_not_close_unrelated_stream():
    # Regression, confirmed live 2026-09-07: an unrelated `<popStream
    # id="room"/>` sitting in the buffer alongside a still-open `inv`
    # pushStream (both awaiting release together because of an earlier
    # held-back block) was miscounted as closing "inv", since the pop
    # count did not check which stream id it actually named.
    filt = StreamingDisplayFilter()
    chunk_a = "<pushStream id='room'/>room text<popStream id='room'/>"
    chunk_b = "<pushStream id='inv'/>Your worn items are:\n  a cap\n<popStream/>after"

    out_a = filt.feed(chunk_a)
    out_b = filt.feed(chunk_b)
    assert out_a + out_b == "room textafter"


def test_earlier_unrelated_bare_pop_does_not_falsely_close_a_later_push():
    # Regression, confirmed live 2026-09-07 via randomized chunk-boundary
    # fuzzing of a real session capture: a bare `<popStream/>` left over
    # from an earlier, already-finished, unrelated stream sat in the
    # buffer *before* a later `<pushStream id="inv"/>`. The old counting
    # (total opens vs. total closes, ignoring order) treated that
    # leftover close as already matching the later push, releasing its
    # un-dropped inventory listing.
    filt = StreamingDisplayFilter()
    chunk_a = "before<pushStream id='other'/>other text<popStream/>"
    chunk_b = "<pushStream id='inv'/>Your worn items are:\n  a cap\n<popStream/>after"

    out_a = filt.feed(chunk_a)
    out_b = filt.feed(chunk_b)
    assert out_a + out_b == "beforeother textafter"


def test_collapses_blank_lines_made_of_crlf_not_bare_lf():
    # Regression, confirmed live 2026-09-07: the real game stream uses
    # CRLF line endings, but this was masked in earlier manual testing
    # because the default text-mode file reading in Python silently
    # translates CRLF to bare LF on read. The live GameSocket decodes
    # raw socket bytes directly and does no such translation, so a run
    # of "\r\n\r\n\r\n..." (many blank lines) reached this filter intact -
    # and _BLANK_LINES_RE (which only matches 3+ consecutive bare "\n")
    # never matched it, since each "\n" has an "\r" immediately before
    # it rather than another "\n".
    text = "line one\r\n\r\n\r\n\r\n\r\n\r\nline two"
    assert strip_display_noise(text) == "line one\n\nline two"


def test_streaming_filter_holds_back_crlf_split_across_chunks():
    # Regression, confirmed live 2026-09-07: a CRLF pair split right
    # between the "\r" and the "\n" across a chunk boundary must not
    # release the bare "\r" as a literal character - it needs to be held
    # back until the "\n" arrives so normalization can still collapse it.
    filt = StreamingDisplayFilter()
    out = filt.feed("line one\r") + filt.feed("\nline two")
    assert out == "line one\nline two"


def test_streaming_filter_keeps_real_content_between_blank_runs():
    # The collapsing must never eat real content - only redundant leading
    # blank lines once the cap is already reached.
    filt = StreamingDisplayFilter()
    first = filt.feed("line one\n\n")
    second = filt.feed("line two\n\n")
    third = filt.feed("line three")

    combined = first + second + third
    assert combined.count("line") == 3
    assert "\n\n\n" not in combined
