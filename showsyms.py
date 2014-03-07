#!/usr/bin/env python
# vim:ts=4 sw=4 expandtab
import sys

from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection
from elftools.elf.descriptions import (
    describe_symbol_type, describe_symbol_bind, describe_symbol_visibility,
    describe_symbol_shndx, describe_reloc_type, describe_dyn_tag,
    )

IGNORE_TYPES=('STT_NOTYPE', 'STT_SECTION', 'STT_FILE')
f = ELFFile(open(sys.argv[1], 'r'))
for sect in f.iter_sections():
    if not isinstance(sect, SymbolTableSection):
        continue
    for sym in sect.iter_symbols():
        if sym['st_info']['type'] in IGNORE_TYPES:
            continue
        """
        print '{} rawtype {} rawbind {} rawvis {}'.format(
            sym.name,
            sym['st_info']['type'],
            sym['st_info']['bind'],
            sym['st_other']['visibility'],
        )
        """
        print '{} {}'.format(
            sym.name,
            describe_symbol_bind(sym['st_info']['bind']),
        )
