"""INDEX_KB and RETRIEVE_CONTEXT: intent narrows the search, TF-IDF ranks within it.

At index time the classifier's rules read each article and tag it with the
intents it covers (from the article's own text, never a hard-coded ID map).
At query time the ticket text is scored against every article with TF-IDF, and
the articles tagged with the ticket's intents come first, best score first.

Why not TF-IDF alone: on the test tickets, plain lexical scores couldn't tell
"found it" from "nothing relevant" (an off-topic ticket sharing the word
"account" outscored correct matches), and some tickets share no words with the
right article at all ("Is BTC a good buy?" vs the no-advice article).

A ticket classified `other` matches no tags. It still gets the single best
TF-IDF article, since the brief requires 1 to 3, but marked `on_intent=False`,
so policy treats it as ungrounded. Anything with the same `retrieve` method can
replace TfidfRetriever (e.g. embedding search).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from triage.classify import Classifier
from triage.schemas import Article

MAX_RESULTS = 3


@dataclass(frozen=True)
class Hit:
    article: Article
    score: float  # TF-IDF cosine similarity to the ticket text, 0..1
    on_intent: bool  # the article is tagged with one of the ticket's intents


class Retriever(Protocol):
    def retrieve(self, text: str, intents: Sequence[str]) -> list[Hit]: ...


class TfidfRetriever:
    def __init__(self, articles: Sequence[Article], classifier: Classifier):
        self.articles = list(articles)
        docs = [_document(a) for a in self.articles]
        self._vectorizer = TfidfVectorizer(stop_words="english", sublinear_tf=True)
        self._matrix = self._vectorizer.fit_transform(docs)
        self.tags: dict[str, frozenset[str]] = {
            a.article_id: frozenset(classifier.classify(doc).matches) for a, doc in zip(self.articles, docs)
        }

    def scores(self, text: str) -> dict[str, float]:
        # Rounded so float noise can never reorder equal scores between runs.
        raw = linear_kernel(self._vectorizer.transform([text]), self._matrix)[0]
        return {a.article_id: round(float(s), 6) for a, s in zip(self.articles, raw)}

    def retrieve(self, text: str, intents: Sequence[str]) -> list[Hit]:
        scores = self.scores(text)
        by_score = sorted(self.articles, key=lambda a: (-scores[a.article_id], a.article_id))

        hits: list[Hit] = []
        for intent in intents:
            for article in by_score:
                if len(hits) == MAX_RESULTS:
                    return hits
                if intent in self.tags[article.article_id] and all(h.article != article for h in hits):
                    hits.append(Hit(article, scores[article.article_id], on_intent=True))

        if not hits:
            best = by_score[0]
            hits.append(Hit(best, scores[best.article_id], on_intent=False))
        return hits


def _document(article: Article) -> str:
    return f"{article.title}. {article.body}"
