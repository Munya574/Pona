# NLP ingredient normalization model
# Architecture: fine-tuned DistilBERT or spaCy pipeline
# Task: map raw ingredient text to standardized ingredient entities
# Training data: Open Food Facts (4M+ products), USDA FoodData Central
#
# Examples:
#   "sodium caseinate"          -> "dairy derivative"
#   "hydrolyzed wheat protein"  -> "gluten source"
#   "groundnuts"                -> "peanuts"
#   "natural flavors"           -> flagged as ambiguous


def normalize(raw_text: str) -> list[str]:
    """Map raw ingredient text to a list of normalized ingredient names."""
    raise NotImplementedError
