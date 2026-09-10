# Ingredient normalization.
#
# SUPERSEDED - use app.ml.matcher instead.
#
# This module was meant to hold a fine-tuned DistilBERT ingredient
# normalizer. That model was built and evaluated on 14,334 real examples
# and scored F1 = 0.0; it never learned to tag the rare classes at all.
#
# The rule-based normalizer in matcher.py replaced it and does better on
# every axis that matters here:
#
#   - 95.7% recall on 14,798 human-tagged products
#     (notebooks/benchmark_matcher.py)
#   - every result traceable to a named rule, which matters for a
#     safety decision someone may need to question
#   - no model, no 2GB of dependencies, no inference latency
#
# Kept as a signpost so nobody re-derives the same dead end. If a model is
# ever revisited, it has to beat the benchmark above to be worth having.

from app.ml.matcher import normalize_ingredient, normalize_ingredients  # noqa: F401
