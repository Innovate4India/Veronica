"""Tests for Veronica's deterministic UTF-8 byte-level tokenizer."""

import unittest

from app.tokenizer import decode, encode


class ByteTokenizerTests(unittest.TestCase):
    def test_english_text_round_trip(self) -> None:
        text = "Hello, Veronica!"
        self.assertEqual(decode(encode(text)), text)

    def test_hindi_devanagari_text_round_trip(self) -> None:
        text = "नमस्ते, वेरोनिका!"
        self.assertEqual(decode(encode(text)), text)

    def test_hinglish_text_round_trip(self) -> None:
        text = "Namaste Veronica, aap kaise hain?"
        self.assertEqual(decode(encode(text)), text)

    def test_mixed_english_hindi_and_hinglish_round_trip(self) -> None:
        text = "Hello! नमस्ते — aap kaise hain?"
        self.assertEqual(decode(encode(text)), text)

    def test_empty_string_round_trip(self) -> None:
        self.assertEqual(encode(""), [])
        self.assertEqual(decode([]), "")

    def test_whitespace_punctuation_and_symbols_are_preserved(self) -> None:
        text = " \tline one\nline two\r\n!?.,;: @#$%^&*()[]{}<>/\\|+=-_`~"
        self.assertEqual(decode(encode(text)), text)

    def test_emoji_and_other_unicode_round_trip(self) -> None:
        text = "🙂 🌍 café — नमस्ते"
        self.assertEqual(decode(encode(text)), text)

    def test_encoding_is_deterministic(self) -> None:
        text = "Veronica नमस्ते 🙂"
        self.assertEqual(encode(text), encode(text))

    def test_each_token_id_is_the_corresponding_utf8_byte(self) -> None:
        self.assertEqual(encode("\x00A"), [0, 65])
        self.assertEqual(encode("न"), list("न".encode("utf-8")))
        self.assertEqual(decode(range(128)), "".join(map(chr, range(128))))

    def test_encode_rejects_non_string_input(self) -> None:
        for value in (None, b"bytes", 42, ["text"]):
            with self.subTest(value=value), self.assertRaisesRegex(
                TypeError, "text must be a string"
            ):
                encode(value)  # type: ignore[arg-type]

    def test_encode_rejects_surrogates_that_are_not_valid_utf8(self) -> None:
        with self.assertRaises(UnicodeEncodeError):
            encode("\ud800")

    def test_decode_rejects_non_iterable_and_string_inputs(self) -> None:
        for value in (None, 42, "65"):
            with self.subTest(value=value), self.assertRaisesRegex(
                TypeError, "token_ids must be an iterable of integers"
            ):
                decode(value)  # type: ignore[arg-type]

    def test_decode_rejects_negative_and_overflowing_token_ids(self) -> None:
        for token_id in (-1, 256):
            with self.subTest(token_id=token_id), self.assertRaisesRegex(
                ValueError, "between 0 and 255"
            ):
                decode([token_id])

    def test_decode_rejects_boolean_and_non_integer_token_ids(self) -> None:
        for token_id in (True, False, 1.5, "65", None):
            with self.subTest(token_id=token_id), self.assertRaisesRegex(
                TypeError, "must be an integer"
            ):
                decode([token_id])  # type: ignore[list-item]

    def test_decode_rejects_malformed_utf8(self) -> None:
        for token_ids in ([0x80], [0xC3, 0x28], [0xF0, 0x9F, 0x99]):
            with self.subTest(token_ids=token_ids), self.assertRaises(
                UnicodeDecodeError
            ):
                decode(token_ids)


if __name__ == "__main__":
    unittest.main()
