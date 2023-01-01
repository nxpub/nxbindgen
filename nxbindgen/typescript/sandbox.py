import json

from typing import Dict, Any

from nxbindgen.typescript.utils import to_python


def load_ast(path: str):
    with open(path) as json_file:
        return json.loads(json_file.read())


class PyGenerator:

    INDENT = '    '

    def __init__(self, ast: Dict):
        self._ast = ast
        self._code = []
        self._buffer = ''
        self._imports = {}
        self._new_types = []

    def insert_imports(self):
        for idx, (_from, imports) in enumerate(self._imports.items()):
            imports = ', '.join(imports)
            self._code.insert(idx, f'from {_from} import {imports}')

    def insert_types(self):
        for new_type in self._new_types:
            self.insert_line(0, new_type, {'indent': 0})

    def add_import(self, _from: str, import_obj: str):
        self._imports.setdefault(_from, set()).add(import_obj)

    def add_line(self, line: str, ctx: Dict[str, Any], backtrack: int = 0):
        formatted = self.INDENT * ctx['indent'] + line
        if not backtrack:
            self.flush()
            self._code.append(formatted)
        else:
            self._code.insert(len(self._code) - abs(backtrack) - 1, formatted)

    def insert_line(self, line_no: int, line: str, ctx: Dict[str, Any]):
        self._code.insert(line_no, self.INDENT * ctx['indent'] + line)

    def add(self, string: str, ctx: Dict[str, Any]):
        if not self._buffer:
            self._buffer = self.INDENT * ctx['indent']
        self._buffer += string

    def add_empty(self, count: int = 1):
        self.flush()
        for _ in range(count):
            self._code.append('')

    def flush(self):
        if self._buffer:
            self._code.append(self._buffer)
            self._buffer = ''

    def traverse(self):

        def get_name(node, ctx) -> str:
            if node['name']['kind'] == 'Identifier':
                # TODO: Pythonize the name here, preserve the original name somewhere
                return node['name']['escapedText']
            return f'# {node["name"]}'

        # TODO: Get rid of this, use flags, please
        def is_read_only(node):
            for item in node.get('modifiers', []):
                if item['kind'] == 'ReadonlyKeyword':
                    return True
            return False

        # TODO: Get rid of this, use flags, please
        def is_static(node):
            for item in node.get('modifiers', []):
                if item['kind'] == 'StaticKeyword':
                    return True
            return False

        def is_optional(node):
            if token := node.get('questionToken'):
                # TODO: What other options are possible here?
                return token['kind'] == 'QuestionToken'
            return False

        # TODO: Generic, TypeVar -> I'm sure we need them
        def visit_node(node, ctx):
            node_kind = node['kind']
            match node_kind:

                case 'SourceFile':
                    for stmt in node['statements']:
                        visit_node(stmt, ctx)

                # TODO: Use typings.Protocol for InterfaceDeclaration
                # TODO: We don't support abstract modifier yet!
                case 'ClassDeclaration' | 'InterfaceDeclaration':
                    self.add_empty(2)
                    self.add_line('@external', ctx)
                    self.add(f'class {get_name(node, ctx)}', ctx)
                    if heritages := node.get('heritageClauses', []):
                        self.add('(', ctx)
                        for h in heritages:
                            visit_node(h, ctx)
                        self.add(')', ctx)
                    elif node_kind == 'InterfaceDeclaration':
                        # TODO: Check if this is a good idea
                        self.add_import('typings', 'Protocol')
                        self.add('(Protocol)', ctx)
                    self.add(':', ctx)
                    if node['members']:
                        cls_ctx = {**ctx, 'indent': ctx['indent'] + 1, 'methods': {}}
                        for member in node['members']:
                            visit_node(member, cls_ctx)

                        offset = 0
                        for method_name, line_nums in cls_ctx['methods'].items():
                            if len(line_nums) > 1:
                                self.add_import('functools', 'singledispatchmethod')
                                for idx, line_no in enumerate(line_nums):
                                    if idx == 0:
                                        self.insert_line(line_no + offset, '@singledispatchmethod', cls_ctx)
                                    else:
                                        self.insert_line(line_no + offset, f'@{method_name}.register', cls_ctx)
                                    offset += 1
                    else:
                        self.add_line('...', {**ctx, 'indent': ctx['indent'] + 1})

                case 'HeritageClause':
                    # TODO: It looks more complex, verify and revisit
                    for idx, h_type in enumerate(node['types']):
                        if idx > 0:
                            self.add(', ', ctx)
                        visit_node(h_type, ctx)

                case 'ExpressionWithTypeArguments':
                    # TODO: typeArguments processing!
                    self.add(node['expression']['escapedText'], ctx)

                case 'Constructor':
                    self.add_empty()
                    self.add('def __init__(self', ctx)
                    for param in node['parameters']:
                        self.add(', ', ctx)
                        visit_node(param, ctx)
                    self.add('): ...', ctx)

                case 'Parameter':
                    # TODO: dotDotDotToken -> ...args, aka *args?
                    if ctx.get('with_name', True):
                        param_name = to_python(get_name(node, ctx))
                        self.add(f'{param_name}: ', ctx)
                    optional = is_optional(node)
                    if optional:
                        self.add_import('typings', 'Optional')
                        self.add('Optional[', ctx)
                    visit_node(node['type'], ctx)
                    if optional:
                        if ctx.get('with_default', True):
                            self.add('] = None', ctx)
                        else:
                            self.add(']', ctx)

                # TODO: Seems reasonable to separate PropertySignature and avoid @property there
                case 'PropertyDeclaration' | 'PropertySignature':
                    self.add_empty()
                    js_name = get_name(node, ctx)
                    is_aliased = (property_name := to_python(js_name)) != js_name
                    if not is_static(node):
                        self.add_line('@property', ctx)
                        if is_aliased:
                            self.add_line(f'@alias(\'{js_name}\')', ctx)
                        self.add(f'def {property_name}(self) -> ', ctx)
                        visit_node(node['type'], ctx)
                        self.add(':', ctx)
                        self.add_line('raise NotImplementedError', {'indent': ctx['indent'] + 1})
                        if not is_read_only(node):
                            self.add_empty()
                            self.add_line(f'@{property_name}.setter', ctx)
                            if is_aliased:
                                self.add_line(f'@alias(\'{js_name}\')', ctx)
                            self.add(f'def {property_name}(self, value: ', ctx)
                            visit_node(node['type'], ctx)
                            self.add(') -> None: ...', ctx)
                    else:
                        # TODO: We need to make them readonly somehow, class variables are not the best for such stuff
                        self.add(f'{property_name}: ', ctx)
                        visit_node(node['type'], ctx)

                case 'MethodDeclaration' | 'MethodSignature':
                    self.add_empty()
                    js_name = get_name(node, ctx)
                    is_aliased = (method_name := to_python(js_name)) != js_name
                    # TODO: This is a temporary workaround, remove #-check later
                    if not method_name.startswith('#'):
                        # TODO: Should we render _-name for >[0] methods? See docs functools.singledispatch
                        ctx['methods'].setdefault(method_name, []).append(len(self._code))
                        if is_aliased:
                            self.add_line(f'@alias(\'{js_name}\')', ctx)
                        self.add(f'def {method_name}(self', ctx)
                        for param in node['parameters']:
                            self.add(', ', ctx)
                            visit_node(param, ctx)
                        self.add(') -> ', ctx)
                        visit_node(node['type'], ctx)
                        self.add(': ...', ctx)
                        # TODO: Looks like we can mess up w/ ctx w/o cleanups
                        if ctx.pop('is_async', None):
                            # TODO: Can we do it better?
                            self._buffer = self._buffer.replace(f'def {method_name}', f'async def {method_name}')
                    else:
                        self.add_line(method_name, ctx)

                case 'FunctionDeclaration':
                    self.add_empty(2)
                    js_name = get_name(node, ctx)
                    if (function_name := to_python(js_name)) != js_name:
                        self.add_line(f'@alias(\'{js_name}\')', ctx)
                    # TODO: We also have "typeParameters" to process, have no idea how
                    self.add(f'def {function_name}(', ctx)
                    for idx, param in enumerate(node['parameters']):
                        if idx > 0:
                            self.add(', ', ctx)
                        visit_node(param, ctx)
                    self.add(f') -> ', ctx)
                    visit_node(node['type'], ctx)
                    self.add(': ...', ctx)

                case 'TypeAliasDeclaration':
                    self.add_empty(2)
                    type_name = get_name(node, ctx)
                    self.add(f'{type_name} = ', ctx)
                    visit_node(node['type'], ctx)

                case 'ParenthesizedType':
                    # TODO: Looks like just a proxy, verify/revisit
                    visit_node(node['type'], ctx)

                case 'FunctionType':
                    self.add_import('typings', 'Callable')
                    self.add('Callable[', ctx)
                    self.add('[', ctx)
                    for idx, param in enumerate(node['parameters']):
                        if idx > 0:
                            self.add(', ', ctx)
                        visit_node(param, {**ctx, 'with_name': False, 'with_default': False})
                    self.add('], ', ctx)
                    visit_node(node['type'], ctx)
                    self.add(']', ctx)

                case 'VoidKeyword':
                    self.add('None', ctx)

                case 'AnyKeyword':
                    # TODO: Raise some flag due to Any appearance?
                    self.add('Any', ctx)

                case 'BooleanKeyword':
                    self.add('bool', ctx)

                case 'TrueKeyword':
                    self.add('True', ctx)

                case 'FalseKeyword':
                    self.add('False', ctx)

                case 'NumberKeyword' | 'BigIntKeyword':
                    self.add('int', ctx)

                case 'StringKeyword':
                    self.add('str', ctx)

                case 'IntersectionType':
                    # TODO: Type1 & Type2, Python doesn't support this yet
                    #  So, we gonna use the first one of the chain (only)
                    visit_node(node['types'][0], ctx)

                case 'IndexedAccessType':
                    # TODO: Implement it somehow
                    self.add('TODO_INDEXED_ACCESS_TYPE', ctx)

                case 'UnionType':
                    # TODO: Drop Union usage later
                    # self.add_import('typings', 'Union')
                    # self.add('Union[', ctx)
                    for idx, item in enumerate(node['types']):
                        if idx > 0:
                            self.add(' | ', ctx)
                        visit_node(item, ctx)
                    # self.add(']', ctx)

                case 'LiteralType':
                    self.add_import('typings', 'Literal')
                    self.add('Literal[', ctx)
                    visit_node(node['literal'], ctx)
                    self.add(']', ctx)

                case 'StringLiteral':
                    self.add(f'\'{node["text"]}\'', ctx)

                case 'FirstLiteralToken':
                    self.add(node['text'], ctx)

                case 'NullKeyword' | 'UndefinedKeyword':
                    # TODO: UndefinedKeyword is not the same, but it may work
                    self.add('None', ctx)

                case 'TypeQuery':
                    self.add_import('typings', 'Type')
                    self.add('Type[', ctx)
                    # TODO: Looks too simple, check other ways
                    self.add(node['exprName']['escapedText'], ctx)
                    self.add(']', ctx)

                case 'TypeLiteral':
                    # TODO: Generate a proper name for the virtual type (use ctx.path!)
                    new_type_name = f'Type_{id(node)}'
                    # Let's do Protocol, TODO: TypedDict or even @dataclass?
                    sub_tree = DtsCodegen(ast={
                        'kind': 'InterfaceDeclaration',
                        'name': {
                            'kind': 'Identifier',
                            'escapedText': new_type_name,
                        },
                        'members': node['members'],
                    })
                    sub_tree.traverse()
                    # TODO: Merge imports, there can be new
                    self._new_types.append(str(sub_tree))
                    self.add(new_type_name, ctx)

                case 'TupleType':
                    self.add_import('typings', 'Tuple')
                    self.add('Tuple[', ctx)
                    for idx, elem in enumerate(node['elements']):
                        if idx > 0:
                            self.add(', ', ctx)
                        visit_node(elem, ctx)
                    self.add(']', ctx)

                case 'NamedTupleMember':
                    # TODO: We can't use names, so we need to generate a new type
                    #  Current solution is a temporary one!
                    visit_node(node['type'], ctx)

                case 'ArrayType':
                    self.add_import('typings', 'List')
                    self.add('List[', ctx)
                    visit_node(node['elementType'], ctx)
                    self.add(']', ctx)

                case 'TypeReference':

                    def _map(t_name: str) -> str:
                        match t_name:
                            case 'Promise':
                                self.add_import('typings', 'Awaitable')
                                ctx['is_async'] = True
                                return 'Awaitable'
                            case 'Map':
                                self.add_import('typings', 'Dict')
                                return 'Dict'
                            case 'IterableIterator':
                                self.add_import('typings', 'Iterable')
                                return 'Iterable'
                            case 'This':
                                self.add_import('typings', 'Self')
                                return 'Self'
                            case _:
                                # TODO: This is just wrong, we need to map!
                                return t_name

                    type_name = node['typeName']['escapedText']
                    self.add(f'{_map(type_name)}', ctx)
                    if node.get('typeArguments'):
                        self.add('[', ctx)
                        for idx, t_arg in enumerate(node['typeArguments']):
                            if idx > 0:
                                self.add(', ', ctx)
                            visit_node(t_arg, ctx)
                        self.add(']', ctx)

                case 'FirstStatement':
                    for vd in node.get('VariableDeclarationList', []):
                        visit_node(vd, ctx)

                case 'VariableDeclaration':
                    # TODO: Verify other potential applications, I don't think it's only global variables
                    self.add_empty(2)
                    # TODO: Resolve type properly
                    global_type = 'Any'
                    self.add(f'{get_name(node, ctx)}: {global_type}', ctx)

                case 'ModuleDeclaration':
                    # I don't think we ever will need this, skip
                    pass

                case _:
                    print('Unsupported node kind:', node['kind'])

        visit_node(self._ast, {'indent': 0})
        self.flush()

    def to_file(self, path: str):
        self.insert_types()
        # TODO: Find a way to separate woma imports from others
        self.add_import('woma.host.bindgen', 'external')
        self.add_import('woma.host.bindgen', 'alias')
        self.insert_imports()
        with open(path, 'w') as py_file:
            py_file.write('\n'.join(self._code))

    def __str__(self):
        return '\n'.join(self._code)


if __name__ == '__main__':
    dts = PyGenerator(load_ast('../samples/workers-types.schema.json'))
    dts.traverse()
    dts.to_file('../samples/workers_types.py')
