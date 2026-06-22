"""Streamlit web UI for the biomedical literature learning workflow."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import json
import os

import streamlit as st
from dotenv import load_dotenv

_ENV_FILE = _PROJECT_ROOT / ".env"
load_dotenv(_ENV_FILE, override=False)

from bioquestion import __version__
from bioquestion.extract import extract_knowledge, save_knowledge
from bioquestion.grade import grade_answers, save_report
from bioquestion.i18n import LANGUAGES, build_translation_map
from bioquestion.llm import LLMClient
from bioquestion.pdf_reader import load_uploaded_document
from bioquestion.providers import LLMProvider, PROVIDER_SPECS, provider_is_configured
from bioquestion.quiz import generate_quiz, save_quiz
from bioquestion.report_note import build_study_report_bundle
from bioquestion.schemas import (
    GradingReport,
    KnowledgeExtractionResult,
    MultipleChoiceQuestion,
    QuizMode,
    QuizResult,
    ShortAnswerQuestion,
    UserAnswer,
    UserAnswerSheet,
)
from bioquestion.stats import (
    LEADERBOARD_API_PORT,
    append_score_record,
    build_recent_score_trend,
    leaderboard_api_url,
    load_score_records,
    personal_stats_summary,
)
from bioquestion.ui_strings import UI_STRINGS

STEP_KEYS = [
    "step.literature_input",
    "step.knowledge_points",
    "step.quiz",
    "step.grading",
]

CATEGORY_KEYS = {
    "entity": "category.entity",
    "mechanism": "category.mechanism",
    "finding": "category.finding",
}

OUTPUT_DIR = Path("output")


def t(key: str, **kwargs: object) -> str:
    catalog = st.session_state.get("ui_strings") or UI_STRINGS
    text = catalog.get(key, UI_STRINGS.get(key, key))
    if kwargs:
        return text.format(**kwargs)
    return text


def _init_session() -> None:
    defaults = {
        "step": 0,
        "source_text": "",
        "pdf_meta": None,
        "knowledge": None,
        "quiz": None,
        "report": None,
        "answer_sheet": None,
        "source_label": "input.pasted_label",
        "answers_submitted": False,
        "quiz_mode": QuizMode.NORMAL.value,
        "user_display_name": "",
        "ui_lang": "en",
        "ui_strings": dict(UI_STRINGS),
        "llm_provider": LLMProvider.GOOGLE.value,
        "llm_model": os.getenv("GOOGLE_MODEL", "gemini-3.5-flash"),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _sync_translations(lang: str) -> None:
    if st.session_state.get("_ui_lang_loaded") == lang and st.session_state.get("ui_strings"):
        return
    with st.spinner("Loading interface translation…" if lang != "en" else None):
        st.session_state.ui_strings = build_translation_map(lang)
        st.session_state._ui_lang_loaded = lang


def _go_to_step(step: int) -> None:
    st.session_state.step = step
    st.rerun()


def _get_llm() -> LLMClient:
    return LLMClient(
        provider=st.session_state.llm_provider,
        model=st.session_state.llm_model or None,
    )


def _persist_outputs(
    knowledge: KnowledgeExtractionResult | None,
    quiz: QuizResult | None,
    report: GradingReport | None,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if knowledge:
        save_knowledge(knowledge, OUTPUT_DIR / "knowledge.json")
    if quiz:
        save_quiz(quiz, OUTPUT_DIR / "quiz.json")
    if report:
        save_report(report, OUTPUT_DIR / "grading.json")


def _render_sidebar() -> None:
    st.sidebar.title(t("app.title"))
    st.sidebar.caption(f"{t('app.tagline')} · v{__version__}")

    st.sidebar.divider()
    st.sidebar.caption(t("sidebar.language"))
    lang_options = list(LANGUAGES.keys())
    lang_labels = [LANGUAGES[code] for code in lang_options]
    current_lang = st.session_state.get("ui_lang", "en")
    lang_index = lang_options.index(current_lang) if current_lang in lang_options else 0
    selected_lang = st.sidebar.selectbox(
        t("sidebar.language"),
        options=lang_options,
        index=lang_index,
        format_func=lambda code: LANGUAGES[code],
        label_visibility="collapsed",
    )
    st.sidebar.caption(t("sidebar.language_hint"))
    if selected_lang != st.session_state.ui_lang:
        st.session_state.ui_lang = selected_lang
        st.session_state.pop("_ui_lang_loaded", None)
        st.rerun()
    _sync_translations(selected_lang)

    st.sidebar.divider()
    st.sidebar.caption(t("sidebar.llm_provider"))
    provider_options = [p.value for p in LLMProvider]
    provider_labels = {p.value: PROVIDER_SPECS[p].label for p in LLMProvider}
    current_provider = st.session_state.get("llm_provider", LLMProvider.GOOGLE.value)
    provider_index = (
        provider_options.index(current_provider)
        if current_provider in provider_options
        else 0
    )
    selected_provider = st.sidebar.selectbox(
        t("sidebar.llm_provider"),
        options=provider_options,
        index=provider_index,
        format_func=lambda value: provider_labels[value],
        label_visibility="collapsed",
    )
    spec = PROVIDER_SPECS[LLMProvider(selected_provider)]
    default_model = os.getenv(spec.model_env, spec.default_model)
    if selected_provider != st.session_state.llm_provider:
        st.session_state.llm_provider = selected_provider
        st.session_state.llm_model = default_model
    model = st.sidebar.text_input(t("sidebar.model"), value=st.session_state.llm_model or default_model)
    st.session_state.llm_model = model.strip() or default_model

    if provider_is_configured(selected_provider):
        st.sidebar.success(t("sidebar.api_configured", provider=spec.label))
    else:
        st.sidebar.error(t("sidebar.api_missing", provider=spec.label))
        st.sidebar.caption(
            t("sidebar.env_hint", env_key=spec.api_key_env, env_file=str(_ENV_FILE))
        )

    with st.sidebar.expander(t("sidebar.provider_rules_title"), expanded=False):
        st.markdown(t("sidebar.provider_rules_body"))

    st.sidebar.divider()
    st.sidebar.caption(t("sidebar.profile"))
    user_name = st.sidebar.text_input(
        t("sidebar.display_name"),
        value=st.session_state.get("user_display_name", ""),
        placeholder=t("sidebar.display_name_ph"),
    )
    st.session_state.user_display_name = user_name.strip()

    st.sidebar.divider()
    st.sidebar.caption(t("sidebar.workflow"))
    selected = st.sidebar.radio(
        t("sidebar.workflow"),
        options=list(range(len(STEP_KEYS))),
        format_func=lambda i: f"{i + 1}. {t(STEP_KEYS[i])}",
        index=st.session_state.step,
        label_visibility="collapsed",
    )
    if selected != st.session_state.step:
        st.session_state.step = selected
        st.rerun()


def _step_input() -> None:
    st.header(t("input.header", step=t(STEP_KEYS[0])))
    st.write(t("input.intro"))

    uploaded = st.file_uploader(t("input.upload"), type=["txt", "pdf"])
    use_ocr = st.checkbox(t("input.ocr"), value=True)
    pasted = st.text_area(
        t("input.paste"),
        value=st.session_state.source_text,
        height=280,
        placeholder=t("input.paste_ph"),
    )

    if uploaded is not None:
        if uploaded.type == "application/pdf" or uploaded.name.lower().endswith(".pdf"):
            progress = st.progress(0.0, text=t("input.parsing_pdf"))
            status = st.empty()

            def on_progress(current: int, total: int, mode: str) -> None:
                label = t("input.ocr_label") if mode == "ocr" else t("input.text_label")
                progress.progress(
                    current / total,
                    text=t("input.page_progress", label=label, current=current, total=total),
                )
                status.caption(
                    t("input.processing_page", current=current, label=label)
                )

            try:
                text, pdf_meta = load_uploaded_document(
                    uploaded.name,
                    uploaded.getvalue(),
                    use_ocr=use_ocr,
                    on_progress=on_progress,
                )
            except Exception as exc:
                progress.empty()
                status.empty()
                st.error(t("input.pdf_failed", error=exc))
                return

            progress.progress(1.0, text=t("input.pdf_done"))
            status.empty()
            st.session_state.pdf_meta = pdf_meta
            pasted = text
            st.success(pdf_meta.summary if pdf_meta else t("input.pdf_done"))
            with st.expander(t("input.preview"), expanded=False):
                preview = text[:3000] + ("…" if len(text) > 3000 else "")
                st.text(preview)
        else:
            st.session_state.pdf_meta = None
            pasted = uploaded.read().decode("utf-8", errors="replace")

    col1, col2 = st.columns(2)
    with col1:
        extract_btn = st.button(t("input.extract_btn"), type="primary", use_container_width=True)
    with col2:
        reset_btn = st.button(t("input.reset_btn"), use_container_width=True)

    if reset_btn:
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    if extract_btn:
        text = pasted.strip()
        if not text:
            st.warning(t("input.empty_warning"))
            return
        with st.spinner(t("input.extracting")):
            try:
                knowledge = extract_knowledge(text, _get_llm())
            except Exception as exc:
                st.error(t("input.extract_failed", error=exc))
                return

        st.session_state.source_text = text
        if uploaded is not None:
            st.session_state.source_label = uploaded.name
        else:
            st.session_state.source_label = t("input.pasted_label")
        st.session_state.knowledge = knowledge
        st.session_state.quiz = None
        st.session_state.report = None
        st.session_state.answer_sheet = None
        st.session_state.answers_submitted = False
        _persist_outputs(knowledge, None, None)

        if not knowledge.has_substantive_content:
            st.warning(t("input.no_kp"))
            return

        st.session_state.step = 1
        st.rerun()


def _step_knowledge() -> None:
    st.header(t("knowledge.header", step=t(STEP_KEYS[1])))
    knowledge: KnowledgeExtractionResult | None = st.session_state.knowledge
    if not knowledge:
        st.info(t("knowledge.need_extract"))
        if st.button(t("common.back_literature")):
            _go_to_step(0)
        return

    if not knowledge.has_substantive_content:
        st.warning(t("input.no_kp"))
        if knowledge.summary:
            st.write(knowledge.summary)
        return

    st.subheader(t("knowledge.summary"))
    st.info(knowledge.summary)

    if knowledge.entities:
        st.subheader(t("knowledge.entities"))
        st.write(", ".join(knowledge.entities))

    st.subheader(t("knowledge.points"))
    for kp in knowledge.knowledge_points:
        label = t(CATEGORY_KEYS.get(kp.category.value, kp.category.value))
        with st.expander(f"**{kp.id}** · {label} · {kp.title}", expanded=False):
            st.markdown(kp.content)
            st.caption(t("knowledge.source_quote", quote=kp.source_quote))

    st.divider()
    st.caption(t("knowledge.mode_hint"))
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button(t("common.back")):
            _go_to_step(0)
    with col2:
        generate_btn = st.button(t("knowledge.generate_quiz"), type="primary", use_container_width=True)
    with col3:
        ez_btn = st.button(t("knowledge.generate_ez"), use_container_width=True)

    if generate_btn or ez_btn:
        mode = QuizMode.EZ if ez_btn else QuizMode.NORMAL
        spinner_text = t("knowledge.generating_ez") if mode == QuizMode.EZ else t("knowledge.generating_normal")
        with st.spinner(spinner_text):
            try:
                quiz = generate_quiz(knowledge, _get_llm(), mode=mode)
            except Exception as exc:
                st.error(t("knowledge.quiz_failed", error=exc))
                return
        st.session_state.quiz = quiz
        st.session_state.quiz_mode = mode.value
        st.session_state.report = None
        st.session_state.answers_submitted = False
        _persist_outputs(knowledge, quiz, None)
        st.session_state.step = 2
        st.rerun()


def _step_quiz() -> None:
    st.header(t("quiz.header", step=t(STEP_KEYS[2])))
    quiz: QuizResult | None = st.session_state.quiz
    if not quiz:
        st.info(t("quiz.need_generate"))
        if st.button(t("common.back_knowledge")):
            _go_to_step(1)
        return

    is_ez = quiz.mode == QuizMode.EZ
    st.caption(t("quiz.ez_caption") if is_ez else t("quiz.normal_caption"))
    answers: list[UserAnswer] = []

    for q in quiz.questions:
        st.markdown(f"### {q.id}")
        if isinstance(q, MultipleChoiceQuestion):
            st.markdown(q.stem)
            option_keys = sorted(q.options.keys())
            if is_ez:
                selected_key = st.radio(
                    t("quiz.select_one"),
                    options=option_keys,
                    format_func=lambda key: f"{key}. {q.options[key]}",
                    key=f"mc_{q.id}",
                    label_visibility="collapsed",
                )
                answers.append(UserAnswer(question_id=q.id, answer=[selected_key]))
            else:
                option_labels = [f"{k}. {q.options[k]}" for k in option_keys]
                label_to_key = {f"{k}. {q.options[k]}": k for k in option_keys}
                selected_labels = st.multiselect(
                    t("quiz.select_many"),
                    options=option_labels,
                    key=f"mc_{q.id}",
                    label_visibility="collapsed",
                )
                selected = sorted(label_to_key[label] for label in selected_labels)
                answers.append(UserAnswer(question_id=q.id, answer=selected))
        elif isinstance(q, ShortAnswerQuestion):
            st.markdown(q.stem)
            text = st.text_area(
                t("quiz.your_answer"),
                key=f"sa_{q.id}",
                height=120,
                label_visibility="collapsed",
                placeholder=t("quiz.answer_ph"),
            )
            answers.append(UserAnswer(question_id=q.id, answer=text))

        st.divider()

    col1, col2 = st.columns(2)
    with col1:
        if st.button(t("common.back")):
            _go_to_step(1)
    with col2:
        submit_btn = st.button(t("quiz.submit"), type="primary", use_container_width=True)

    if submit_btn:
        empty_mc = [
            a.question_id
            for a in answers
            if isinstance(a.answer, list) and len(a.answer) == 0
        ]
        empty_sa = [
            a.question_id
            for a in answers
            if isinstance(a.answer, str) and not a.answer.strip()
        ]
        if empty_mc or empty_sa:
            st.warning(t("quiz.unanswered", ids=", ".join(empty_mc + empty_sa)))
            return

        sheet = UserAnswerSheet(answers=answers)
        with st.spinner(t("quiz.grading")):
            try:
                report = grade_answers(quiz, sheet, _get_llm())
            except Exception as exc:
                st.error(t("quiz.grade_failed", error=exc))
                return

        st.session_state.report = report
        st.session_state.answer_sheet = sheet
        st.session_state.answers_submitted = True
        answers_path = OUTPUT_DIR / "answers.json"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        answers_path.write_text(
            json.dumps(sheet.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _persist_outputs(st.session_state.knowledge, quiz, report)
        if report.scoring_enabled:
            append_score_record(
                report,
                source_label=st.session_state.get("source_label", ""),
                user_name=st.session_state.get("user_display_name", ""),
            )
        st.session_state.step = 3
        st.rerun()


def _render_leaderboard_and_stats() -> None:
    st.subheader(t("grading.leaderboard"))
    st.caption(
        t(
            "grading.leaderboard_caption",
            url=leaderboard_api_url(),
            port=LEADERBOARD_API_PORT,
        )
    )
    with st.container(border=True):
        st.markdown(f"##### {t('grading.leaderboard_window')}")
        st.info(
            t("grading.leaderboard_placeholder", port=LEADERBOARD_API_PORT)
        )
        st.table(
            {
                t("grading.rank"): [t("grading.dash")] * 3,
                t("grading.member"): [t("grading.coming_soon")] * 3,
                t("grading.score"): [t("grading.dash")] * 3,
            }
        )

    st.divider()
    st.subheader(t("grading.personal_stats"))
    records = load_score_records()
    summary = personal_stats_summary(records)

    s1, s2, s3, s4 = st.columns(4)
    s1.metric(t("grading.attempts"), summary["total_submissions"])
    s2.metric(
        t("grading.lifetime_avg"),
        f"{summary['average_score']:.1f}%" if summary["average_score"] is not None else t("grading.dash"),
    )
    s3.metric(
        t("grading.best_score"),
        f"{summary['best_score']:.1f}%" if summary["best_score"] is not None else t("grading.dash"),
    )
    s4.metric(
        t("grading.week_avg"),
        f"{summary['recent_7_day_average']:.1f}%"
        if summary["recent_7_day_average"] is not None
        else t("grading.dash"),
    )

    st.markdown(f"##### {t('grading.trend_title')}")
    st.caption(t("grading.trend_caption"))
    trend = build_recent_score_trend(records)
    chart_rows = [
        {
            t("grading.chart_period"): bucket["label"],
            t("grading.chart_avg"): bucket["average_score"],
        }
        for bucket in trend
        if bucket["average_score"] is not None
    ]
    if chart_rows:
        st.bar_chart(
            chart_rows,
            x=t("grading.chart_period"),
            y=t("grading.chart_avg"),
            height=320,
        )
        with st.expander(t("grading.bucket_details"), expanded=False):
            for bucket in trend:
                avg = bucket["average_score"]
                avg_text = f"{avg:.1f}%" if avg is not None else t("grading.no_data")
                st.write(
                    t(
                        "grading.bucket_line",
                        label=bucket["label"],
                        avg=avg_text,
                        count=bucket["submission_count"],
                    )
                )
    else:
        st.info(t("grading.trend_empty"))


def _step_grading() -> None:
    st.header(t("grading.header", step=t(STEP_KEYS[3])))
    report: GradingReport | None = st.session_state.report
    quiz: QuizResult | None = st.session_state.quiz

    if not report:
        st.info(t("grading.need_submit"))
        _render_leaderboard_and_stats()
        if st.button(t("common.back_quiz")):
            _go_to_step(2)
        return

    scoring_enabled = report.scoring_enabled
    if scoring_enabled:
        st.metric(
            t("grading.total_score"),
            f"{report.total_score:.1f} / {report.max_score:.0f}",
        )
        st.progress(
            report.percentage / 100.0,
            text=t("grading.score_progress", pct=report.percentage),
        )
    else:
        st.info(t("grading.ez_info"))
    st.subheader(t("grading.overall"))
    st.write(report.summary)

    st.subheader(t("grading.details"))
    quiz_map = {q.id: q for q in quiz.questions} if quiz else {}

    for item in report.question_results:
        verdict = t("grading.verdict_ok") if item.is_correct else t("grading.verdict_bad")
        if item.question_type.value == "short_answer" and item.short_answer_detail:
            if item.short_answer_detail.logic_complete:
                verdict = t("grading.verdict_logic_ok")
            else:
                verdict = t("grading.verdict_incomplete")

        title_suffix = (
            t("grading.pts_suffix", score=item.score, max=item.max_score)
            if scoring_enabled and item.max_score > 0
            else ""
        )
        with st.expander(f"{item.question_id}  {verdict}  {title_suffix}".strip(), expanded=False):
            q = quiz_map.get(item.question_id)
            if q:
                st.markdown(t("grading.question", stem=q.stem))

            if item.choice_detail and scoring_enabled:
                d = item.choice_detail
                c1, c2, c3 = st.columns(3)
                c1.write(
                    t(
                        "grading.your_answer",
                        answer=", ".join(d.user_answers) or t("grading.empty_answer"),
                    )
                )
                c2.write(t("grading.correct_answer", answer=", ".join(d.correct_answers)))
                if d.missed:
                    c3.error(t("grading.missed", items=", ".join(d.missed)))
                if d.extra:
                    c3.warning(t("grading.extra", items=", ".join(d.extra)))
                if d.missed and len(d.missed) > 2:
                    st.error(t("grading.missed_zero", items=", ".join(d.missed)))
                elif d.missed and len(d.missed) == 2 and d.wrong:
                    st.error(
                        t(
                            "grading.two_miss_wrong",
                            missed=", ".join(d.missed),
                            wrong=", ".join(d.wrong),
                        )
                    )
                elif d.missed and len(d.missed) == 2:
                    st.warning(t("grading.two_miss_cap", items=", ".join(d.missed)))
                elif d.wrong and len(d.wrong) >= 2:
                    st.error(t("grading.two_wrong_zero", items=", ".join(d.wrong)))
                elif d.wrong:
                    c3.error(t("grading.wrong_penalty", items=", ".join(d.wrong)))
            elif item.choice_detail:
                d = item.choice_detail
                c1, c2 = st.columns(2)
                c1.write(
                    t(
                        "grading.your_answer",
                        answer=", ".join(d.user_answers) or t("grading.empty_answer"),
                    )
                )
                c2.write(t("grading.correct_answer", answer=", ".join(d.correct_answers)))
                if d.missed:
                    st.warning(t("grading.missed", items=", ".join(d.missed)))
                if d.wrong:
                    st.error(t("grading.incorrect", items=", ".join(d.wrong)))

            if item.short_answer_detail:
                d = item.short_answer_detail
                if d.matched_keywords:
                    st.success(t("grading.matched_kw", items=", ".join(d.matched_keywords)))
                if d.missing_keywords:
                    st.warning(t("grading.missing_kw", items=", ".join(d.missing_keywords)))
                if d.feedback:
                    st.info(d.feedback)
                if isinstance(q, ShortAnswerQuestion):
                    with st.popover(t("grading.view_model")):
                        st.write(q.standard_answer)
                        st.caption(t("grading.grading_kw", items=", ".join(q.grading_keywords)))

            st.markdown(t("grading.explanation"))
            st.write(item.explanation)
            if item.references:
                for ref in item.references:
                    st.caption(f"[{ref.knowledge_point_id}] {ref.source_quote}")

    st.divider()
    _render_leaderboard_and_stats()

    st.divider()
    st.subheader(t("grading.download_report"))
    st.caption(t("grading.download_caption"))

    answer_sheet: UserAnswerSheet | None = st.session_state.get("answer_sheet")
    if answer_sheet is None:
        answers_path = OUTPUT_DIR / "answers.json"
        if answers_path.exists():
            answer_sheet = UserAnswerSheet.model_validate(
                json.loads(answers_path.read_text(encoding="utf-8"))
            )

    knowledge: KnowledgeExtractionResult | None = st.session_state.get("knowledge")
    source_label = st.session_state.get("source_label", t("input.pasted_label"))

    try:
        bundle = build_study_report_bundle(
            report,
            quiz,
            knowledge,
            answer_sheet,
            source_label=source_label,
        )
    except Exception as exc:
        st.error(t("grading.report_failed", error=exc))
        bundle = None

    if bundle:
        stem = bundle["filename_stem"]
        with st.expander(t("grading.preview_md"), expanded=False):
            st.markdown(bundle["markdown"][:12000])
            if len(bundle["markdown"]) > 12000:
                st.caption(t("grading.preview_truncated"))

        dl1, dl2, dl3 = st.columns(3)
        with dl1:
            st.download_button(
                t("grading.download_pdf"),
                data=bundle["pdf_bytes"],
                file_name=f"{stem}.pdf",
                mime="application/pdf",
                use_container_width=True,
                type="primary",
            )
        with dl2:
            st.download_button(
                t("grading.download_md"),
                data=bundle["markdown"],
                file_name=f"{stem}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with dl3:
            st.download_button(
                t("grading.download_json"),
                data=json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
                file_name=f"{stem}.json",
                mime="application/json",
                use_container_width=True,
            )

    st.divider()
    if st.button(t("common.back_quiz")):
        _go_to_step(2)


def main() -> None:
    _init_session()
    st.set_page_config(
        page_title=UI_STRINGS["app.page_title"],
        page_icon="🧬",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _render_sidebar()

    step = st.session_state.step
    if step == 0:
        _step_input()
    elif step == 1:
        _step_knowledge()
    elif step == 2:
        _step_quiz()
    else:
        _step_grading()


if __name__ == "__main__":
    main()
