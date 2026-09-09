from backend.ingestion.chunker import chunk_python_file


def _first(iter_):
    return next(iter(iter_), None)


def test_extracts_top_level_function():
    src = '''
def add(a, b):
    """Add two numbers."""
    return a + b
'''
    chunks = list(chunk_python_file(
        repo="test/test",
        default_branch="main",
        file_path="foo.py",
        source=src,
    ))
    assert len(chunks) == 1
    c = chunks[0]
    assert c.name == "add"
    assert c.kind == "function"
    assert c.docstring == "Add two numbers."
    assert "return a + b" in c.source


def test_class_emits_class_plus_methods():
    src = '''
class Widget:
    """A widget."""
    def foo(self): pass
    def bar(self): pass
'''
    chunks = list(chunk_python_file(
        repo="test/test",
        default_branch="main",
        file_path="w.py",
        source=src,
    ))
    names = [c.name for c in chunks]
    assert "Widget" in names
    assert "Widget.foo" in names
    assert "Widget.bar" in names


def test_syntax_error_returns_empty():
    src = "def broken(:\n    pass"
    chunks = list(chunk_python_file(
        repo="test/test",
        default_branch="main",
        file_path="broken.py",
        source=src,
    ))
    assert chunks == []
