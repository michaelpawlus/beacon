"""Tests for job relevance scoring engine."""


from beacon.research.job_scoring import (
    WEIGHTS,
    _score_keywords,
    _score_location,
    _score_seniority,
    _score_title,
    compute_job_relevance,
)


class TestWeights:
    def test_weights_sum_to_one(self):
        assert abs(sum(WEIGHTS.values()) - 1.0) < 0.001


class TestTitleScoring:
    def test_exact_role_match(self):
        score, reasons = _score_title("Senior Data Engineer")
        assert score == 10.0
        assert any("title_match" in r for r in reasons)

    def test_ml_engineer_match(self):
        score, _ = _score_title("Machine Learning Engineer")
        assert score == 10.0

    def test_analytics_engineer_match(self):
        score, _ = _score_title("Analytics Engineer")
        assert score == 10.0

    def test_partial_data_and_eng(self):
        score, reasons = _score_title("Data Platform Architect")
        assert score >= 5.0

    def test_unrelated_title(self):
        score, _ = _score_title("Office Manager")
        assert score == 0.0

    def test_data_only_partial(self):
        score, reasons = _score_title("Data Coordinator")
        assert 3.0 <= score <= 8.0

    def test_engineering_only_partial(self):
        score, reasons = _score_title("Software Engineer")
        assert score == 3.0

    def test_case_insensitive(self):
        score, _ = _score_title("SENIOR DATA ENGINEER")
        assert score == 10.0


class TestKeywordScoring:
    def test_many_positive_keywords(self):
        desc = "We use python, sql, dbt, spark, airflow, and snowflake daily."
        score, reasons = _score_keywords(desc)
        assert score >= 8.0
        assert any("positive_keywords" in r for r in reasons)

    def test_negative_keywords_penalize(self):
        desc = "This is a sales account executive role."
        score, reasons = _score_keywords(desc)
        assert score < 5.0
        assert any("negative_keywords" in r for r in reasons)

    def test_no_description_neutral(self):
        score, reasons = _score_keywords("")
        assert score == 5.0
        assert "no_description" in reasons

    def test_mixed_keywords(self):
        desc = "Python and SQL for marketing manager role."
        score, _ = _score_keywords(desc)
        assert 0.0 <= score <= 10.0

    def test_single_keyword(self):
        score, _ = _score_keywords("Experience with python required.")
        assert score > 2.0


class TestLocationScoring:
    def test_remote_preferred(self):
        score, reasons = _score_location("Remote")
        assert score == 10.0
        assert any("preferred_location" in r for r in reasons)

    def test_san_francisco(self):
        score, _ = _score_location("San Francisco, CA")
        assert score == 10.0

    def test_non_preferred_location(self):
        score, reasons = _score_location("Mumbai, India")
        assert score == 3.0
        assert "non_preferred_location" in reasons

    def test_no_location_neutral(self):
        score, _ = _score_location("")
        assert score == 5.0

    def test_case_insensitive(self):
        score, _ = _score_location("REMOTE - US")
        assert score == 10.0


class TestSeniorityScoring:
    def test_senior_target(self):
        score, reasons = _score_seniority("Senior Data Engineer")
        assert score == 10.0
        assert any("target_seniority" in r for r in reasons)

    def test_staff_target(self):
        score, _ = _score_seniority("Staff ML Engineer")
        assert score == 10.0

    def test_intern_low_score(self):
        score, reasons = _score_seniority("Data Engineering Intern")
        assert score == 2.0
        assert any("junior_role" in r for r in reasons)

    def test_director_exec(self):
        score, reasons = _score_seniority("Director of Data Engineering")
        assert score == 4.0
        assert any("exec_role" in r for r in reasons)

    def test_no_seniority(self):
        score, _ = _score_seniority("Data Engineer")
        assert score == 6.0


class TestCompositeScore:
    def test_perfect_match(self):
        job = {
            "title": "Senior Data Engineer",
            "description_text": "We use python, sql, dbt, spark, airflow, snowflake, and bigquery.",
            "location": "Remote",
        }
        result = compute_job_relevance(job)
        assert result["score"] >= 9.0
        assert result["title_score"] == 10.0
        assert len(result["reasons"]) > 0

    def test_irrelevant_job(self):
        job = {
            "title": "Office Manager",
            "description_text": "Manage the office, schedule meetings, handle payroll.",
            "location": "Mumbai, India",
        }
        result = compute_job_relevance(job)
        assert result["score"] < 3.0

    def test_score_capped_at_10(self):
        job = {
            "title": "Senior Data Engineer",
            "description_text": " ".join(["python sql dbt spark airflow snowflake bigquery"] * 10),
            "location": "Remote, US",
        }
        result = compute_job_relevance(job)
        assert result["score"] <= 10.0

    def test_empty_job(self):
        result = compute_job_relevance({})
        assert 0.0 <= result["score"] <= 10.0

    def test_returns_all_subscores(self):
        result = compute_job_relevance({"title": "ML Engineer", "location": "NYC"})
        assert "title_score" in result
        assert "keyword_score" in result
        assert "location_score" in result
        assert "seniority_score" in result

    def test_reasons_are_strings(self):
        result = compute_job_relevance({"title": "Data Analyst", "description_text": "sql python"})
        assert all(isinstance(r, str) for r in result["reasons"])
