"""Unit tests for chunk_js in tools/embeddings.py."""

from __future__ import annotations

from tools.embeddings import chunk_js


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def write(tmp_path, name, src):
    p = tmp_path / name
    p.write_text(src, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# basic declarations
# ---------------------------------------------------------------------------


class TestChunkJsBasic:
    def test_named_function(self, tmp_path):
        f = write(tmp_path, "a.js", "function hello() {\n  return 1;\n}\n")
        keys = [k for k, _ in chunk_js(f)]
        assert "hello" in keys

    def test_arrow_const(self, tmp_path):
        f = write(tmp_path, "a.js", "const greet = () => 'hi';\n")
        keys = [k for k, _ in chunk_js(f)]
        assert "greet" in keys

    def test_class_declaration(self, tmp_path):
        f = write(tmp_path, "a.ts", "class Animal {\n  speak() {}\n}\n")
        keys = [k for k, _ in chunk_js(f)]
        assert "Animal" in keys

    def test_async_function(self, tmp_path):
        f = write(
            tmp_path, "a.ts", "async function fetchData() {\n  return await api();\n}\n"
        )
        keys = [k for k, _ in chunk_js(f)]
        assert "fetchData" in keys

    def test_exported_function(self, tmp_path):
        f = write(tmp_path, "a.ts", "export function util() {}\n")
        keys = [k for k, _ in chunk_js(f)]
        assert "util" in keys

    def test_export_default_function(self, tmp_path):
        f = write(tmp_path, "a.js", "export default function() {\n  return 42;\n}\n")
        keys = [k for k, _ in chunk_js(f)]
        assert "default" in keys

    def test_typescript_interface(self, tmp_path):
        f = write(tmp_path, "a.ts", "interface User {\n  name: string;\n}\n")
        keys = [k for k, _ in chunk_js(f)]
        assert "User" in keys

    def test_typescript_type_alias(self, tmp_path):
        f = write(tmp_path, "a.ts", "type ID = string | number;\n")
        keys = [k for k, _ in chunk_js(f)]
        assert "ID" in keys

    def test_enum(self, tmp_path):
        f = write(tmp_path, "a.ts", "enum Direction {\n  Up,\n  Down,\n}\n")
        keys = [k for k, _ in chunk_js(f)]
        assert "Direction" in keys

    def test_let_and_var(self, tmp_path):
        src = "let handler = function() {};\nvar legacy = () => {};\n"
        f = write(tmp_path, "a.js", src)
        keys = [k for k, _ in chunk_js(f)]
        assert "handler" in keys
        assert "legacy" in keys


# ---------------------------------------------------------------------------
# body content
# ---------------------------------------------------------------------------


class TestChunkJsBody:
    def test_body_contains_source(self, tmp_path):
        src = "function add(a, b) {\n  return a + b;\n}\n"
        f = write(tmp_path, "a.js", src)
        chunks = dict(chunk_js(f))
        assert "return a + b" in chunks["add"]

    def test_multiple_decls_each_get_own_chunk(self, tmp_path):
        src = (
            "function foo() { return 1; }\n"
            "function bar() { return 2; }\n"
            "function baz() { return 3; }\n"
        )
        f = write(tmp_path, "a.js", src)
        keys = [k for k, _ in chunk_js(f)]
        assert "foo" in keys
        assert "bar" in keys
        assert "baz" in keys

    def test_each_chunk_body_is_scoped(self, tmp_path):
        src = "function foo() { return 1; }\nfunction bar() { return 2; }\n"
        f = write(tmp_path, "a.js", src)
        chunks = dict(chunk_js(f))
        assert "return 1" in chunks["foo"]
        assert "return 2" in chunks["bar"]
        assert "return 2" not in chunks["foo"]


# ---------------------------------------------------------------------------
# edge cases
# ---------------------------------------------------------------------------


class TestChunkJsEdgeCases:
    def test_empty_file(self, tmp_path):
        f = write(tmp_path, "a.js", "")
        assert chunk_js(f) == []

    def test_whitespace_only_file(self, tmp_path):
        f = write(tmp_path, "a.js", "   \n\n  ")
        assert chunk_js(f) == []

    def test_no_declarations_returns_file_chunk(self, tmp_path):
        src = "// just a comment\nconsole.log('hello');\n"
        f = write(tmp_path, "a.js", src)
        chunks = chunk_js(f)
        assert len(chunks) == 1
        assert chunks[0][0] == "__file__"
        assert "console.log" in chunks[0][1]

    def test_duplicate_names_are_deduped(self, tmp_path):
        src = "function handle() { return 1; }\nfunction handle() { return 2; }\n"
        f = write(tmp_path, "a.js", src)
        keys = [k for k, _ in chunk_js(f)]
        assert len(keys) == len(set(keys)), "duplicate keys produced"
        assert "handle" in keys
        assert "handle_2" in keys

    def test_tsx_extension(self, tmp_path):
        src = "export const Button = () => <button>Click</button>;\n"
        f = write(tmp_path, "comp.tsx", src)
        keys = [k for k, _ in chunk_js(f)]
        assert "Button" in keys

    def test_jsx_extension(self, tmp_path):
        src = "function App() { return <div/>; }\n"
        f = write(tmp_path, "app.jsx", src)
        keys = [k for k, _ in chunk_js(f)]
        assert "App" in keys
