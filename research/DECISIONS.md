# Research and decision log

How 20 survey responses drove what Pona became — including what was cut, and the largest problem it does not solve.

**Method:** 20 respondents, four open questions about checking whether food is safe. Free-text answers coded by hand. Raw data in [`dashboard/data/`](dashboard/data/).

| | |
|---|---|
| Respondents | 20 |
| Had a checking method fail them | 11 / 20 |
| Answered on behalf of someone else | 4 / 20 |
| Conditions | 9 other dietary restriction · 4 proxy · 3 lactose intolerance · 2 food allergy · 2 acid reflux |

> **Stated up front:** this sample is small and convenience-recruited. It is enough to surface *which* problems exist and to quote people describing them. It is not enough to size them. Where this says "about half mentioned restaurants", read that as a theme worth acting on, not a market estimate.

---

## Finding 1 — the hardest problem is other people's food

Roughly half the free-text answers described restaurants, friends' kitchens, or asking staff. Not grocery labels.

> "Many restaurants have food which is labeled gluten free but is not actually safe for me to eat. I have to decide how much I trust the waiter, read their body language to try to tell whether they know what they're talking about, and whether they are taking me seriously."

> "Dealing with the other person's reaction and the internal feeling of not being included."

> "Asking the one who prepared the food too many questions."

> "Making sure it is within my dietary requirements without offending anyone."

A theme almost nothing is built for: **the burden is social as much as informational.** People already know what they cannot eat. The cost is in the asking.

## Finding 2 — label reading is the default, and it fails

Multi-select, n = 20:

| Method | Count |
|---|---|
| Read the label | 11 |
| Google it | 10 |
| Ask staff / cook | 9 |
| **Avoid anything uncertain** | **8** |
| Use an app | 5 |

Two of those rows are not strategies. **Eight of twenty cope by avoiding anything they are unsure about** — that is the status quo Pona competes with: people eating less than they safely could, because verifying is harder than abstaining. It reframes the goal. The win is not only catching allergens; it is returning foods to people that were never unsafe.

And only a quarter use an app at all.

> "Usually without my notice I overlook the milk content in the food."

> "Determining whether there are byproducts in the ingredients list that I might not recognize."

## Finding 3 — regulation itself creates a blind spot

> "In the US where I live, food labels include 'wheat' in allergen lists but don't include 'gluten', so products which contain rye or barley won't have any warning that they contain gluten. I've seen products labeled (and certified) as gluten free which also have the warning 'may contain wheat'."

Not an opinion — a description of a checkable gap between two things a user must not conflate. It became a direct design constraint.

---

# Decision log

## Separate wheat allergy from celiac disease — **shipped**

**Finding.** *"Products which contain rye or barley won't have any warning that they contain gluten."*

**Decision.** Two conditions rather than one "Wheat/Gluten allergy". Wheat allergy matches wheat protein; celiac disease matches gluten, wheat, **barley and rye**, and is described as autoimmune rather than an allergy.

**Outcome.** Celiac detection reaches 97.3% recall on human-tagged products, 99.2% counting cross-contamination flags. The barley and rye cases the respondent described are caught.

## Detect ingredient names people don't recognise — **shipped**

**Finding.** *"Byproducts in the ingredients list that I might not recognize."* / *"I overlook the milk content."*

**Decision.** Curate the hidden forms that share no obvious word with the allergen — `semolina`, `sodium caseinate`, `whey protein concentrate`, `ghee`, `marzipan` — plus guards so lookalikes are not wrongly flagged. Cocoa butter is not dairy; coconut milk is not dairy; buckwheat is not wheat.

**Outcome.** 94.5% recall over 22,799 allergen tags. 16 hidden forms and 14 lookalikes covered by regression tests.

## Never report "safe" for something not checked — **shipped**

**Finding.** The failure narratives were consistently about false confidence — confirming with staff and reacting anyway, or reading a label and missing something.

**Decision.** Remove "safe" from the vocabulary entirely. Results describe what was found relative to the profile, and anything that could not be evaluated is named in the result.

**Outcome.** Four separate paths that could have silently cleared a food were found and closed, each with a regression test. Including one where OCR reported 93.7% confidence while dropping `PEANUTS` from the ingredient list.

## No assumed trigger list for acid reflux — **shipped**

**Finding.** Both reflux respondents described knowing their own triggers rather than following a general list. Separately, eight of twenty already over-avoid.

**Decision.** Ship reflux with an empty trigger list. The user adds what they personally react to. A profile with nothing added reports that nothing was looked for — it does not report "no triggers found".

**Outcome.** A reflux user is never told to avoid tomato unless they said tomato affects them.

## Remove MSG sensitivity and gout — **removed**

**Finding.** Not from the survey directly, but from a scope rule the survey implied: respondents wanted to know what a food *contains*, not to be told what to eat.

**Decision.** An entry qualifies only if it names a specific ingredient, has support in food-regulator guidance, and can be stated without judging the food. MSG sensitivity fails the evidence test — the reported symptom cluster originates in a 1968 anecdote and has not been reproduced in controlled trials. Gout is disease diet management flagging broad categories such as "red meat".

**Outcome.** 13 conditions instead of a claimed 25+. A smaller product that does not assert things the evidence does not support.

## Coconut is not a tree nut — **reversed after measurement**

**Decision (first).** Follow the FDA, which classifies coconut as a tree nut for labelling.

**What the data said.** Measured across 14,798 real products, that made **860 of 1,073** tree-nut flags coconut products. Tree nut precision fell to 58.6%.

**Decision (revised).** Treat coconut as its own thing. Coconut allergy is uncommon and largely independent of tree nut allergy; the FDA classification is a labelling convention, not a clinical finding. Anyone who does react can add it as a personal trigger.

**Outcome.** Tree nut precision 58.6% → 85.6%, at a cost of 0.6 points of recall.

*Recorded as a reversal on purpose. The second decision was not better-reasoned than the first — it had a measurement behind it.*

## Photo and barcode as input methods — **shipped**

**Finding.** *"Take a pic and for it to tell me if it's good or not."* / *"Scan a code from the label."*

**Decision.** Three tiers by reliability: barcode, then label photo, then typed text. Neither scan feeds the matcher directly — extracted text is shown for the user to confirm against the packet.

**Outcome.** Barcode reads reliably and returns human-transcribed ingredients. Photo reading measured at 71.7% allergen recall, up from 56.5% after switching to a multi-pass approach — which is exactly why the confirmation step is mandatory rather than cosmetic.

## Chef card — **shipped**

**Finding.** The largest theme: the social cost of asking. *"Too many questions"*, *"without offending anyone"*, *"not being included"*.

**Decision.** Render the profile for a kitchen. Two things a handwritten card cannot do: list the hidden names an allergen appears under (from the same knowledge base as the matcher, so they cannot drift), and separate conditions by **nature** rather than severity — an IgE allergy and celiac disease both need clean equipment, for different reasons; an intolerance needs neither.

The questions are sized to be **shown**, not just spoken. Asking out loud is the costly part, and more so for someone nonverbal or who finds the exchange draining.

**Outcome.** Tests assert celiac is never described as an allergy, and that an intolerance-only profile does not request clean equipment — asking for it where trace amounts do not matter trains kitchens to discount the request where they do.

## Restaurant and cross-contact checking — **not built**

**Finding.** The largest theme in the survey.

**Decision.** Deliberately deferred. Restaurant food has no ingredient list, no barcode and no database behind it — there is nothing to match against. The packaged-food path was the tractable adjacent problem, and it builds the engine any restaurant feature would need.

**Outcome.** The chef card addresses the *communication* half. The verification half remains unsolved, recorded here rather than quietly dropped.

---

# What the shipped system measures

| | |
|---|---|
| Allergen recall, English labels | **94.5%** (95.6% with cross-contamination flags) |
| Measured over | 22,799 allergen tags on real products |
| Label photo reading | 71.7%, up from 56.5% |
| Conditions | 13, each evidence-scoped |

## A finding the product did not set out to make

Splitting the benchmark by label language exposed a disparity in the system's own behaviour:

| | Recall |
|---|---|
| English labels | **96.5%** |
| Other languages | **27.3%** |

Reported separately rather than averaged into a flattering combined figure. A safety tool that protects English speakers and largely fails everyone else is a defect, not a footnote — and it is only visible because the results were disaggregated.

# What the research says to do next

1. **Close the language gap.** The largest measured defect. Candidate allergen terms can be mined in any language by statistical lift over the language-independent allergen tags, then confirmed by a speaker. A trial run surfaced `fromage` and `lait` correctly without anyone reading French.
2. **Substitutions, then recipes.** Four of twenty answered for someone else. "What do I cook instead" is the half the scanner does not touch.
3. **Revisit restaurants.** Still the biggest theme. Worth returning to when there is a reason to believe a data source exists.
4. **Clinical review.** The knowledge base is seed data. The benchmark makes review cheap — it is a check on judgement calls, not an audit from scratch.

---

*Survey conducted June 2026, n = 20, convenience sample. Benchmarks run against the Open Food Facts public dataset. The Pona knowledge base is seed data and has not been clinically reviewed.*
