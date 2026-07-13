"""
Core DocuBot class responsible for:
- Loading documents from the docs/ folder
- Building a simple retrieval index (Phase 1)
- Retrieving relevant snippets (Phase 1)
- Supporting retrieval only answers
- Supporting RAG answers when paired with Gemini (Phase 2)
"""

import os
import glob
import re


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


def _tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


class DocuBot:
    def __init__(self, docs_folder="docs", llm_client=None):
        """
        docs_folder: directory containing project documentation files
        llm_client: optional Gemini client for LLM based answers
        """
        self.docs_folder = docs_folder
        self.llm_client = llm_client

        # Load documents into memory
        self.documents = self.load_documents()  # List of (filename, text)

        # Build a retrieval index (implemented in Phase 1)
        self.index = self.build_index(self.documents)

    # -----------------------------------------------------------
    # Document Loading
    # -----------------------------------------------------------

    def load_documents(self):
        """
        Loads all .md and .txt files inside docs_folder.
        Returns a list of tuples: (filename, text)
        """
        docs = []
        pattern = os.path.join(self.docs_folder, "*.*")
        for path in glob.glob(pattern):
            if path.endswith(".md") or path.endswith(".txt"):
                with open(path, "r", encoding="utf8") as f:
                    text = f.read()
                filename = os.path.basename(path)
                docs.append((filename, text))
        return docs

    # -----------------------------------------------------------
    # Index Construction (Phase 1)
    # -----------------------------------------------------------

    def build_index(self, documents):
        """
        TODO (Phase 1):
        Build a tiny inverted index mapping lowercase words to the documents
        they appear in.

        Example structure:
        {
            "token": ["AUTH.md", "API_REFERENCE.md"],
            "database": ["DATABASE.md"]
        }

        Keep this simple: split on whitespace, lowercase tokens,
        ignore punctuation if needed.
        """
        index = {}
        for filename, text in documents:
            for chunk_idx, chunk in enumerate(self._chunk_text(text)):
                for token in _tokenize(chunk):
                    index.setdefault(token, []).append((filename, chunk_idx, chunk))
        return index

    # -----------------------------------------------------------
    # Scoring and Retrieval (Phase 1)
    # -----------------------------------------------------------

    def _chunk_text(self, text, chunk_size=120):
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        chunks = []

        for paragraph in paragraphs:
            sentences = re.split(r"(?<=[.!?])\s+", paragraph)
            current = ""
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                if current and len(current.split()) + len(sentence.split()) > chunk_size:
                    chunks.append(current.strip())
                    current = sentence
                else:
                    current = f"{current} {sentence}".strip() if current else sentence
            if current:
                chunks.append(current.strip())

        return chunks or [text.strip()]

    def _extract_query_terms(self, query):
        return [token for token in _tokenize(query) if token not in STOPWORDS]

    def _has_meaningful_evidence(self, query, snippets):
        query_terms = self._extract_query_terms(query)
        if not query_terms or not snippets:
            return False

        best_score = max(self.score_document(query, text) for _, text in snippets)
        return best_score >= 1

    def score_document(self, query, text):
        """
        TODO (Phase 1):
        Return a simple relevance score for how well the text matches the query.

        Suggested baseline:
        - Convert query into lowercase words
        - Count how many appear in the text
        - Return the count as the score
        """
        query_tokens = self._extract_query_terms(query)
        text_tokens = _tokenize(text)

        if not query_tokens:
            return 0

        text_token_counts = {}
        for token in text_tokens:
            text_token_counts[token] = text_token_counts.get(token, 0) + 1

        score = 0
        for token in query_tokens:
            if token in text_token_counts:
                score += 1 + min(text_token_counts[token], 1)
        return score

    def retrieve(self, query, top_k=3):
        """
        TODO (Phase 1):
        Use the index and scoring function to select top_k relevant document snippets.

        Return a list of (filename, text) sorted by score descending.
        """
        query_tokens = self._extract_query_terms(query)
        if not query_tokens:
            return []

        seen_chunks = set()
        candidate_chunks = []
        for token in query_tokens:
            for filename, chunk_idx, chunk_text in self.index.get(token, []):
                chunk_ref = (filename, chunk_idx)
                if chunk_ref not in seen_chunks:
                    seen_chunks.add(chunk_ref)
                    candidate_chunks.append((filename, chunk_idx, chunk_text))

        if not candidate_chunks:
            return []

        results = []
        for filename, _, text in candidate_chunks:
            score = self.score_document(query, text)
            if score > 0:
                results.append((score, filename, text))

        results.sort(key=lambda item: (-item[0], item[1]))
        return [(filename, text) for _, filename, text in results[:top_k]]

    # -----------------------------------------------------------
    # Answering Modes
    # -----------------------------------------------------------

    def answer_retrieval_only(self, query, top_k=3):
        """
        Phase 1 retrieval only mode.
        Returns raw snippets and filenames with no LLM involved.
        """
        snippets = self.retrieve(query, top_k=top_k)

        if not self._has_meaningful_evidence(query, snippets):
            return "I do not know based on these docs."

        formatted = []
        for filename, text in snippets:
            formatted.append(f"[{filename}]\n{text}\n")

        return "\n---\n".join(formatted)

    def answer_retrieval_oonly(self, query, top_k=3):
        return self.answer_retrieval_only(query, top_k=top_k)

    def answer_rag(self, query, top_k=3):
        """
        Phase 2 RAG mode.
        Uses student retrieval to select snippets, then asks Gemini
        to generate an answer using only those snippets.
        """
        if self.llm_client is None:
            raise RuntimeError(
                "RAG mode requires an LLM client. Provide a GeminiClient instance."
            )

        snippets = self.retrieve(query, top_k=top_k)

        if not self._has_meaningful_evidence(query, snippets):
            return "I do not know based on these docs."

        return self.llm_client.answer_from_snippets(query, snippets)

    # -----------------------------------------------------------
    # Bonus Helper: concatenated docs for naive generation mode
    # -----------------------------------------------------------

    def full_corpus_text(self):
        """
        Returns all documents concatenated into a single string.
        This is used in Phase 0 for naive 'generation only' baselines.
        """
        return "\n\n".join(text for _, text in self.documents)
