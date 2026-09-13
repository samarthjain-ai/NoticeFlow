import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from noticeflow.services.document_service import DocumentProcessingError, extract_text


class DocumentServiceTests(unittest.TestCase):
    @staticmethod
    def _make_pdf(text: str) -> bytes:
        content_stream = f"BT /F1 18 Tf 20 100 Td ({text}) Tj ET".encode("ascii")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length " + str(len(content_stream)).encode("ascii") + b" >>\nstream\n" + content_stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]
        pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for index, obj in enumerate(objects, start=1):
            offsets.append(len(pdf))
            pdf.extend(f"{index} 0 obj\n".encode("ascii"))
            pdf.extend(obj)
            pdf.extend(b"\nendobj\n")
        xref_offset = len(pdf)
        pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        pdf.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        pdf.extend(
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
        )
        return bytes(pdf)

    def test_extracts_text_from_a_real_local_pdf(self) -> None:
        with TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "notice.pdf"
            pdf_path.write_bytes(self._make_pdf("Submit abstract by Friday"))

            result = extract_text(pdf_path.name, pdf_path.read_bytes())

        self.assertIn("Submit abstract by Friday", result)

    def test_reports_unreadable_scanned_pdf_without_returning_empty_analysis(self) -> None:
        with self.assertRaisesRegex(DocumentProcessingError, "scanned|read"):
            extract_text("scanned.pdf", b"not a valid pdf")

    def test_extracts_and_cleans_text_file(self) -> None:
        result = extract_text("notice.txt", b"  Deadline: Friday\n\nSubmit the form.  ")

        self.assertEqual(result, "Deadline: Friday\nSubmit the form.")

    def test_rejects_unsupported_files(self) -> None:
        with self.assertRaisesRegex(DocumentProcessingError, "not supported"):
            extract_text("notice.exe", b"not a notice")

    def test_rejects_empty_files(self) -> None:
        with self.assertRaisesRegex(DocumentProcessingError, "empty"):
            extract_text("notice.txt", b"")

    def test_rejects_oversized_files(self) -> None:
        with self.assertRaisesRegex(DocumentProcessingError, "too large"):
            extract_text("notice.txt", b"notice", max_file_size=2)


if __name__ == "__main__":
    unittest.main()