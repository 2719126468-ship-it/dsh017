import unittest

from app.chat_ui import _iter_utf8_text


class ChatStreamDecodingTests(unittest.TestCase):
    def test_utf8_codepoints_survive_arbitrary_byte_boundaries(self):
        expected = "Hello，中文 streaming 😊"
        encoded = expected.encode("utf-8")
        chunks = [encoded[index:index + 1] for index in range(len(encoded))]
        self.assertEqual("".join(_iter_utf8_text(chunks)), expected)

    def test_incomplete_final_utf8_sequence_is_flushed_as_replacement(self):
        self.assertEqual("".join(_iter_utf8_text([b"safe text ", b"\\xe4"])), "safe text �")


if __name__ == "__main__":
    unittest.main()
