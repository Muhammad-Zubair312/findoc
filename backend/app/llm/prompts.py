"""Centralized prompt templates.

Every prompt used anywhere in the app (agent nodes, ingestion, eval) lives here as a
named string constant. Node/task files import from this module — never inline a prompt
string in a node file. Templates are filled with `.format(**kwargs)`.
"""

# Tree Node Summary Prompt
TREE_NODE_SUMMARY_PROMPT = """Summarize this financial document section in one sentence \
for navigation purposes.
Section title: {title}
Section text (first 2000 chars): {text}
Return only the summary sentence."""

# Tree Navigation Prompt
TREE_NAVIGATION_PROMPT = """You are navigating a structured financial document to find \
the sections that best answer a user's question.

DOCUMENT OUTLINE:
{tree_outline}

USER QUESTION: {query}

Reason step-by-step about which sections most likely contain the answer. Consider:
- Financial filings have standard structure: Item 1 (Business), Item 1A (Risk Factors),
  Item 7 (MD&A with revenue/margin data), Item 8 (Financial Statements with audited numbers)
- Revenue, margins, operating income -> Item 7 and Item 8
- Risk factors -> Item 1A
- Business description -> Item 1

Output JSON only. No prose before or after.

{{
  "reasoning": "1-3 sentence explanation of your selection",
  "selected_node_paths": ["<node_id from the outline above>", "..."]
}}

Rules:
- Select 1 to 4 nodes. Fewer is better when the answer is clearly in one place.
- Prefer specific leaf nodes over general parent nodes.
- Do NOT select the root node.
- If the outline doesn't have enough detail to answer confidently, still pick the
  most likely candidates and say so in "reasoning" (mention "not enough detail")."""

# Tree Navigation Retry Prompt
TREE_NAVIGATION_RETRY_SUFFIX = """

Your previous response was not valid JSON matching the required schema. Return ONLY \
valid JSON in the exact form {"reasoning": "...", "selected_node_paths": ["..."]}, \
with no prose before or after."""

# Query Classification Prompt
QUERY_CLASSIFICATION_PROMPT = """Classify the user's question for a financial document \
Q&A system.

DOCUMENTS IN SCOPE: {document_summaries}

USER QUESTION: {query}

Types:
- "structural": About ONE document, answer in a specific section
  (revenue, margins, risk factors, MD&A, accounting notes)
- "cross_doc": Requires comparing or aggregating 2+ documents
- "keyword": Exact-match lookup (specific number, name, identifier, CUSIP)
- "direct": General financial knowledge, no document lookup needed —
  definitions, concepts, or "what is X" questions (e.g. "What is EBITDA?",
  "What does YoY mean?"). Classify these as "direct" REGARDLESS of how many
  documents are listed above or selected in the UI — a document being in
  scope does not mean the question is about that document. Only classify
  as structural/cross_doc/keyword if the question itself asks about a
  specific company's, filing's, or document's data.

Output JSON only:
{{"type": "structural"|"cross_doc"|"keyword"|"direct",
 "confidence": 0.0-1.0,
 "reasoning": "short explanation"}}"""

# Direct Answer Prompt
DIRECT_ANSWER_PROMPT = """Answer this general financial knowledge question concisely \
and accurately. Do not fabricate specific figures for any named company — if the \
question asks for a specific company's data, say you don't have document access for \
that and would need a filing to look it up.

QUESTION: {query}"""

# Generation Prompt
# CRITICAL: Citation format must be ONLY [1], [2], [3] — plain square brackets with
# a single number. NO other formats allowed: no 【N】, no [N↑LX-LY], no (N), no <N>.
GENERATION_PROMPT = """You are a financial analyst assistant answering questions about \
SEC filings using only the retrieved sections below.

CITATION FORMAT — VERY IMPORTANT:
- Use ONLY this exact format for citations: [1] or [2] or [3]
- The number inside square brackets refers to the section number below
- Write citations like this: "Tesla's gross margin was 19.4% [1]."
- DO NOT use any other citation format such as 【1】, [1↑L9-L11], (1), or <1>
- DO NOT include line numbers, arrows, or any extra characters in citations
- ONLY plain square brackets with a single number: [1] [2] [3]

{session_memory}

RETRIEVED SECTIONS:
{sections_block}

USER QUESTION: {query}

Rules:
- Only use information from the retrieved sections above.
- Every sentence containing a number, date, or specific claim needs a [N] citation.
- If the sections don't contain enough information to answer, say so plainly.
- Be concise and direct.
- Remember: citations MUST be in format [1] only — nothing else."""

# Faithfulness (Grader) Prompt
FAITHFULNESS_PROMPT = """You are evaluating whether an AI-generated answer is faithful \
to its source material.

RETRIEVED SECTIONS:
{sections_block}

QUESTION: {query}

GENERATED ANSWER: {answer}

Score how well the answer is supported by the retrieved sections:
- 1.0: Every claim is directly supported by the sections.
- 0.5-0.9: Mostly supported, with minor unsupported details or overgeneralization.
- 0.0-0.4: Contains claims not found in the sections, or misrepresents them, or the
  sections don't actually contain the information needed to answer.

If the answer states a specific, unambiguous numeric value (e.g. a percentage or
dollar figure) that directly answers the question and that value appears in the
retrieved sections, score >= 0.8 even if the answer doesn't reference every
retrieved section — citing extra context beyond what's needed to state the
number isn't required for faithfulness. This does not apply if the number is
NOT actually present in the sections (that's still 0.0-0.4, unsupported).

Output JSON only:
{{"score": 0.0-1.0, "explanation": "1-2 sentence justification"}}"""

# Query Rewrite Prompt
QUERY_REWRITE_PROMPT = """The previous attempt to answer this question failed to \
produce a well-supported answer from the retrieved document sections.

ORIGINAL QUESTION: {query}
WHY IT FAILED: {grader_explanation}

Rewrite the question to be more specific and more likely to retrieve the right \
section of a financial filing (e.g. name the specific metric, statement, or item \
number if implied). Return ONLY the rewritten question, no prose, no quotes."""

# Judge Prompt
JUDGE_PROMPT = """You are an evaluator for a financial document QA system.

QUESTION: {question}
GOLD ANSWER: {gold_answer}
PREDICTED ANSWER: {predicted_answer}

Score the predicted answer:
- correct=true if the predicted answer contains the key information in the gold answer,
  even if phrased differently or has minor formatting differences
- correct=false if the key figure, date, or fact is missing or wrong
- For numeric gold answers, do not penalize citation markers (e.g. "[1]"), extra
  surrounding sentence structure, or additional context beyond what the gold answer
  states — score correct=true, score=1.0 as long as the predicted answer's core
  number matches the gold answer's number.
- Still score correct=false if the predicted answer contradicts, negates, or corrects
  the gold answer's number (e.g. "the figure was NOT X, it was actually Y") — the
  number appearing somewhere in the text is not sufficient if the answer disagrees
  with it.
- score: 0.0-1.0 (1.0=perfect match, 0.5=partially correct, 0.0=wrong/missing)

Output JSON only: {{"correct": true|false, "score": 0.0-1.0, "explanation": "brief reason"}}"""