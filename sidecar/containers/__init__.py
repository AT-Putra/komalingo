"""Container readers. One module per format, and each one reads only.

Phase 3 needs CBZ enumeration so the page-cache contract is frozen against a
real multi-page item rather than against a directory of loose files. Phase 6
is what adds writing, safety enforcement and the other formats -- and it is a
different code path on purpose, because the read that feeds the editor and the
ingest that enforces a zip-bomb budget have different failure modes and should
not share a function.
"""
