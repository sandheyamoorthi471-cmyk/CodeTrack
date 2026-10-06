import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import psycopg
from curl_cffi import requests


def call_leetcode_verifier(submission_id, db_config):
    return verify_leetcode_submission(submission_id, db_config)


def verify_leetcode_submission(submission_id, db_config):
    try:
        with psycopg.connect(**db_config) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        s.id,
                        s.task_id,
                        s.student_id,
                        s.answer,
                        t.platform,
                        t.problem_identifier,
                        t.problem_url,
                        t.assigned_at
                    FROM submissions s
                    JOIN tasks t
                        ON t.id = s.task_id
                    WHERE s.id = %s
                    """,
                    (submission_id,),
                )

                submission = cur.fetchone()

                if not submission:
                    return {
                        "success": False,
                        "message": "Submission not found."
                    }, 404

                (
                    submission_id,
                    task_id,
                    student_id,
                    answer,
                    platform,
                    problem_identifier,
                    problem_url,
                    task_assigned_at,
                ) = submission

                # Check platform
                if not platform or platform.lower() != "leetcode":
                    return {
                        "success": False,
                        "message": "This submission is not a LeetCode submission."
                    }, 400

                # Check problem identifier
                if not problem_identifier:
                    return {
                        "success": False,
                        "message": "LeetCode problem identifier is missing."
                    }, 400

                # Get student's LeetCode username
                cur.execute(
                    """
                    SELECT username
                    FROM student_platforms
                    WHERE student_id = %s
                    AND LOWER(platform) = 'leetcode'
                    LIMIT 1
                    """,
                    (student_id,),
                )

                platform_row = cur.fetchone()

                if not platform_row:
                    return {
                        "success": False,
                        "message": "Student has not connected a LeetCode account."
                    }, 400

                leetcode_username = platform_row[0]

                if not leetcode_username:
                    return {
                        "success": False,
                        "message": "LeetCode username is missing."
                    }, 400

                # Get student membership time
                cur.execute(
                    """
                    SELECT gm.joined_at
                    FROM group_members gm
                    JOIN tasks t
                        ON t.group_id = gm.group_id
                    WHERE t.id = %s
                    AND gm.student_id = %s
                    LIMIT 1
                    """,
                    (task_id, student_id),
                )

                membership_row = cur.fetchone()

                student_joined_at = (
                    membership_row[0]
                    if membership_row
                    else None
                )

                # Determine when student became eligible
                eligibility_time = task_assigned_at

                if (
                    student_joined_at
                    and (
                        eligibility_time is None
                        or student_joined_at > eligibility_time
                    )
                ):
                    eligibility_time = student_joined_at

                if eligibility_time is None:
                    eligibility_time = datetime.min.replace(
                        tzinfo=ZoneInfo("Asia/Kolkata")
                    )
                elif eligibility_time.tzinfo is None:
                    eligibility_time = eligibility_time.replace(
                        tzinfo=ZoneInfo("Asia/Kolkata")
                    )

                # Extract LeetCode submission ID
                answer_text = answer or ""

                submission_match = re.search(
                    r"leetcode\.com/submissions/(\d+)",
                    answer_text,
                    re.IGNORECASE,
                )

                if not submission_match:
                    submission_match = re.search(
                        r"/submissions/(\d+)",
                        answer_text,
                        re.IGNORECASE,
                    )

                if not submission_match:
                    return {
                        "success": False,
                        "message": (
                            "Could not find a valid LeetCode submission "
                            "ID in the submitted URL."
                        )
                    }, 400

                external_submission_id = submission_match.group(1)

                # LeetCode GraphQL query
                graphql_query = """
                query recentAcSubmissions($username: String!, $limit: Int!) {
                    recentAcSubmissionList(
                        username: $username
                        limit: $limit
                    ) {
                        id
                        title
                        titleSlug
                        timestamp
                    }
                }
                """

                graphql_variables = {
                    "username": leetcode_username,
                    "limit": 100,
                }

                response = requests.post(
                    "https://leetcode.com/graphql",
                    json={
                        "query": graphql_query,
                        "variables": graphql_variables,
                    },
                    impersonate="chrome",
                    timeout=20,
                )

                response.raise_for_status()

                result = response.json()

                recent_submissions = (
                    result.get("data", {})
                    .get("recentAcSubmissionList", [])
                )

                # Find exact submission ID
                matched_submission = None

                for item in recent_submissions:
                    if str(item.get("id")) == str(external_submission_id):
                        matched_submission = item
                        break

                if not matched_submission:
                    return {
                        "success": False,
                        "message": (
                            "The LeetCode submission was not found "
                            "in the student's recent accepted submissions."
                        )
                    }, 400

                # Get submitted problem slug
                submitted_title_slug = (
                    matched_submission.get("titleSlug") or ""
                ).strip().lower()

                # Get expected problem slug
                expected_identifier = (
                    str(problem_identifier).strip().lower()
                )

                expected_slug = expected_identifier

                if "leetcode.com" in expected_slug:
                    parsed = urlparse(expected_slug)

                    parts = [
                        part
                        for part in parsed.path.split("/")
                        if part
                    ]

                    if "problems" in parts:
                        problem_index = parts.index("problems")

                        if problem_index + 1 < len(parts):
                            expected_slug = parts[
                                problem_index + 1
                            ]

                expected_slug = expected_slug.split("?")[0]
                expected_slug = expected_slug.split("#")[0]
                expected_slug = expected_slug.strip("/").lower()

                # Check problem match
                if submitted_title_slug != expected_slug:
                    return {
                        "success": False,
                        "message": (
                            "The submitted LeetCode problem does not "
                            "match the assigned task."
                        ),
                        "expected": expected_slug,
                        "found": submitted_title_slug,
                    }, 400

                # Check timestamp
                timestamp_value = matched_submission.get("timestamp")

                if not timestamp_value:
                    return {
                        "success": False,
                        "message": "LeetCode submission timestamp is missing."
                    }, 400

                submission_time = datetime.fromtimestamp(
                    int(timestamp_value),
                    tz=timezone.utc,
                )

                eligibility_time_utc = (
                    eligibility_time.astimezone(timezone.utc)
                )

                if submission_time <= eligibility_time_utc:
                    return {
                        "success": False,
                        "message": (
                            "The LeetCode submission was made before "
                            "the task became available."
                        )
                    }, 400

                # Prevent reuse of same LeetCode submission
                cur.execute(
                    """
                    SELECT id
                    FROM submissions
                    WHERE external_submission_id = %s
                    AND id <> %s
                    LIMIT 1
                    """,
                    (
                        external_submission_id,
                        submission_id,
                    ),
                )

                reused_submission = cur.fetchone()

                if reused_submission:
                    return {
                        "success": False,
                        "message": (
                            "This LeetCode submission has already "
                            "been used for another task."
                        )
                    }, 400

                # Approve submission
                cur.execute(
                    """
                    UPDATE submissions
                    SET
                        status = 'approved',
                        external_submission_id = %s
                    WHERE id = %s
                    """,
                    (
                        external_submission_id,
                        submission_id,
                    ),
                )

                # Check whether points already exist
                cur.execute(
                    """
                    SELECT id
                    FROM student_points
                    WHERE submission_id = %s
                    LIMIT 1
                    """,
                    (submission_id,),
                )

                existing_points = cur.fetchone()

                # Award 100 points only once
                if not existing_points:
                    cur.execute(
                        """
                        INSERT INTO student_points (
                            student_id,
                            submission_id,
                            points,
                            reason
                        )
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            student_id,
                            submission_id,
                            100,
                            "Verified LeetCode submission",
                        ),
                    )

                conn.commit()

                return {
                    "success": True,
                    "message": "LeetCode submission verified successfully.",
                    "submission_id": submission_id,
                    "leetcode_submission_id": external_submission_id,
                    "problem": submitted_title_slug,
                    "points": 100,
                    "status": "approved",
                }, 200

    except requests.RequestException as error:
        return {
            "success": False,
            "message": "Could not connect to LeetCode.",
            "error": str(error),
        }, 502

    except Exception as error:
        return {
            "success": False,
            "message": "LeetCode verification failed.",
            "error": str(error),
        }, 500


def run_batch_leetcode_verification(db_config):
    checked = 0
    newly_verified = 0

    try:
        with psycopg.connect(**db_config) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT id
                    FROM submissions
                    WHERE LOWER(status) <> 'approved'
                    AND EXISTS (
                        SELECT 1
                        FROM tasks t
                        WHERE t.id = submissions.task_id
                        AND LOWER(t.platform) = 'leetcode'
                    )
                    ORDER BY id
                    """
                )

                submissions = cur.fetchall()

        for row in submissions:
            submission_id = row[0]
            checked += 1

            data, status_code = call_leetcode_verifier(
                submission_id,
                db_config,
            )

            if (
                status_code == 200
                and data.get("success") is True
            ):
                newly_verified += 1

        print(
            f"[Batch LeetCode Verification] "
            f"checked {checked} pending submissions across all students, "
            f"{newly_verified} newly verified."
        )

        return {
            "success": True,
            "checked": checked,
            "newly_verified": newly_verified,
        }

    except Exception as error:
        print(
            "[Batch LeetCode Verification] Error:",
            error,
        )

        return {
            "success": False,
            "checked": checked,
            "newly_verified": newly_verified,
            "error": str(error),
        }