import re
import tempfile
import subprocess

from pathlib import Path
from typing import List, Optional

from pycparser.c_parser import CParser
from pycparser.c_generator import CGenerator

from nxbindgen.c99 import PyGenerator, config

BINARYEN_PATH = Path('/home/nxpub/dev/nxbinaryen/binaryen/')
CPYTHON_PATH = Path('/home/nxpub/dev/nxpython/build/cpython/')
OUTPUT_PATH = Path('/home/nxpub/dev/nxbindgen/build/')


def preprocess(c_path: Path, *, keep_comments: bool = False, cpp_args: Optional[List[str]] = None) -> str:
    lines = []
    run_line = ['cpp', '-nostdinc', '-E', '-P', *(cpp_args or []), str(c_path)] + (['-CC'] if keep_comments else [])
    print(' '.join(run_line))
    for line in map(lambda x: x.strip(), subprocess.Popen(
        run_line, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    ).stdout.read().decode('utf-8').splitlines()):
        lines.append(line)
    return '\n'.join(lines)


def remove_comments(cdef: str) -> str:
    raise NotImplementedError


class PythonConverter:

    def __init__(
        self, *,
        imports: Optional[List[str]] = None,
        includes: Optional[List[str]] = None,
        defines: Optional[dict] = None,
    ) -> None:
        self._ast = None
        self._imports = imports or []
        self._defines = defines or {}
        self._includes = includes or []

    # Specifically for 3.11 version
    RE_BEGIN_MARKER = re.compile(r'/\* BEWARE!(\s+.*){3}?\*/', re.MULTILINE)
    RE_END_MARKER = re.compile(r'#if USE_COMPUTED_GOTOS\s+TARGET_DO_TRACING:', re.MULTILINE)

    def crop(self, source: str) -> str:
        begin_match = self.RE_BEGIN_MARKER.search(source)
        end_match = self.RE_END_MARKER.search(source)
        return source[begin_match.span()[1]:end_match.span()[0]]

    def apply_fixes(self, fp, header_path: Path) -> None:
        for macro_src, macro_dst in {
            # https://github.com/eliben/pycparser/wiki/FAQ#what-do-i-do-about-__attribute__
            '__attribute__(x)': '',
            '__typeof__(x)': '',
            # https://github.com/eliben/pycparser/issues/430, https://github.com/eliben/pycparser/issues/476
            '_Atomic(x)': 'x',
        }.items():
            fp.write(f'#define {macro_src} {macro_dst}'.strip() + '\n')
        for include_name in self._includes:
            fp.write(f'#include "{include_name}"\n')
        for macro_src, macro_dst in self._defines.items():
            fp.write(f'#define {macro_src} {macro_dst}'.strip() + '\n')
        with open(header_path) as h_file:
            lines = self.crop(h_file.read()).splitlines()
            for idx, line in enumerate(lines):
                clean = line.strip()
                if not clean:
                    fp.write('//\n')
                else:
                    # https://github.com/eliben/pycparser/issues/484
                    if clean.endswith(':') and lines[idx + 1].strip() == '}':
                        line = f'{line};'
                    fp.write(line + '\n')
        fp.flush()

    def load_c(
        self, path: Path,
        flags: List[str],
        includes: List[Path],
    ) -> None:
        with tempfile.NamedTemporaryFile('w+', dir=path.parent) as temp_file:
            self.apply_fixes(temp_file, path)
            processed = preprocess(Path(temp_file.name), cpp_args=[
                *map(lambda f: f'-D{f}', flags),
                *map(lambda p: f'-I{p}', includes)
            ])
        # processed = remove_comments(processed)
        self._ast = CParser().parse(processed, filename=str(path))

    REPLACERS = {
        r'(\s{0,})env\.stack\.peek\((.*?)\) = (.*)(\s{0,})': r'\1env.stack.poke(\2, \3)\4'
    }

    def _fix_line(self, line: str) -> Optional[str]:
        # if line.strip():
        for src, dst in self.REPLACERS.items():
            line = re.sub(src, dst, line)
        return line

    def render_py(self, path: Path) -> None:
        generator = PyGenerator(keep_empty_declarations=False, type_hint_declarations=False)
        with open(path, 'w') as py_file:
            if self._imports:
                for imp in self._imports:
                    py_file.write(imp + '\n')
                py_file.write('\n\n')
            started = False
            for line in generator.visit(self._ast, parent=None).splitlines():
                if line.startswith('def op_NOP('):
                    started = True
                if started:
                    if (line := self._fix_line(line)) is not None:
                        py_file.write(line + '\n')

    def render_c(self, path: Path) -> None:
        generator = CGenerator()
        with open(path, 'w') as c_file:
            c_file.write(generator.visit(self._ast))


if __name__ == '__main__':
    bc = PythonConverter(
        imports=[
            # 'from nxbinaryen.capi import *',
            # 'from tests.utils import *',
        ],
        includes=config.INCLUDES,
        defines=config.DEFINES,
    )
    bc.load_c(
        CPYTHON_PATH / 'Python/ceval.c',
        # BINARYEN_PATH / 'test/example/c-api-kitchen-sink.c',
        flags=[
            'Py_BUILD_CORE=1',
        ],
        includes=[
            Path('./fake_libc_include').resolve(),
            # BINARYEN_PATH / 'src',
            CPYTHON_PATH / 'Include',
            CPYTHON_PATH / 'Include/internal',
            CPYTHON_PATH / 'builddir/wasi',
        ]
    )
    # bc.render_c(OUTPUT_PATH / 'test_kitchen_sink.c')
    # bc.render_py(OUTPUT_PATH / 'test_kitchen_sink.py')
    bc.render_c(OUTPUT_PATH / 'generated_cases.c.h')
    bc.render_py(OUTPUT_PATH / 'generated_cases.py')
