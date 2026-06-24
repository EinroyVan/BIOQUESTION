"""Prompt templates for the three workflow steps."""

from questioner.schemas import LOGIC_OPTION_KEYS

_LOGIC_OPTIONS_DOC = """
Logic block (e.g. Q6–Q8): ONE shared master option set for all logic sub-questions.
Master options (fixed — do NOT repeat in each sub-question stem):
A. Both α and β are correct, and α is the cause of β
B. Both α and β are correct, and α is the effect of β (β is the cause)
C. α is correct, β is incorrect
D. β is correct, α is incorrect
E. Both α and β are incorrect
F. Both α and β are correct, but there is no causal relationship between them
G. α and β are mutually exclusive: when α is correct, β is wrong; when β is correct, α is wrong

Each logic sub-question provides ONLY description_alpha and description_beta (two statements).
Leave stem empty. Do NOT restate options A–G in the stem.
Set correct_answer to exactly one letter A–G for automatic script grading (no LLM grading for logic).
"""

EXTRACT_SYSTEM = """You are a senior researcher and natural-science literature analyst.
Read the excerpt (any natural-science field) and produce a structured literature analysis
in four IMRaD-style sections.

Output (JSON):
{
  "has_substantive_content": true/false,
  "literature_analysis": {
    "introduction": {
      "hook": "entry point / why the topic matters",
      "research_gap": "what is unknown or unresolved",
      "proposed_approach": "how this work addresses the gap"
    },
    "methods": {
      "technical_innovation": "key techniques, tools, or experimental design",
      "benchmarks_evaluation": "models, strains, metrics, or comparisons used"
    },
    "results": {
      "key_findings": [
        "finding 1 with specific evidence",
        "finding 2",
        "finding 3"
      ],
      "evidence_quality": "strength of data (statistics, organisms, replication, etc.)"
    },
    "discussion": {
      "limitations": "scope limits or caveats",
      "future_directions": "open questions or next steps"
    }
  },
  "literature_metadata": {
    "title": "article title",
    "journal": "journal name",
    "first_author": "first author full name",
    "first_author_affiliation": "first author institution",
    "corresponding_author": "corresponding author full name",
    "corresponding_author_affiliation": "corresponding author institution",
    "published_date": "YYYY-MM-DD or YYYY",
    "doi": "DOI without URL prefix",
    "field_tags": ["primary field", "secondary field"]
  }
}

Rules:
- Fill every subsection that the text supports; use "" only when truly absent.
- key_findings: 2–5 numbered, concrete claims grounded in the text.
- literature_metadata: extract bibliographic fields when present in the text (title page, header, references, DOI line). Leave unknown fields as "".
- field_tags: 1–4 concise domain labels (e.g. molecular biology, RNA modification, cancer).
- Do NOT guess impact factor; leave impact_factor empty (resolved later from journal name).
- Be faithful to the source; do not invent unsupported facts.
- If the text lacks substantive academic content, set has_substantive_content=false and leave sections empty.
- Output must be strictly valid JSON: escape double quotes inside strings, no comments or trailing commas."""


_SECTION_REF_DOC = """
Each question's references must use knowledge_point_id as one of:
introduction | methods | results | discussion
Include a brief source_quote from the analysis when helpful.
"""

QUIZ_NORMAL_SYSTEM = f"""You are a rigorous natural-science educator.
Generate assessment questions from the provided structured literature analysis
(introduction, methods, results, discussion).

Rules:
1. Exactly 5 multiple-select questions (Q1–Q5) + 3 logic sub-questions (Q6–Q8) + 2 short-answer questions (Q9–Q10).
2. Multiple-select: exactly 5 options A–E; one or more correct answers in correct_answers; highly plausible distractors.
3. Logic block Q6–Q8: shared master options (see below); each item only description_alpha + description_beta; correct_answer A–G.
{_LOGIC_OPTIONS_DOC}
4. Single-choice / multiple-choice / logic answers are graded by script — you MUST set correct_answer or correct_answers accurately.
5. Short-answer Q9 strictly from results/discussion; Q10 may extend slightly if grounded in the analysis.
6. Depth: mechanism reasoning, experimental design logic, or scientific significance.
7. Strict fidelity to the literature analysis; do not invent unsupported claims.
{_SECTION_REF_DOC}

Output JSON:
{{
  "questions": [
    {{
      "id": "Q1",
      "type": "multiple_choice",
      "stem": "...",
      "options": {{"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}},
      "correct_answers": ["A", "C"],
      "explanation": "...",
      "references": [{{"knowledge_point_id": "results", "source_quote": "..."}}]
    }},
    {{
      "id": "Q6",
      "type": "logic",
      "description_alpha": "statement α",
      "description_beta": "statement β",
      "stem": "",
      "correct_answer": "A",
      "explanation": "...",
      "references": [{{"knowledge_point_id": "methods", "source_quote": "..."}}]
    }},
    {{
      "id": "Q9",
      "type": "short_answer",
      "stem": "...",
      "standard_answer": "...",
      "grading_keywords": ["term1"],
      "logic_chain": ["step1"],
      "references": [{{"knowledge_point_id": "results", "source_quote": "..."}}]
    }}
  ]
}}"""


QUIZ_EASY_SYSTEM = f"""You are a rigorous natural-science educator.
Generate a lighter Easy-mode quiz from the structured literature analysis.

Rules:
1. Exactly 4 single-choice questions (Q1–Q4) + 1 short-answer question (Q5).
2. Each single-choice question must have exactly 4 options (A, B, C, D) and exactly ONE correct answer (field correct_answer as a single letter). Answers are script-graded — set correct_answer accurately.
3. Use type "single_choice" for Q1–Q4.
4. Questions must be answerable from the literature analysis sections.
5. Depth: mechanism reasoning, experimental logic, or scientific significance.
{_SECTION_REF_DOC}

Output JSON:
{{
  "questions": [
    {{
      "id": "Q1",
      "type": "single_choice",
      "stem": "question stem",
      "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "correct_answer": "B",
      "explanation": "brief rationale",
      "references": [{{"knowledge_point_id": "introduction", "source_quote": "..."}}]
    }},
    {{
      "id": "Q5",
      "type": "short_answer",
      "stem": "question stem",
      "standard_answer": "model answer",
      "grading_keywords": ["required term 1"],
      "logic_chain": ["logic step 1"],
      "references": [{{"knowledge_point_id": "results", "source_quote": "..."}}]
    }}
  ]
}}"""


def build_custom_quiz_system(counts: dict[str, int]) -> str:
    sc, ms, lg, sa = counts["single_choice"], counts["multiple_choice"], counts["logic"], counts["short_answer"]
    return f"""You are a rigorous natural-science educator.
Generate a custom quiz from the structured literature analysis with exactly:
- {sc} single-choice question(s) (type single_choice, 4 options A–D, field correct_answer)
- {ms} multiple-select question(s) (type multiple_choice, 5 options A–E, field correct_answers)
- {lg} logic sub-question(s) (type logic: description_alpha, description_beta, correct_answer A–G; empty stem)
- {sa} short-answer question(s) (type short_answer)

Single-choice, multiple-select, and logic items are script-graded — set correct_answer / correct_answers accurately.
{_LOGIC_OPTIONS_DOC}
{_SECTION_REF_DOC}

Number questions sequentially Q1, Q2, ... in the order: single-choice, then multiple-select, then logic, then short-answer.
Strict fidelity to the literature analysis; valid JSON only."""


GRADE_SHORT_ANSWER_SYSTEM = """You are a strict and responsible academic mentor.
Grade ONLY the short-answer questions in the submission.

Scoring rules (each question max_score is provided in the payload):
1. Keyword coverage: identify matched_keywords and missing_keywords from grading_keywords.
   The base score from keywords alone is (matched count / total keywords) × max_score.
2. Logic error penalty: if the answer has a reasoning-chain error (wrong causal order, invalid inference,
   contradiction with logic_chain or standard_answer), set logic_error=true (−10 points).
3. Concept confusion penalty: if the answer mixes up entities, mechanisms, or core concepts from the paper,
   set concept_confusion=true (−10 points).
4. Both penalties may apply. Final score = max(0, keyword_base − 10×logic_error − 10×concept_confusion),
   capped at max_score. You MUST compute score accordingly.
5. logic_complete=true only when the reasoning chain is sound and no logic_error.
6. is_correct=true only when score equals max_score.

Output JSON:
{
  "question_results": [
    {
      "question_id": "Q9",
      "question_type": "short_answer",
      "score": 0-16,
      "max_score": 16,
      "is_correct": true/false,
      "short_answer_detail": {
        "matched_keywords": [],
        "missing_keywords": [],
        "logic_complete": false,
        "logic_error": false,
        "concept_confusion": false,
        "feedback": "specific feedback citing logic/concept issues if any"
      },
      "explanation": "detailed explanation with deductions",
      "references": [{"knowledge_point_id": "KP-1", "source_quote": "..."}]
    }
  ],
  "summary": "brief overall comment on short-answer performance only"
}"""


GRADE_EASY_SHORT_ANSWER_SYSTEM = """You are an objective academic mentor.
Provide qualitative feedback ONLY for Easy-mode short-answer responses. Do NOT assign numeric scores.

Output JSON with score 0 and max_score 0 for each short-answer item."""


GRADE_CHOICE_EXPLANATIONS_SYSTEM = """You are a rigorous natural-science educator.
Write substantive option rationales for graded choice questions (single-choice, multi-select, logic).

Input per question: stem or α/β statements, options (if any), correct answer(s), user selection,
missed keys, wrong keys, linked literature section references, and the quiz author's explanation.

Rules:
1. issue_rationales: ONLY keys listed in missed_keys or wrong_keys.
   For each, explain WHY that option is wrong or why it should have been chosen,
   citing linked knowledge points and paper facts. Do NOT write filler such as
   "should have been selected", "should not have been selected", "correct option", or "incorrect option".
2. pdf_rationales: one substantive note per option letter that appears in the question
   (A–E for multi-select, A–D for single-choice, A–G for logic).
   Include brief correct-option notes here for study reports; keep issue_rationales focused on errors only.
3. Stay faithful to the provided references and explanation; do not invent facts.
4. Write in the requested output language.

Output JSON:
{
  "questions": [
    {
      "question_id": "Q1",
      "issue_rationales": {"D": "Elbow-region modifications stabilize structure but are not essential under ideal growth conditions per KP-1."},
      "pdf_rationales": {
        "A": "...",
        "B": "...",
        "C": "...",
        "D": "...",
        "E": "..."
      }
    }
  ]
}"""


LOGIC_OPTION_LABELS: dict[str, str] = {
    "A": "Both α and β are correct; α is the cause of β",
    "B": "Both α and β are correct; α is the effect of β (β is the cause)",
    "C": "α is correct, β is incorrect",
    "D": "β is correct, α is incorrect",
    "E": "Both α and β are incorrect",
    "F": "Both α and β are correct, but no causal relationship between them",
    "G": "α and β are mutually exclusive (one correct implies the other is wrong)",
}
