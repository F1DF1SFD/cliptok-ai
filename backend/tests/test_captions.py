from app.schemas import CaptionStyle, Transcript, TranscriptSegment, Word
from app.services.captions import caption_events, caption_runs, group_lines, hex_to_rgba, transcript_words


def make_transcript(words: list[tuple[float, float, str]]) -> Transcript:
    payload = [Word(start=start, end=end, word=text) for start, end, text in words]
    return Transcript(
        language="en",
        text=" ".join(text for _, _, text in words),
        words=payload,
        segments=[TranscriptSegment(id=0, start=0, end=words[-1][1], text="segment", words=payload)],
        duration=words[-1][1],
    )


def test_group_lines_splits_on_word_limit_and_pauses():
    style = CaptionStyle(words_per_line=3)
    words = transcript_words(
        make_transcript(
            [
                (0.0, 0.3, "one"),
                (0.3, 0.6, "two"),
                (0.6, 0.9, "three"),
                (0.95, 1.2, "four"),
                (2.4, 2.7, "after-pause"),
            ]
        )
    )
    lines = group_lines(words, style)
    assert [len(line) for line in lines] == [3, 1, 1]
    assert lines[1][0]["word"] == "four"
    assert lines[2][0]["word"] == "after-pause"


def test_caption_runs_emit_one_run_per_word():
    transcript = make_transcript(
        [(0.0, 0.3, "this"), (0.3, 0.6, "is"), (0.6, 1.0, "insane")]
    )
    style = CaptionStyle(words_per_line=4, uppercase=True)
    runs = caption_runs(transcript, style)
    assert len(runs) == 3
    assert runs[0].active == 0 and runs[1].active == 1
    assert runs[0].words == ["THIS", "IS", "INSANE"]
    assert runs[0].end == runs[1].start


def test_caption_events_match_display_text():
    transcript = make_transcript([(0.0, 0.4, "clip"), (0.4, 0.8, "it")])
    events = caption_events(transcript, CaptionStyle(uppercase=True))
    assert events[0]["text"] == "CLIP IT"
    assert events[0]["words"][1]["word"] == "it"


def test_hex_to_rgba_handles_short_and_invalid_values():
    assert hex_to_rgba("#FFE600") == (255, 230, 0, 255)
    assert hex_to_rgba("#0f8") == (0, 255, 136, 255)
    assert hex_to_rgba("nope") == (255, 255, 255, 255)


def test_transcript_words_merges_split_contractions():
    transcript = make_transcript(
        [(0.0, 0.2, "Y"), (0.2, 0.4, "'ALL"), (0.4, 0.7, "KNOW")]
    )
    words = transcript_words(transcript)
    assert [word["word"] for word in words] == ["Y'ALL", "KNOW"]
    assert words[0]["end"] == 0.4


def test_transcript_words_enforces_minimum_duration():
    transcript = make_transcript([(0.0, 0.0, "zero"), (0.5, 0.6, "next")])
    words = transcript_words(transcript)
    assert words[0]["end"] > words[0]["start"]
    assert words[1]["start"] >= words[0]["end"]


def test_transcript_words_falls_back_to_segments():
    words = [Word(start=0.1, end=0.4, word="hello")]
    transcript = Transcript(
        language="en",
        text="hello",
        segments=[TranscriptSegment(id=0, start=0.1, end=0.4, text="hello", words=words)],
        duration=0.4,
    )
    assert transcript_words(transcript) == [{"start": 0.1, "end": 0.4, "word": "hello"}]
