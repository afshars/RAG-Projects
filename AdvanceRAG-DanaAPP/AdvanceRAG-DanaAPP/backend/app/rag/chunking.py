import re


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks, breaking on sentence/word boundaries
    where possible. This is the fast, dependency-free fallback used when
    semantic chunking is disabled or unavailable.
    """
    clean = re.sub(r"\r\n", "\n", text)
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
    if not clean:
        return []

    chunks: list[str] = []
    start = 0
    step = max(1, chunk_size - overlap)

    while start < len(clean):
        end = min(start + chunk_size, len(clean))
        if end < len(clean):
            boundary = clean.rfind("\n", start, end)
            space = clean.rfind(" ", start, end)
            cut = boundary if boundary > start + chunk_size * 0.4 else space
            if cut > start + chunk_size * 0.3:
                end = cut

        piece = clean[start:end].strip()
        if len(piece) > 20:
            chunks.append(piece)

        if end >= len(clean):
            break
        start = end - overlap
        if start <= 0:
            start = end

    return chunks


def semantic_chunk_text(
    text: str,
    chunk_size: int,
    overlap: int,
    embeddings,
) -> list[str]:
    """Semantic chunking via LangChain's SemanticChunker: instead of cutting
    text at a fixed character count, it embeds consecutive sentences and
    splits where the *meaning* shifts (a large jump in embedding distance).
    This keeps each chunk topically coherent, which is what actually helps
    the retriever later on — fixed-size windows routinely slice a sentence
    (or an idea) in half.

    Falls back to the plain character-based splitter if langchain-experimental
    isn't installed, if `embeddings` is unavailable (e.g. the configured
    provider doesn't support /embeddings), or if anything goes wrong.
    """
    try:
        from langchain_experimental.text_splitter import SemanticChunker
    except Exception:
        return chunk_text(text, chunk_size, overlap)

    if embeddings is None:
        return chunk_text(text, chunk_size, overlap)

    try:
        splitter = SemanticChunker(
            embeddings,
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=90,
        )
        docs = splitter.create_documents([text])
        pieces = [d.page_content.strip() for d in docs if d.page_content and d.page_content.strip()]

        # SemanticChunker can occasionally produce a piece far larger than
        # chunk_size (e.g. one long coherent section) — re-split those with
        # the character splitter so nothing blows past the configured size.
        final: list[str] = []
        max_size = chunk_size * 2
        for piece in pieces:
            if len(piece) > max_size:
                final.extend(chunk_text(piece, chunk_size, overlap))
            elif len(piece) > 20:
                final.append(piece)

        return final if final else chunk_text(text, chunk_size, overlap)
    except Exception:
        return chunk_text(text, chunk_size, overlap)
