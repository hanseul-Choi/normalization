"""Pure Python Trie for high-throughput multi-keyword matching (`docs/10-api-design.md`)."""

from __future__ import annotations

from collections.abc import Iterable


class TrieNode:
    __slots__ = ("children", "word")

    def __init__(self) -> None:
        self.children: dict[str, TrieNode] = {}
        self.word: str | None = None


class Trie:
    """Trie structure optimized for searching multiple keywords in a single scan."""

    def __init__(self, words: Iterable[str] | None = None) -> None:
        self.root = TrieNode()
        if words is not None:
            self.insert_all(words)

    def insert(self, word: str) -> None:
        """Insert a single keyword into the trie."""
        if not word:
            return
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.word = word

    def insert_all(self, words: Iterable[str]) -> None:
        """Insert multiple keywords."""
        for word in words:
            self.insert(word)

    def find_all(self, text: str, *, case_sensitive: bool = False) -> list[tuple[int, int, str]]:
        """Find all keyword occurrences in text.

        Returns
        -------
        list of (start, end, matched_keyword)
        """
        matches: list[tuple[int, int, str]] = []
        search_text = text if case_sensitive else text.lower()
        text_len = len(text)

        for i in range(text_len):
            node = self.root
            j = i
            while j < text_len:
                char = search_text[j]
                if char not in node.children:
                    break
                node = node.children[char]
                if node.word is not None:
                    matches.append((i, j + 1, node.word))
                j += 1

        return matches
