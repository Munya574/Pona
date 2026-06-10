# Sensitivity matching engine
# Type: rule-based with ML ranking layer
# Knowledge base: curated sensitivity-to-ingredient mapping (sensitivity_kb/)
# Vector store: FAISS for RAG-based retrieval


def match(ingredients: list[str], sensitivities: list[str]) -> list[dict]:
    """
    Return a list of trigger dicts for any ingredient that conflicts with
    the given sensitivity list.

    Each dict has: ingredient, sensitivity, explanation, confidence.
    """
    raise NotImplementedError
