from __future__ import annotations

from backend.app.store import QueryRecord
from backend.app.trie import Suggestion, SuggestionTrie


def record_to_suggestion(record: QueryRecord, mode: str = "basic") -> Suggestion:
    score = record.trending_score
    if mode == "basic":
        return Suggestion(query=record.query, count=record.global_count, score=float(record.global_count))
    return Suggestion(query=record.query, count=record.global_count, score=score)


def records_to_suggestions(records: list[QueryRecord], mode: str = "basic") -> list[Suggestion]:
    suggestions = [record_to_suggestion(r, mode) for r in records]
    if mode == "basic":
        suggestions.sort(key=lambda s: (-s.count, s.query))
    else:
        suggestions.sort(key=lambda s: (-s.score, -s.count, s.query))
    return suggestions


def trie_suggestions_to_response(suggestions: list[Suggestion]) -> list[dict]:
    return [s.to_dict() for s in suggestions]
