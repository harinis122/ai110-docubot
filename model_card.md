# DocuBot Model Card

DocuBot is a lightweight documentation assistant for a small sample application. It is designed to answer developer questions by reading project docs, retrieving relevant snippets, and optionally using an LLM for a more natural explanation. The system is intentionally simple and transparent, with a strong preference for refusing to answer when evidence is weak.

---

## 1. System Overview

**What is DocuBot trying to do?**  
DocuBot helps developers find information quickly in project documentation. Its main goal is to provide grounded answers about authentication, APIs, setup, and database usage without pretending to know facts that are not actually supported by the docs.

**What inputs does DocuBot take?**  
DocuBot reads markdown and text files from the docs folder, plus a user question. If an LLM client is configured, it can also use an API key from the environment to support RAG-style answers.

**What outputs does DocuBot produce?**  
The system returns retrieved snippet(s) for retrieval-only mode, or a short answer that is grounded in those snippets for RAG mode. If there is not enough evidence, it returns a refusal message instead of guessing.

---

## 2. Retrieval Design

**How does your retrieval system work?**  
The retrieval system is a simple keyword-based pipeline. Documents are loaded from the docs folder, split into smaller chunks, and indexed by lowercase word tokens. For a user query, DocuBot removes common stopwords, looks up matching chunks in the index, scores them by overlap with meaningful query terms, and returns the highest-scoring snippets.

- Documents are turned into an index by tokenizing each chunk and storing which chunk contains each term.
- Relevance is scored by counting meaningful query terms that appear in a chunk.
- Top snippets are chosen from the highest-scoring chunks, with a limit set by the caller.

**What tradeoffs did you make?**  
The system favors simplicity and transparency over recall or semantic understanding. It is fast and easy to inspect, but it can miss relevant content when wording differs from the query or when the answer depends on broader context.

---

## 3. Use of the LLM (Gemini)

**When does DocuBot call the LLM and when does it not?**  
- Naive LLM mode: Uses the full docs corpus with no retrieval and is only appropriate when the LLM is available and the user is comfortable with a less grounded answer.
- Retrieval only mode: Does not call the LLM at all. It returns the most relevant snippets directly from the docs.
- RAG mode: Calls the LLM only after retrieval has selected relevant snippets, and it is instructed to answer using only those snippets.

**What instructions do you give the LLM to keep it grounded?**  
The prompt tells the model to use only the provided snippets, not to invent endpoints or configuration values, and to say “I do not know based on the docs I have” whenever the evidence is insufficient.

---

## 4. Experiments and Comparisons

The same style of questions were used across the three modes. The results were most consistent when the docs contained direct, explicit text.

| Query | Naive LLM: helpful or harmful? | Retrieval only: helpful or harmful? | RAG: helpful or harmful? | Notes |
|------|---------------------------------|--------------------------------------|---------------------------|-------|
| Where is the auth token generated? | Potentially helpful but less trustworthy | Helpful | Helpful | Retrieval and RAG both surface the relevant auth docs. |
| How do I connect to the database? | Could sound plausible but may overgeneralize | Helpful | Helpful | The docs contain setup and database guidance that retrieval can surface clearly. |
| Which endpoint lists all users? | Risky if the model guesses | Helpful | Helpful | The API reference provides a direct answer. |
| How does a client refresh an access token? | Can sound convincing without grounding | Helpful | Helpful | Retrieval is a strong fit for this kind of specific documentation question. |

**What patterns did you notice?**  

- Naive LLM looks impressive when the question is broad or conversational, but it can be untrustworthy because it is not tied to the docs.
- Retrieval only is often better for exact questions where the answer is explicitly present in the docs.
- RAG is usually the best choice when the user wants a concise explanation rather than raw snippets, as long as the retrieved evidence is strong enough.

---

## 5. Failure Cases and Guardrails

**Describe at least two concrete failure cases you observed.**  

- What was the question? “the” or another vague query.  
  What did the system do? Earlier versions could return weak or noisy matches.  
  What should have happened instead? The system should refuse and say it does not have meaningful evidence.

- What was the question? A question about a topic that is not covered in the docs, such as payment processing.  
  What did the system do? A naive LLM may answer confidently even though the docs do not mention it.  
  What should have happened instead? The system should say that the docs do not contain enough evidence to support an answer.

**When should DocuBot say “I do not know based on the docs I have”?**  
It should refuse when the query is vague, when the retrieved snippets have no meaningful overlap with the question, or when answering would require inventing facts that are not in the documentation.

**What guardrails did you implement?**  
The system now filters out common stopwords, retrieves smaller chunks instead of whole documents, and refuses to answer unless at least one chunk has meaningful evidence. This makes the behavior safer and easier to audit.

---

## 6. Limitations and Future Improvements

**Current limitations**  
1. Retrieval is keyword-based and does not understand synonyms or deeper semantics.
2. Chunking is simple and may split information awkwardly.
3. The system does not yet rerank or verify whether a retrieved chunk truly answers the question.
4. The LLM can still be affected by prompt wording and may be less reliable when the evidence is sparse.

**Future improvements**  
1. Add embeddings-based semantic retrieval.
2. Add a reranker to improve snippet precision.
3. Improve citation and evidence quality so answers point to the exact supporting lines or sections.
4. Add a confidence score so the system can refuse more consistently.

---

## 7. Responsible Use

**Where could this system cause real world harm if used carelessly?**  
If someone treats DocuBot as a source of truth without checking the docs, it could provide incorrect instructions or missed details for setup, security, or API behaviors.

**What instructions would you give real developers who want to use DocuBot safely?**  
- Treat DocuBot as an assistant, not an authority.
- Verify important instructions against the original documentation.
- Prefer retrieval-only or RAG outputs over naive generation when accuracy matters.
- Do not use the system for high-stakes decisions without human review.
