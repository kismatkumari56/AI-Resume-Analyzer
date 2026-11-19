import io
import json
import os
import uuid
import threading
import webbrowser


from docx.opc.exceptions import PackageNotFoundError
from flask import Flask, render_template, request

from flask import Flask, jsonify, redirect, render_template, request, send_file, session, url_for

from werkzeug.utils import secure_filename
from docx.opc.exceptions import PackageNotFoundError


from analyzer.docx_reader import DocxReadError

from analyzer.pdf_reader import extract_pdf_text
from analyzer.docx_reader import DocxReadError, check_docx_file

from analyzer.resume_extractor import extract_resume_text
from analyzer.ocr import OCRError
from analyzer.section_detector import extract_sections
from analyzer.skills_extractor import extract_skills, get_suggestions
from analyzer.resume_scorer import calculate_resume_score
from analyzer.suggestions import generate_recommendations
from analyzer.keyword_analyzer import analyze_keywords
from analyzer.ats_checker import analyze_ats
from analyzer.job_matcher import match_resume_to_job
from analyzer.report_generator import build_report, build_txt_report
from analyzer.section_quality import analyze_section_quality
from analyzer.project_checker import check_project_descriptions
from analyzer.action_verb_analyzer import analyze_action_verbs
from analyzer.readability_analyzer import analyze_readability
from analyzer.timeline_checker import check_timeline_consistency
from analyzer.credentials_detector import detect_certifications, detect_achievements
from analyzer.validator import (
    ALLOWED_EXTENSIONS,
    MAX_JOB_DESCRIPTION_LENGTH,
    format_error_response,
    validate_report_download,
    validate_resume_upload,
    wants_json_response,
)
from analyzer.duplicate_detector import detect_duplicates
from analyzer.skill_gap_analyzer import analyze_skill_gap, get_supported_roles
from analyzer.roadmap_generator import generate_roadmap, calculate_roadmap_progress
from analyzer.temp_manager import (
    DEFAULT_TEMP_DIR,
    cleanup_stale_temp_files,
    generate_secure_filename,
    get_temp_upload_dir,
    remove_temp_file,
)


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "resume-ai-roadmap-session-key-2026")

app.config["UPLOAD_FOLDER"] = os.environ.get("RESUME_UPLOAD_FOLDER", DEFAULT_TEMP_DIR)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
# The optional job description is cut to this many characters
MAX_JOB_DESCRIPTION_LENGTH = 20000

# Ensure dedicated temporary upload directory exists with restricted permissions
get_temp_upload_dir(app.config["UPLOAD_FOLDER"])
cleanup_stale_temp_files(app.config["UPLOAD_FOLDER"])


@app.route("/")
def home():
    return render_template("index.html", supported_roles=get_supported_roles())


@app.route("/analyze", methods=["POST"])
@app.route("/api/analyze", methods=["POST"])
def analyze():

    filepath = None

    is_valid, file, extension, error_resp = validate_resume_upload(request)
    if not is_valid:
        return error_resp


    file = request.files["resume"]

    if not file.filename:
        return "No file selected."

    original_filename = file.filename
    extension = os.path.splitext(original_filename)[1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        return "Only PDF and DOCX files are allowed."

    # Used in messages shown to the user: "PDF" or "DOCX"
    file_type = extension[1:].upper()

    filename = secure_filename(original_filename)

    if not filename:
        return "Invalid filename."

    unique_filename = f"{uuid.uuid4().hex}_{filename}"

    file_type = extension[1:].upper()
    unique_filename = generate_secure_filename(extension)


    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        unique_filename
    )

    try:
        # Save the uploaded resume.
        file.save(filepath)

        # Extract text using the centralized format dispatcher.
        resume_text = extract_resume_text(filepath)

        if not resume_text.strip():
            msg = f"No readable text found in this {file_type}."
            return format_error_response(
                message=msg,
                status_code=422 if wants_json_response(request) else 200,
                error_code="EMPTY_DOCUMENT_TEXT",
                request=request,
                legacy_200_for_html=True,
            )

        # Detect and organize sections
        resume_sections = extract_sections(resume_text)

        # Detect Certifications and Achievements (Issue #56)
        certifications = detect_certifications(
            resume_text,
            resume_sections=resume_sections
        )
        achievements = detect_achievements(
            resume_text,
            resume_sections=resume_sections
        )

        # Detect Skills
        found_skills = extract_skills(resume_text)

        # Generate Suggestions
        suggestions = get_suggestions(found_skills)

        # Calculate Resume Score
        score_data = calculate_resume_score(resume_text)

        resume_score = score_data["score"]
        score_breakdown = score_data["breakdown"]
        category_details = score_data.get("category_details", {})
        overall_explanation = score_data.get("overall_explanation", "")
        scoring_formula = score_data.get("scoring_formula", "")
        improvement_areas = score_data.get("improvement_areas", [])

        # Section-wise improvement recommendations
        recommendations = generate_recommendations(resume_text)
        # Keyword analysis (optional job description from the form or JSON payload)
        if request.is_json and request.json:
            job_description = request.json.get("job_description", "")
        else:
            job_description = request.form.get("job_description", "")
        job_description = str(job_description or "")[:MAX_JOB_DESCRIPTION_LENGTH]

        keyword_analysis = analyze_keywords(
            resume_text,
            job_description,
            resume_sections=resume_sections
        )
        # ATS Compatibility Analysis
        ats_result = analyze_ats(resume_text, found_skills)

        # Section Quality Analysis (Issue #51)
        section_quality = analyze_section_quality(
            resume_text,
            resume_sections=resume_sections
        )
        # Project Description Quality Analysis (Issue #52)
        project_analysis = check_project_descriptions(
            resume_text,
            resume_sections=resume_sections
        )
        # Action Verb Analysis (Issue #54)
        action_verb_analysis = analyze_action_verbs(
            resume_text,
            resume_sections=resume_sections
        )
        # Readability Analysis (Issue #55)
        readability_analysis = analyze_readability(resume_text)
        # Timeline & Date Consistency Analysis (Issue #53)
        timeline_analysis = check_timeline_consistency(
            resume_text,
            resume_sections=resume_sections
        )

        # Job Description Matching

        job_match = match_resume_to_job(found_skills, job_description)

        job_match = match_resume_to_job(
            found_skills,
            job_description,
            resume_text=resume_text,
            resume_sections=resume_sections
        )

        # Results for the report (sent back by Download buttons)
        # Semantic and Exact Duplicate Content Detection
        duplicate_analysis = detect_duplicates(resume_text)
        # Personalized Skill Gap Analysis against selected or best-matching career role
        target_role = request.form.get("target_role", "").strip() or None
        skill_gap = analyze_skill_gap(found_skills, target_role=target_role)
        # Generate personalized 3-phase improvement roadmap from actual analysis results
        roadmap = generate_roadmap(
            resume_score=resume_score,
            score_breakdown=score_breakdown,
            found_skills=found_skills,
            ats_result=ats_result,
            keyword_analysis=keyword_analysis,
            job_match=job_match,
            recommendations=recommendations,
        )
        session["roadmap"] = roadmap
        session["completed_tasks"] = []

        # Results for the PDF report (sent back by the Download button)
        report = {
            "score": resume_score,
            "breakdown": score_breakdown,
            "skills": found_skills,
            "suggestions": suggestions,
            "section_quality": section_quality,
            "project_analysis": project_analysis,
            "action_verbs": action_verb_analysis,
            "readability": readability_analysis,
            "timeline": timeline_analysis,
            "certifications": certifications,
            "achievements": achievements,
            "recommendations": recommendations,
            "job_match": job_match,
            "duplicate_analysis": duplicate_analysis,
            "skill_gap": skill_gap,
            "roadmap": roadmap,
        }


        print("\n========== RESUME ANALYSIS ==========")
        print("DETECTED SKILLS:", found_skills)
        print("SECTION QUALITY:", section_quality.get("summary", {}).get("overall_quality"))
        print("PROJECTS STATUS:", project_analysis.get("overall_status"))
        print("ACTION VERBS COUNT:", action_verb_analysis.get("total_action_verbs"))
        print("TIMELINE STATUS:", timeline_analysis.get("timeline_status"))
        print("CERTIFICATIONS:", certifications)
        print("ACHIEVEMENTS:", achievements)
        print("RESUME SCORE:", resume_score)
        print("SCORE BREAKDOWN:", score_breakdown)
        print("READABILITY LEVEL:", readability_analysis.get("reading_level"))
        print("AVG SENTENCE LENGTH:", readability_analysis.get("avg_sentence_length"))
        print("DUPLICATE STATEMENTS DETECTED:", duplicate_analysis.get("total_duplicates_count"))
        print("TARGET ROLE:", skill_gap.get("target_role"))
        print("SKILL GAP MATCH:", f"{skill_gap.get('match_percentage')}% ({skill_gap.get('readiness_level')})")
        print("ROADMAP TASKS:", roadmap.get("total_tasks"))
        if job_match.get("has_job_description"):
            print("JOB MATCH SCORE:", job_match.get("match_percentage"))
            if job_match.get("semantic_match_percentage") is not None:
                print("SEMANTIC SIMILARITY:", job_match.get("semantic_match_percentage"))
        print("=====================================\n")

        # API JSON response for API clients
        if wants_json_response(request):
            return jsonify({
                "status": "success",
                "score": resume_score,
                "score_breakdown": score_breakdown,
                "skills": found_skills,
                "skill_count": len(found_skills),
                "suggestions": suggestions,
                "recommendations": recommendations,
                "ats_result": ats_result,
                "job_match": job_match,
                "keyword_analysis": keyword_analysis,
                "resume_sections": resume_sections,
                "report": report,
            }), 200

        # Display Results
        return render_template(
            "result.html",
            found_skills=found_skills,
            suggestions=suggestions,
            skill_count=len(found_skills),
            resume_text=resume_text,
            resume_score=resume_score,
            score_breakdown=score_breakdown,

            category_details=category_details,
            overall_explanation=overall_explanation,
            scoring_formula=scoring_formula,
            improvement_areas=improvement_areas,

            recommendations=recommendations,
            keyword_analysis=keyword_analysis,
            ats_result=ats_result,
            section_quality=section_quality,
            project_analysis=project_analysis,
            action_verb_analysis=action_verb_analysis,
            readability_analysis=readability_analysis,
            timeline_analysis=timeline_analysis,
            resume_sections=resume_sections,
            certifications=certifications,
            achievements=achievements,
            job_match=job_match,
            duplicate_analysis=duplicate_analysis,
            skill_gap=skill_gap,
            supported_roles=get_supported_roles(),
            selected_role=target_role,
            roadmap=roadmap,
            report_json=json.dumps(report)
        )


    except (DocxReadError, PackageNotFoundError) as error:
        # DocxReadError messages are written for the user, so they are safe
        # to show. PackageNotFoundError comes from python-docx when the
        # uploaded file is not a valid DOCX.
        if isinstance(error, PackageNotFoundError):
            return "This file is not a valid DOCX document."
        return str(error)

    except OCRError as error:
        # OCR errors (e.g. missing tesseract or image read failure) provide clear guidance
        return str(error)
    except PackageNotFoundError:
        return "This file is not a valid DOCX document."

    except DocxReadError as error:
        # The message was written for the user, so it is safe to show
        return format_error_response(
            message=str(error),
            status_code=400,
            error_code="INVALID_DOCX_FILE",
            request=request,
            legacy_200_for_html=True,
        )


    except Exception as error:
        print("Analysis Error:", error)
        if extension == ".docx":
            try:
                check_docx_file(filepath)  # explains fake or oversized DOCX files
            except DocxReadError as docx_error:
                return format_error_response(
                    message=str(docx_error),
                    status_code=400,
                    error_code="INVALID_DOCX_FILE",
                    request=request,
                    legacy_200_for_html=True,
                )
        safe_msg = f"Unable to analyze this {file_type}. Please try another {file_type}."
        return format_error_response(
            message=safe_msg,
            status_code=422 if wants_json_response(request) else 200,
            error_code="ANALYSIS_FAILED",
            request=request,
            legacy_200_for_html=True,
        )

    finally:
        if filepath:
            remove_temp_file(filepath)
        try:
            file.close()
        except (OSError, ValueError):
            pass


@app.route("/download-report", methods=["POST"])
@app.route("/api/download-report", methods=["POST"])
def download_report():

    is_valid, report_dict, error_resp = validate_report_download(request)
    if not is_valid:
        return error_resp

    try:
        pdf_bytes = build_report(report_dict)
    except Exception as error:
        print("Report Error:", error)
        return format_error_response(
            message="Unable to create the report. Please analyze your resume again.",
            status_code=400,
            error_code="REPORT_GENERATION_FAILED",
            request=request,
            legacy_200_for_html=False,
        )

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="resume-analysis-report.pdf"
    )


@app.route("/download-txt-report", methods=["POST"])
@app.route("/api/download-txt-report", methods=["POST"])
def download_txt_report():

    is_valid, report_dict, error_resp = validate_report_download(request)
    if not is_valid:
        return error_resp

    try:
        txt_content = build_txt_report(report_dict)
    except Exception as error:
        print("TXT Report Error:", error)
        return format_error_response(
            message="Unable to create the report. Please analyze your resume again.",
            status_code=400,
            error_code="REPORT_GENERATION_FAILED",
            request=request,
            legacy_200_for_html=False,
        )

    return send_file(
        io.BytesIO(txt_content.encode("utf-8")),
        mimetype="text/plain; charset=utf-8",
        as_attachment=True,
        download_name="resume-analysis-report.txt"
    )


@app.errorhandler(400)
def handle_bad_request(error):
    return format_error_response(
        message="Bad Request: The server could not understand the request.",
        status_code=400,
        error_code="BAD_REQUEST",
        request=request,
        legacy_200_for_html=False,
    )


@app.errorhandler(404)
def handle_not_found(error):
    return format_error_response(
        message="Resource not found.",
        status_code=404,
        error_code="NOT_FOUND",
        request=request,
        legacy_200_for_html=False,
    )


@app.errorhandler(405)
def handle_method_not_allowed(error):
    return format_error_response(
        message="Method not allowed.",
        status_code=405,
        error_code="METHOD_NOT_ALLOWED",
        request=request,
        legacy_200_for_html=False,
    )


@app.errorhandler(413)
def handle_payload_too_large(error):
    return format_error_response(
        message="File size exceeds the 10 MB limit. Please upload a smaller file.",
        status_code=413,
        error_code="FILE_TOO_LARGE",
        request=request,
        legacy_200_for_html=False,
    )


@app.errorhandler(500)
def handle_server_error(error):
    return format_error_response(
        message="An internal server error occurred. Please try again later.",
        status_code=500,
        error_code="INTERNAL_SERVER_ERROR",
        request=request,
        legacy_200_for_html=False,
    )
@app.route("/roadmap", methods=["GET"])
def view_roadmap():
    """View the interactive resume improvement roadmap for the current session."""
    roadmap = session.get("roadmap")
    if not roadmap:
        return redirect("/")

    return render_template("roadmap.html", roadmap=roadmap)


@app.route("/roadmap/toggle", methods=["POST"])
def toggle_roadmap_task():
    """Toggle a roadmap task's completed state and update session progress."""
    roadmap = session.get("roadmap")
    if not roadmap:
        return jsonify({"error": "No roadmap in session"}), 404

    data = request.get_json(silent=True) or request.form
    task_id = data.get("task_id")
    completed = data.get("completed")

    if isinstance(completed, str):
        completed = completed.lower() in ("true", "1", "yes")

    completed_tasks = set(session.get("completed_tasks", []))
    if completed:
        completed_tasks.add(task_id)
    else:
        completed_tasks.discard(task_id)

    session["completed_tasks"] = list(completed_tasks)
    roadmap = calculate_roadmap_progress(roadmap, completed_tasks)
    session["roadmap"] = roadmap

    return jsonify({
        "status": "success",
        "task_id": task_id,
        "completed": completed,
        "completed_tasks": roadmap["completed_tasks"],
        "total_tasks": roadmap["total_tasks"],
        "completion_percentage": roadmap["completion_percentage"],
    })


if __name__ == "__main__":

    url = "http://127.0.0.1:5000"

    threading.Timer(
        1.5,
        lambda: webbrowser.open_new(url)
    ).start()

    app.run(debug=True, use_reloader=False)