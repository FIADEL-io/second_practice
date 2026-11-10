from __future__ import annotations


class CargoError(Exception):
    pass


class ManifestNotFound(CargoError):
    pass


def parse_manifest(text: str) -> dict[str, object]:
    parser = _Parser(text.lstrip("\ufeff"))
    return parser.parse_document()


def package_name(manifest: dict[str, object]) -> str:
    package = manifest.get("package")
    if not isinstance(package, dict):
        return ""
    name = package.get("name")
    if isinstance(name, str):
        return name
    return ""


def workspace_members(manifest: dict[str, object]) -> list[str]:
    workspace = manifest.get("workspace")
    if not isinstance(workspace, dict):
        return []
    members = workspace.get("members")
    if not isinstance(members, list):
        return []
    names: list[str] = []
    for item in members:
        if isinstance(item, str) and "*" not in item:
            names.append(item.strip("/"))
    return names


def direct_dependencies(
    manifest: dict[str, object],
) -> list[tuple[str, str]]:
    dependencies = manifest.get("dependencies")
    if not isinstance(dependencies, dict):
        return []
    found: list[tuple[str, str]] = []
    for key, value in dependencies.items():
        if not isinstance(key, str):
            continue
        found.append(_dependency(key, value))
    found.sort()
    return found


def _dependency(key: str, value: object) -> tuple[str, str]:
    if isinstance(value, str):
        return key, value
    if not isinstance(value, dict):
        return key, ""
    name = value.get("package")
    if not isinstance(name, str) or name == "":
        name = key
    version = value.get("version")
    if isinstance(version, str):
        return name, version
    return name, ""


class _Parser:

    def __init__(self, text: str) -> None:
        self._text = text
        self._index = 0
        self._length = len(text)

    def parse_document(self) -> dict[str, object]:
        root: dict[str, object] = {}
        current = root
        while self._has_more():
            self._skip()
            if not self._has_more():
                break
            if self._peek() == "[":
                current = self._enter(root, self._table_header())
                continue
            parts, value = self._key_and_value()
            self._assign(current, parts, value)
        return root

    def _table_header(self) -> list[str]:
        self._take("[")
        if self._peek() == "[":
            raise CargoError("массивы таблиц в Cargo.toml не поддерживаются")
        parts = self._key_parts()
        self._skip()
        self._take("]")
        return parts

    def _key_and_value(self) -> tuple[list[str], object]:
        parts = self._key_parts()
        self._skip()
        self._take("=")
        value = self._value()
        return parts, value

    def _key_parts(self) -> list[str]:
        parts: list[str] = []
        while True:
            self._skip()
            if self._peek() in "\"'":
                parts.append(self._string())
            else:
                parts.append(self._bare_key())
            self._skip()
            if self._peek() != ".":
                return parts
            self._index += 1

    def _value(self) -> object:
        self._skip()
        char = self._peek()
        if char in "\"'":
            return self._string()
        if char == "[":
            return self._array()
        if char == "{":
            return self._inline_table()
        if self._starts("true"):
            self._index += len("true")
            return True
        if self._starts("false"):
            self._index += len("false")
            return False
        return self._bare_value()

    def _array(self) -> list[object]:
        self._take("[")
        items: list[object] = []
        while self._has_more():
            self._skip()
            if self._peek() == "]":
                self._index += 1
                return items
            items.append(self._value())
            self._skip()
            if self._peek() == ",":
                self._index += 1
        raise CargoError("не закрыт массив в Cargo.toml")

    def _inline_table(self) -> dict[str, object]:
        self._take("{")
        table: dict[str, object] = {}
        while self._has_more():
            self._skip()
            if self._peek() == "}":
                self._index += 1
                return table
            parts, value = self._key_and_value()
            self._assign(table, parts, value)
            self._skip()
            if self._peek() == ",":
                self._index += 1
        raise CargoError("не закрыта таблица в Cargo.toml")

    def _string(self) -> str:
        if self._text.startswith('"""', self._index):
            return self._multiline('"""')
        if self._text.startswith("'''", self._index):
            return self._multiline("'''")
        quote = self._peek()
        self._index += 1
        chars: list[str] = []
        while self._has_more():
            char = self._text[self._index]
            if char == quote:
                self._index += 1
                return "".join(chars)
            if quote == '"' and char == "\\":
                chars.append(self._escape())
                continue
            chars.append(char)
            self._index += 1
        raise CargoError("незакрытая строка в Cargo.toml")

    def _multiline(self, quote: str) -> str:
        self._index += len(quote)
        end = self._text.find(quote, self._index)
        if end < 0:
            raise CargoError("незакрытая строка в Cargo.toml")
        value = self._text[self._index:end]
        self._index = end + len(quote)
        return value

    def _escape(self) -> str:
        self._index += 1
        char = self._peek()
        self._index += 1
        if char == "n":
            return "\n"
        if char == "t":
            return "\t"
        if char == "\\":
            return "\\"
        if char == '"':
            return '"'
        return char

    def _bare_key(self) -> str:
        start = self._index
        while self._has_more() and _is_key_char(self._peek()):
            self._index += 1
        if start == self._index:
            raise CargoError("ожидался ключ в Cargo.toml")
        return self._text[start:self._index]

    def _bare_value(self) -> str:
        start = self._index
        while self._has_more() and self._peek() not in " \t\r\n,]}#":
            self._index += 1
        if start == self._index:
            raise CargoError("ожидалось значение в Cargo.toml")
        return self._text[start:self._index]

    def _enter(
        self,
        root: dict[str, object],
        parts: list[str],
    ) -> dict[str, object]:
        current = root
        for part in parts:
            current = _child_table(current, part)
        return current

    def _assign(
        self,
        table: dict[str, object],
        parts: list[str],
        value: object,
    ) -> None:
        current = table
        for part in parts[:-1]:
            current = _child_table(current, part)
        current[parts[-1]] = value

    def _skip(self) -> None:
        while self._has_more():
            char = self._peek()
            if char in " \t\r\n":
                self._index += 1
                continue
            if char != "#":
                return
            while self._has_more() and self._peek() != "\n":
                self._index += 1

    def _starts(self, word: str) -> bool:
        if not self._text.startswith(word, self._index):
            return False
        after = self._index + len(word)
        if after >= self._length:
            return True
        return not _is_key_char(self._text[after])

    def _take(self, token: str) -> None:
        if self._peek() != token:
            raise CargoError(f"в Cargo.toml ожидался символ {token}")
        self._index += 1

    def _peek(self) -> str:
        if not self._has_more():
            return ""
        return self._text[self._index]

    def _has_more(self) -> bool:
        return self._index < self._length


def _child_table(table: dict[str, object], key: str) -> dict[str, object]:
    child = table.get(key)
    if isinstance(child, dict):
        return child
    created: dict[str, object] = {}
    table[key] = created
    return created


def _is_key_char(char: str) -> bool:
    return char.isalnum() or char in "-_"
