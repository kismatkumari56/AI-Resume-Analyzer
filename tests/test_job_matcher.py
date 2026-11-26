import unittest

from analyzer.job_matcher import (
    extract_job_skills,
    match_resume_to_job,
    generate_missing_skill_suggestions,
    JOB_SKILLS,
    SKILL_ALIASES,
)


class TestJobMatcher(unittest.TestCase):

    def test_normal_job_description_keyword_extraction(self):
        jd = """
        We are seeking a Backend Developer.
        Requirements:
        - Strong proficiency in Python, Flask, and SQL.
        - Experience with Docker, Git, and REST API.
        """
        extracted = extract_job_skills(jd)
        self.assertIn("Python", extracted)
        self.assertIn("Flask", extracted)
        self.assertIn("SQL", extracted)
        self.assertIn("Docker", extracted)
        self.assertIn("Git", extracted)
        self.assertIn("REST API", extracted)

    def test_case_insensitive_matching(self):
        jd = "Looking for someone skilled in python, FLASK, and Sql."
        extracted = extract_job_skills(jd)
        self.assertEqual(set(extracted), {"Python", "Flask", "SQL"})

    def test_matching_skills(self):
        resume_skills = ["Python", "Flask", "SQL"]
        jd = "Requirements: Python, Flask, SQL, Docker"
        result = match_resume_to_job(resume_skills, jd)
        self.assertEqual(set(result["matching_skills"]), {"Python", "Flask", "SQL"})
        self.assertEqual(result["total_matching"], 3)

    def test_missing_skills(self):
        resume_skills = ["Python"]
        jd = "Requirements: Python, Docker, Kubernetes"
        result = match_resume_to_job(resume_skills, jd)
        self.assertEqual(set(result["missing_skills"]), {"Docker", "Kubernetes"})
        self.assertEqual(result["matching_skills"], ["Python"])

    def test_partial_skill_overlap(self):
        # 3 out of 5 required match = 60%
        resume_skills = ["Python", "Flask", "SQL", "Java"]
        jd = "Requirements: Python, Flask, SQL, Docker, Git"
        result = match_resume_to_job(resume_skills, jd)
        self.assertEqual(set(result["matching_skills"]), {"Python", "Flask", "SQL"})
        self.assertEqual(set(result["missing_skills"]), {"Docker", "Git"})
        self.assertEqual(result["total_required"], 5)
        self.assertEqual(result["total_matching"], 3)
        self.assertEqual(result["match_percentage"], 60)

    def test_no_matching_skills(self):
        resume_skills = ["C++", "Rust"]
        jd = "Required: Python, Flask, Django"
        result = match_resume_to_job(resume_skills, jd)
        self.assertEqual(result["matching_skills"], [])
        self.assertEqual(set(result["missing_skills"]), {"Python", "Flask", "Django"})
        self.assertEqual(result["match_percentage"], 0)
        self.assertEqual(result["total_matching"], 0)

    def test_all_skills_matching(self):
        resume_skills = ["Python", "SQL", "Docker", "Git"]
        jd = "Requirements: Python, SQL"
        result = match_resume_to_job(resume_skills, jd)
        self.assertEqual(set(result["matching_skills"]), {"Python", "SQL"})
        self.assertEqual(result["missing_skills"], [])
        self.assertEqual(result["match_percentage"], 100)
        self.assertEqual(result["total_matching"], 2)
        self.assertEqual(result["total_required"], 2)

    def test_duplicate_keywords_do_not_inflate_score(self):
        resume_skills = ["Python", "Python", "Flask"]
        jd = "Python Python Python, Flask Flask, SQL"
        result = match_resume_to_job(resume_skills, jd)
        # Unique required: Python, Flask, SQL (3)
        # Matching: Python, Flask (2) -> 67%
        self.assertEqual(result["total_required"], 3)
        self.assertEqual(result["total_matching"], 2)
        self.assertEqual(result["match_percentage"], 67)

    def test_skill_aliases(self):
        # JD contains aliases like k8s, postgres, js
        jd = "Need experience in k8s, postgres, and js."
        extracted = extract_job_skills(jd)
        self.assertIn("Kubernetes", extracted)
        self.assertIn("PostgreSQL", extracted)
        self.assertIn("JavaScript", extracted)

        # Resume has canonical names, JD has aliases
        resume_skills = ["Kubernetes", "PostgreSQL", "JavaScript"]
        result = match_resume_to_job(resume_skills, jd)
        self.assertEqual(result["match_percentage"], 100)

    def test_empty_job_description(self):
        for empty_jd in ["", None, "   \n\t  "]:
            result = match_resume_to_job(["Python"], empty_jd)
            self.assertFalse(result["has_job_description"])
            self.assertEqual(result["matching_skills"], [])
            self.assertEqual(result["missing_skills"], [])
            self.assertEqual(result["required_skills"], [])
            self.assertEqual(result["match_percentage"], 0)
            self.assertEqual(result["total_required"], 0)
            self.assertEqual(result["total_matching"], 0)

    def test_whitespace_only_job_description(self):
        result = match_resume_to_job(["Python"], "     \n\n\t  ")
        self.assertFalse(result["has_job_description"])
        self.assertEqual(result["match_percentage"], 0)

    def test_job_description_without_recognizable_skills(self):
        jd = "Looking for a punctual individual who arrives at 9am every day to greet visitors."
        result = match_resume_to_job(["Python"], jd)
        self.assertTrue(result["has_job_description"])
        self.assertEqual(result["required_skills"], [])
        self.assertEqual(result["matching_skills"], [])
        self.assertEqual(result["missing_skills"], [])
        self.assertEqual(result["total_required"], 0)
        self.assertEqual(result["total_matching"], 0)
        self.assertEqual(result["match_percentage"], 0)
        self.assertIn("No recognizable technical skills were detected", result["explanation"])

    def test_empty_resume_skills(self):
        jd = "Requirements: Python, Flask"
        result = match_resume_to_job([], jd)
        self.assertTrue(result["has_job_description"])
        self.assertEqual(result["matching_skills"], [])
        self.assertEqual(set(result["missing_skills"]), {"Python", "Flask"})
        self.assertEqual(result["match_percentage"], 0)
        self.assertEqual(result["total_required"], 2)

    def test_both_inputs_containing_no_skills(self):
        result = match_resume_to_job([], "Hello world, just a general note.")
        self.assertTrue(result["has_job_description"])
        self.assertEqual(result["matching_skills"], [])
        self.assertEqual(result["missing_skills"], [])
        self.assertEqual(result["match_percentage"], 0)
        self.assertEqual(result["total_required"], 0)

    def test_division_by_zero_protection(self):
        # Total required is 0
        result = match_resume_to_job(["Python", "SQL"], "Non-technical description")
        self.assertEqual(result["total_required"], 0)
        self.assertEqual(result["match_percentage"], 0)

    def test_score_calculation_correctness(self):
        # 1 match out of 4 required = 25%
        resume_skills = ["Python"]
        jd = "Need Python, AWS, Docker, Kubernetes"
        result = match_resume_to_job(resume_skills, jd)
        self.assertEqual(result["total_matching"], 1)
        self.assertEqual(result["total_required"], 4)
        self.assertEqual(result["match_percentage"], 25)
        self.assertIn("25%", result["explanation"])

    def test_flask_resume_only_workflow_compatibility(self):
        # When job_description is not passed or empty in Flask analyze
        from app import app
        import io
        from unittest.mock import patch

        client = app.test_client()

        # Mock pdf extraction and analyze_ats
        with patch("app.extract_resume_text", return_value="John Doe\nSkills\nPython, SQL"):
            data = {
                "resume": (io.BytesIO(b"%PDF-1.4 dummy pdf"), "resume.pdf"),
            }
            response = client.post("/analyze", data=data, content_type="multipart/form-data")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Your Resume Analysis", response.data)
            # Should not render the Job Description Match section card when none provided
            self.assertNotIn(b"<h2>Job Description Match</h2>", response.data)

    def test_flask_with_job_description_workflow(self):
        from app import app
        import io
        from unittest.mock import patch

        client = app.test_client()

        with patch("app.extract_resume_text", return_value="John Doe\nSkills\nPython, SQL"):
            data = {
                "resume": (io.BytesIO(b"%PDF-1.4 dummy pdf"), "resume.pdf"),
                "job_description": "We need Python and Docker developer."
            }
            response = client.post("/analyze", data=data, content_type="multipart/form-data")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Job Description Match", response.data)
            self.assertIn(b"Python", response.data)
            self.assertIn(b"Docker", response.data)


    def test_generate_missing_skill_suggestions_basic(self):
        missing = ["Docker", "Kubernetes"]
        suggestions = generate_missing_skill_suggestions(missing)
        self.assertEqual(len(suggestions), 2)
        self.assertTrue(any("Docker" in s for s in suggestions))
        self.assertTrue(any("Kubernetes" in s for s in suggestions))

    def test_generate_missing_skill_suggestions_avoids_present_skills(self):
        missing = ["Python", "Docker", "SQL"]
        resume_skills = ["python", "SQL"]
        suggestions = generate_missing_skill_suggestions(missing, resume_skills=resume_skills)
        self.assertEqual(len(suggestions), 1)
        self.assertIn("Docker", suggestions[0])
        # Present skills must not have suggestions
        for s in suggestions:
            self.assertNotIn("learning Python", s)
            self.assertNotIn("SQL knowledge", s)

    def test_generate_missing_skill_suggestions_avoids_aliases_of_present_skills(self):
        # Resume has alias 'k8s' and 'js'
        missing = ["Kubernetes", "JavaScript", "Docker"]
        resume_skills = ["k8s", "js"]
        suggestions = generate_missing_skill_suggestions(missing, resume_skills=resume_skills)
        self.assertEqual(len(suggestions), 1)
        self.assertIn("Docker", suggestions[0])

    def test_generate_missing_skill_suggestions_avoids_duplicates(self):
        missing = ["Docker", "Docker", "docker", "DOCKER", "AWS", "aws"]
        suggestions = generate_missing_skill_suggestions(missing)
        self.assertEqual(len(suggestions), 2)
        self.assertTrue(any("Docker" in s for s in suggestions))
        self.assertTrue(any("AWS" in s for s in suggestions))

    def test_generate_missing_skill_suggestions_empty(self):
        self.assertEqual(generate_missing_skill_suggestions([]), [])
        self.assertEqual(generate_missing_skill_suggestions(["   ", ""]), [])

    def test_generate_missing_skill_suggestions_fallback_for_unlisted_skill(self):
        missing = ["UncommonCustomFramework"]
        suggestions = generate_missing_skill_suggestions(missing)
        self.assertEqual(len(suggestions), 1)
        self.assertIn("UncommonCustomFramework", suggestions[0])
        self.assertIn("Consider gaining hands-on experience", suggestions[0])

    def test_match_resume_to_job_includes_missing_skill_suggestions(self):
        resume_skills = ["Python"]
        jd = "Requirements: Python, Docker, AWS"
        result = match_resume_to_job(resume_skills, jd)
        self.assertIn("missing_skill_suggestions", result)
        suggestions = result["missing_skill_suggestions"]
        self.assertEqual(len(suggestions), 2)
        # Suggestions must be based on missing skills (Docker, AWS) and not present (Python)
        self.assertTrue(any("Docker" in s for s in suggestions))
        self.assertTrue(any("AWS" in s for s in suggestions))
        self.assertFalse(any("Python" in s for s in suggestions))

    def test_match_resume_to_job_no_missing_skills_empty_suggestions(self):
        resume_skills = ["Python", "Docker"]
        jd = "Requirements: Python, Docker"
        result = match_resume_to_job(resume_skills, jd)
        self.assertEqual(result["missing_skills"], [])
        self.assertEqual(result["missing_skill_suggestions"], [])

    def test_flask_renders_missing_skills_suggestions_section(self):
        from app import app
        import io
        from unittest.mock import patch

        client = app.test_client()

        with patch("app.extract_resume_text", return_value="John Doe\nSkills\nPython, SQL"):
            data = {
                "resume": (io.BytesIO(b"%PDF-1.4 dummy pdf"), "resume.pdf"),
                "job_description": "We need Python, Docker, and Kubernetes engineer."
            }
            response = client.post("/analyze", data=data, content_type="multipart/form-data")
            self.assertEqual(response.status_code, 200)
            # Separate section must be present
            self.assertIn(b"Missing Skills Suggestions", response.data)
            # Suggestions for missing skills (Docker, Kubernetes) must be present
            self.assertIn(b"Docker", response.data)
            self.assertIn(b"Kubernetes", response.data)
            # Existing skill analysis remains unchanged
            self.assertIn(b"Skills Detected", response.data)
            self.assertIn(b"Improvement Suggestions", response.data)

    def test_flask_renders_all_skills_matched_message_in_suggestions_section(self):
        from app import app
        import io
        from unittest.mock import patch

        client = app.test_client()

        with patch("app.extract_resume_text", return_value="John Doe\nSkills\nPython, SQL"):
            data = {
                "resume": (io.BytesIO(b"%PDF-1.4 dummy pdf"), "resume.pdf"),
                "job_description": "We need Python and SQL developer."
            }
            response = client.post("/analyze", data=data, content_type="multipart/form-data")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Missing Skills Suggestions", response.data)
            self.assertIn(b"Great job! Your resume covers all required skills detected for this role.", response.data)

    def test_semantic_skill_accounting_and_partial_credit(self):
        """Verify accounting consistency and partial credit for semantically related skills."""
        # JD requires 3 skills: Python, Machine Learning, AWS
        # Candidate has Python (exact) and Deep Learning (semantic equivalent to Machine Learning)
        resume_skills = ["Python", "Deep Learning"]
        jd = "Requirements: Python, Machine Learning, AWS"
        result = match_resume_to_job(resume_skills, jd)

        self.assertEqual(result["total_required"], 3)
        self.assertEqual(result["exact_matching_count"], 1)
        self.assertEqual(result["semantic_matching_count"], 1)
        self.assertEqual(result["total_matching"], 2)
        self.assertEqual(len(result["missing_skills"]), 1)
        self.assertIn("AWS", result["missing_skills"])

        # Accounting rule: total_matching (exact + semantic) + missing == total_required
        self.assertEqual(
            result["total_matching"] + len(result["missing_skills"]),
            result["total_required"],
        )

        # Partial credit: candidate should get more than 1/3 (33%) due to semantic match
        self.assertGreater(result["keyword_match_percentage"], 33)

    def test_report_includes_semantically_related_skills(self):
        """Verify build_report includes semantically related skills without dropping them."""
        from analyzer.report_generator import build_report

        mock_data = {
            "score": 75,
            "breakdown": {"Technical Skills": 15},
            "skills": ["Python", "Deep Learning"],
            "suggestions": ["Add more cloud skills"],
            "job_match": {
                "has_job_description": True,
                "match_percentage": 70,
                "total_matching": 2,
                "total_required": 3,
                "matching_skills": ["Python"],
                "semantically_related_skills": [
                    {"required_skill": "Machine Learning", "matched_skill": "Deep Learning", "similarity": 85}
                ],
                "missing_skills": ["AWS"],
            },
        }
        pdf_bytes = build_report(mock_data)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 500)



if __name__ == "__main__":
    unittest.main()
