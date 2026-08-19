from .docx_parser import docx_to_markdown
from .pdf_parser import pdf_to_markdown
from .xlsx_parser import xlsx_to_markdown
from .text_parser import text_to_markdown

SUPPORTED_EXTENSIONS = {
    ".docx": docx_to_markdown,
    ".pdf": pdf_to_markdown,
    ".xlsx": xlsx_to_markdown,
    ".txt": text_to_markdown,
    ".md": text_to_markdown,
}

__all__ = [
    "docx_to_markdown",
    "pdf_to_markdown",
    "xlsx_to_markdown",
    "text_to_markdown",
    "SUPPORTED_EXTENSIONS",
]
