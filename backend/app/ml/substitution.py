# Substitution retrieval system
# Type: retrieval over curated substitution knowledge base
# Training data: Recipe1MSub benchmark dataset
# Research: FoodBERT / Food2Vec embeddings for semantic similarity


def get_substitutions(ingredient: str, context: str) -> list[dict]:
    """
    Return 1-3 safe alternatives for the given ingredient.
    context: "baking" | "cooking" | "raw"
    Each dict has: name, notes.
    """
    raise NotImplementedError
