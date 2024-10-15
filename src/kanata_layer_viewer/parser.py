import pyparsing as pp
from pathlib import Path


class KanataConfigParser:
    remove_comments = (";;" + pp.restOfLine).suppress()

    @classmethod
    def parse(cls, path: Path):
        srckeys = []
        aliases = {}
        layers = {}

        for section in cls._read(path):
            match section:
                case ["defalias", *args]:
                    aliases |= dict(zip(args[::2], args[1::2]))
                case ["deflayer", layer_name, *keys]:
                    layers[layer_name] = keys
                case ["defsrc", *keys]:
                    srckeys = keys
                case ["defvar" | "defcfg", *args]:
                    pass
                case _:
                    print("Warning: unknown section", section)

        return {"aliases": aliases, "srckeys": srckeys, "layers": layers}

    @classmethod
    def _read(cls, path: Path):
        source = path.open().read()
        source = cls.remove_comments.transform_string(source)
        section = pp.nested_expr(ignore_expr=None)
        config = pp.ZeroOrMore(section).parse_string(source)
        for section in config:
            match section:
                case ["include", other_path]:
                    other_path = path.resolve().parent / other_path
                    yield from cls._read(other_path)
                case _:
                    yield section
