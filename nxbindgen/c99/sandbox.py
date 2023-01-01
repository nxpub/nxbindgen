import tempfile
import subprocess

from pathlib import Path
from typing import List, Optional

from pycparser.c_parser import CParser
from pycparser.c_generator import CGenerator

from nxbindgen.c99 import PyGenerator

ROOT_PATH = Path(__file__).parent
CPYTHON_PATH = (Path(__file__).parent / '../build/cpython/').resolve()


def preprocess(c_path: Path, *, keep_comments: bool = False, cpp_args: Optional[List[str]] = None) -> str:
    lines = []
    for line in map(lambda x: x.strip(), subprocess.Popen(
        ['cpp', '-nostdinc', '-E', '-P', *(cpp_args or []), str(c_path)] + (['-CC'] if keep_comments else []),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE  # subprocess.DEVNULL
    ).stdout.read().decode('utf-8').splitlines()):
        lines.append(line)
    return '\n'.join(lines)


def remove_comments(cdef: str) -> str:
    raise NotImplementedError


def apply_fixes(fp, header_path: Path) -> None:
    # https://github.com/eliben/pycparser/wiki/FAQ#what-do-i-do-about-__attribute__
    fp.write('#define __attribute__(x)\n')
    fp.write('#define __typeof__(x)\n')
    # https://github.com/eliben/pycparser/issues/430, https://github.com/eliben/pycparser/issues/476
    fp.write('#define _Atomic(x) x\n')
    with open(header_path) as h_file:
        for idx, line in enumerate(lines := h_file.readlines()):
            clean = line.strip()
            if not clean:
                fp.write('//\n')
            else:
                # https://github.com/eliben/pycparser/issues/484
                if clean.endswith(':') and lines[idx + 1].strip() == '}':
                    line = f'{line};'
                fp.write(line)
    fp.flush()


class PythonConverter:

    def __init__(self, *, imports: Optional[List[str]] = None) -> None:
        self._ast = None
        self._imports = imports or []

    def load_c(self, path: Path, flags: List[str], includes: List[Path]) -> None:
        with tempfile.NamedTemporaryFile('w+', dir=ROOT_PATH) as temp_file:
            apply_fixes(temp_file, path)
            processed = preprocess(Path(temp_file.name), cpp_args=[
                *map(lambda f: f'-D{f}', flags),
                *map(lambda p: f'-I{p}', includes)
            ])
        # processed = remove_comments(processed)
        self._ast = CParser().parse(processed, filename=str(path))

    def render_py(self, path: Path) -> None:
        generator = PyGenerator(keep_empty_declarations=True, type_hint_declarations=False)
        with open(path, 'w') as py_file:
            if self._imports:
                for imp in self._imports:
                    py_file.write(imp + '\n')
                py_file.write('\n\n')
            py_file.write(generator.visit(self._ast))

    def render_c(self, path: Path) -> None:
        generator = CGenerator()
        with open(path, 'w') as c_file:
            c_file.write(generator.visit(self._ast))


if __name__ == '__main__':
    bc = PythonConverter(
        imports=[
            'from nxbinaryen.capi import *',
            'from tests.utils import *',
        ]
    )
    bc.load_c(
        # CPYTHON_PATH / 'Python/bytecodes.c',
        Path('/home/nxpub/dev/nxbinaryen/binaryen/test/example/c-api-kitchen-sink.c'),
        flags=[
            'Py_BUILD_CORE=1',
        ],
        includes=[
            ROOT_PATH / 'fake_libc_include',
            Path('/home/nxpub/dev/nxbinaryen/binaryen/src'),
            # CPYTHON_PATH / 'Include',
            # CPYTHON_PATH / 'Include/internal',
            # CPYTHON_PATH / 'builddir/wasi',
        ]
    )
    # bc.render_c('/home/nxpub/dev/nxbuilder/cases_generator/bytecodes.gen.c')
    # bc.render_py('/home/nxpub/dev/nxbuilder/cases_generator/bytecodes.gen.py')
    bc.render_c('/home/nxpub/dev/nxbinaryen/tests/test_kitchen_sink.gen.c')
    bc.render_py('/home/nxpub/dev/nxbinaryen/tests/test_kitchen_sink.gen.py')
