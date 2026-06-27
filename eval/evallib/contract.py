"""Reexporta o contrato de runtime do Professor a partir do pacote da Fatia A
(`fine-tune/ftlib`). Fonte única de verdade: a régua mede exatamente o que o
runtime produz. O diretório `fine-tune` tem hífen (não é importável como
pacote), então o adicionamos ao sys.path e importamos o pacote `ftlib`."""
import os
import sys

_FT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "fine-tune"))
if _FT not in sys.path:
    sys.path.insert(0, _FT)

from ftlib.schema import is_valid_hint  # noqa: E402
from ftlib.format_chatml import TUTOR_SYSTEM  # noqa: E402
from ftlib.smoke_eval import extract_json  # noqa: E402

__all__ = ["is_valid_hint", "TUTOR_SYSTEM", "extract_json"]
