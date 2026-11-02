import asyncio
import unittest
from io import BytesIO

from fastapi import HTTPException, UploadFile
from PIL import Image

from guardrails import (
    MAX_INPUT_CHARS,
    MAX_OUTPUT_CHARS,
    read_guarded_upload,
    validate_image_bytes,
    validate_text_input,
    validate_text_output,
)
from pipeline import MAX_RETRIEVED_TEXT_CHARS, _limit_retrieval_results


class TextGuardrailTests(unittest.TestCase):
    def test_input_is_trimmed(self):
        self.assertEqual(validate_text_input("  What is in the document?  "), "What is in the document?")

    def test_input_rejects_empty_and_oversized_values(self):
        with self.assertRaises(HTTPException) as empty_error:
            validate_text_input(" \n\t")
        self.assertEqual(empty_error.exception.status_code, 422)

        with self.assertRaises(HTTPException) as oversized_error:
            validate_text_input("x" * (MAX_INPUT_CHARS + 1))
        self.assertEqual(oversized_error.exception.status_code, 413)

    def test_input_rejects_unsupported_control_characters(self):
        for value in ("hello\x00world", "hello\x85world"):
            with self.subTest(value=value):
                with self.assertRaises(HTTPException) as error:
                    validate_text_input(value)
                self.assertEqual(error.exception.status_code, 422)

    def test_output_removes_control_characters_and_rejects_invalid_output(self):
        self.assertEqual(validate_text_output("answer\x00\x85\ntext"), "answer\ntext")
        for invalid in ("  ", None, 42):
            with self.subTest(invalid=invalid):
                with self.assertRaises(HTTPException) as error:
                    validate_text_output(invalid)
                self.assertEqual(error.exception.status_code, 502)

    def test_retrieved_document_text_is_bounded(self):
        result = _limit_retrieval_results([{"content": "x" * 10_000}], 1)[0]
        self.assertEqual(len(result["content"]), MAX_RETRIEVED_TEXT_CHARS)
        self.assertTrue(result["content"].endswith("[Document excerpt truncated]"))

    def test_output_rejects_oversized_response(self):
        with self.assertRaises(HTTPException) as error:
            validate_text_output("x" * (MAX_OUTPUT_CHARS + 1))
        self.assertEqual(error.exception.status_code, 502)


class UploadGuardrailTests(unittest.TestCase):
    def test_upload_size_is_bounded(self):
        async def read_file():
            upload = UploadFile(file=BytesIO(b"12345"), filename="sample.txt")
            return await read_guarded_upload(upload, 4, "Test file")

        with self.assertRaises(HTTPException) as error:
            asyncio.run(read_file())
        self.assertEqual(error.exception.status_code, 413)

    def test_image_validation_checks_actual_image_data(self):
        image_bytes = BytesIO()
        Image.new("RGB", (2, 2)).save(image_bytes, format="PNG")
        validate_image_bytes(image_bytes.getvalue())

        with self.assertRaises(HTTPException) as error:
            validate_image_bytes(b"not an image")
        self.assertEqual(error.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
