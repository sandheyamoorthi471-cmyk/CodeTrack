import os
import uuid
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
import psycopg
import requests

from werkzeug.utils import secure_filename
from codetracker_ai.ai import ask_codetrack_ai
from codetracker_ai.prompt import build_prompt
load_dotenv()
app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response

# PostgreSQL connection
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "codetrack"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD")
}


@app.route("/")
def home():
    return "CodeTrack Backend is Running!"


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/api/test-db")
def test_db():
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database();")
                database = cur.fetchone()[0]

        return jsonify({
            "success": True,
            "message": "PostgreSQL connected!",
            "database": database
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
@app.route("/api/tasks", methods=["POST"])
def create_task():
    data = request.json

    group_id = data.get("group_id")
    title = data.get("title")
    description = data.get("description")
    task_date = data.get("task_date")

    platform = data.get("platform")
    problem_url = data.get("problem_url")
    problem_identifier = data.get("problem_identifier")

    if not group_id or not title or not task_date:
        return jsonify({
            "success": False,
            "error": "group_id, title and task_date are required"
        }), 400

    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    INSERT INTO tasks (
                        group_id,
                        title,
                        description,
                        task_date,
                        platform,
                        problem_url,
                        problem_identifier
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    group_id,
                    title,
                    description,
                    task_date,
                    platform,
                    problem_url,
                    problem_identifier
                ))

                task_id = cur.fetchone()[0]

                conn.commit()

        return jsonify({
            "success": True,
            "task_id": task_id,
            "message": "Task created successfully!"
        }), 201

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/api/submissions", methods=["POST"])
def create_submission():
    data = request.form if request.form else (request.json or {})

    try:
        task_id = data["task_id"]
        student_id = data["student_id"]
        answer = data.get("answer", "")
        screenshot = request.files.get("screenshot")
        screenshot_url = None

        if screenshot and screenshot.filename:
            extension = os.path.splitext(screenshot.filename)[1].lower()
            if extension not in {".png", ".jpg", ".jpeg", ".webp"}:
                return jsonify({
                    "success": False,
                    "error": "Screenshot must be PNG, JPG, JPEG, or WEBP"
                }), 400

            stored_name = secure_filename(
                f"{student_id}_{task_id}_{uuid.uuid4().hex}{extension}"
            )
            screenshot.save(os.path.join(UPLOAD_FOLDER, stored_name))
            screenshot_url = f"/uploads/{stored_name}"

        # ---------------------------------
        # Create or update submission
        # ---------------------------------
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT id, screenshot_url
                    FROM submissions
                    WHERE task_id = %s
                    AND student_id = %s
                """, (
                    task_id,
                    student_id
                ))

                existing = cur.fetchone()

                if existing:

                    submission_id = existing[0]
                    old_screenshot_url = existing[1]

                    if (
                        old_screenshot_url
                        and old_screenshot_url != screenshot_url
                    ):
                        old_path = os.path.join(
                            UPLOAD_FOLDER,
                            os.path.basename(old_screenshot_url)
                        )
                        if os.path.exists(old_path):
                            os.remove(old_path)

                    cur.execute("""
                        UPDATE submissions
                        SET
                            answer = %s,
                            status = 'submitted',
                            submitted_at = CURRENT_TIMESTAMP,
                            screenshot_url = %s
                        WHERE id = %s
                    """, (
                        answer,
                        screenshot_url,
                        submission_id
                    ))

                else:

                    cur.execute("""
                        INSERT INTO submissions
                        (
                            task_id,
                            student_id,
                            answer,
                            status,
                            screenshot_url
                        )
                        VALUES (
                            %s,
                            %s,
                            %s,
                            'submitted',
                            %s
                        )
                        RETURNING id
                    """, (
                        task_id,
                        student_id,
                        answer,
                        screenshot_url
                    ))

                    submission_id = cur.fetchone()[0]

                # Get task platform
                cur.execute("""
                    SELECT platform
                    FROM tasks
                    WHERE id = %s
                """, (task_id,))

                task = cur.fetchone()

                conn.commit()

        # ---------------------------------
        # Automatic verification
        # ---------------------------------

        verification = {
            "attempted": False,
            "verified": False,
            "message": "Verification not available."
        }

        if task and task[0]:

            platform = task[0].lower()

            if platform == "leetcode":

                verification["attempted"] = True

                try:

                    # Call the verifier function directly (in-process)
                    # instead of making an HTTP request back to this
                    # same server. Avoids extra latency / self-deadlock
                    # risk under the single-threaded dev server.
                    verify_data, verify_status_code = \
                        _call_leetcode_verifier(submission_id)

                    if verify_status_code >= 400:
                        return jsonify({
                            "success": True,
                            "submission_id": submission_id,
                            "status": "pending_review",
                            "verified": False,
                            "fallback_review": bool(screenshot_url),
                            "screenshot_url": screenshot_url,
                            "message": verify_data.get(
                                "message",
                                verify_data.get(
                                    "error",
                                    "Automatic verification unavailable."
                                )
                            )
                        }), 201

                    verification = {
                        "attempted": True,
                        "verified": (
                            verify_status_code == 200
                            and verify_data.get("verified", False)
                        ),
                        "message": verify_data.get(
                            "message",
                            verify_data.get(
                                "error",
                                "Verification completed."
                            )
                        )
                    }

                except Exception as verify_error:

                    print(
                        "Automatic LeetCode verification error:",
                        verify_error
                    )

                    verification = {
                        "attempted": True,
                        "verified": False,
                        "message": (
                            "Submission saved, "
                            "but LeetCode verification "
                            "could not be completed."
                        )
                    }

        # ---------------------------------
        # Response
        # ---------------------------------

        if verification["verified"]:

            return jsonify({
                "success": True,
                "submission_id": submission_id,
                "status": "approved",
                "verified": True,
                "screenshot_url": screenshot_url,
                "message": (
                    "Proof submitted and "
                    "LeetCode verified successfully! 🎉"
                )
            }), 201

        return jsonify({
            "success": True,
            "submission_id": submission_id,
            "status": "submitted",
            "verified": False,
            "screenshot_url": screenshot_url,
            "message": verification["message"]
        }), 201

    except Exception as e:

        print(
            "Submission creation error:",
            e
        )

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
# =========================
# Mentor Task Progress
# =========================
@app.route("/api/mentor/submissions/<int:mentor_id>", methods=["GET"])
def get_mentor_submissions(mentor_id):

    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        t.id AS task_id,
                        t.title AS task_title,
                        t.platform,
                        t.problem_identifier,
                        t.task_date,

                        mg.id AS group_id,
                        mg.name AS group_name,

                        u.id AS student_id,
                        u.name AS student_name,
                        u.email AS student_email,

                        s.id AS submission_id,
                        s.answer,
                        s.status AS submission_status,
                        s.submitted_at

                    FROM tasks t

                    INNER JOIN mentor_groups mg
                        ON t.group_id = mg.id

                    INNER JOIN group_members gm
                        ON mg.id = gm.group_id

                    INNER JOIN users u
                        ON gm.student_id = u.id

                    LEFT JOIN submissions s
                        ON s.task_id = t.id
                        AND s.student_id = u.id

                    WHERE mg.mentor_id = %s

                    ORDER BY
                        t.task_date DESC,
                        t.id DESC,
                        u.name ASC
                """, (mentor_id,))

                rows = cur.fetchall()

        progress = []

        for row in rows:

            task_id = row[0]
            task_title = row[1]
            platform = row[2]
            problem_identifier = row[3]
            task_date = row[4]

            group_id = row[5]
            group_name = row[6]

            student_id = row[7]
            student_name = row[8]
            student_email = row[9]

            submission_id = row[10]
            answer = row[11]
            submission_status = row[12]
            submitted_at = row[13]

            # -------------------------
            # Determine student status
            # -------------------------

            if submission_id is None:

                status = "not_submitted"

            elif submission_status == "approved":

                status = "verified"

            elif submission_status == "rejected":

                status = "rejected"

            else:

                status = "submitted"

            progress.append({

                "task_id": task_id,

                "task_title": task_title,

                "platform": platform,

                "problem_identifier":
                    problem_identifier,

                "task_date":
                    str(task_date),

                "group_id":
                    group_id,

                "group_name":
                    group_name,

                "student_id":
                    student_id,

                "student_name":
                    student_name,

                "student_email":
                    student_email,

                "submission_id":
                    submission_id,

                "answer":
                    answer,

                "status":
                    status,

                "submission_status":
                    submission_status,

                "submitted_at":
                    (
                        str(submitted_at)
                        if submitted_at
                        else None
                    )

            })

        return jsonify({

            "success": True,

            "progress": progress

        })

    except Exception as e:

        print(
            "Mentor progress loading error:",
            e
        )

        return jsonify({

            "success": False,

            "error": str(e)

        }), 500

# =========================
# Mentor student progress summary
# =========================
@app.route("/api/mentor/progress/<int:mentor_id>", methods=["GET"])
def get_mentor_progress(mentor_id):
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        mg.id,
                        mg.name,
                        u.id,
                        u.name,
                        u.email,
                        t.id,
                        t.title,
                        t.platform,
                        t.problem_identifier,
                        t.task_date,
                        s.id,
                        s.status,
                        s.submitted_at,
                        s.screenshot_url
                    FROM mentor_groups mg
                    JOIN group_members gm ON gm.group_id = mg.id
                    JOIN users u ON u.id = gm.student_id
                    LEFT JOIN tasks t ON t.group_id = mg.id
                    LEFT JOIN submissions s
                        ON s.task_id = t.id
                        AND s.student_id = u.id
                    WHERE mg.mentor_id = %s
                    ORDER BY u.name, t.task_date DESC, t.id DESC
                """, (mentor_id,))
                rows = cur.fetchall()

        students = {}
        for row in rows:
            group_id, group_name = row[0], row[1]
            student_id, student_name, student_email = row[2:5]
            task_id = row[5]
            key = (group_id, student_id)

            student = students.setdefault(key, {
                "group_id": group_id,
                "group_name": group_name,
                "student_id": student_id,
                "student_name": student_name,
                "student_email": student_email,
                "total_tasks": 0,
                "submitted_tasks": 0,
                "verified_tasks": 0,
                "total_points": 0,
                "review_tasks": 0,
                "problems": []
            })

            if task_id is None:
                continue

            submission_id, submission_status = row[10], row[11]
            solved = submission_status == "approved"
            student["total_tasks"] += 1
            student["submitted_tasks"] += int(submission_id is not None)
            student["verified_tasks"] += int(solved)
            needs_review = bool(
                row[13] and submission_id and not solved
            )
            student["review_tasks"] += int(needs_review)
            student["problems"].append({
                "task_id": task_id,
                "title": row[6],
                "platform": row[7],
                "problem_identifier": row[8],
                "task_date": str(row[9]) if row[9] else None,
                "submission_id": submission_id,
                "status": "solved" if solved else (
                    "submitted" if submission_id else "not_submitted"
                ),
                "needs_review": needs_review,
                "submitted_at": str(row[12]) if row[12] else None
                ,"screenshot_url": row[13]
            })

        result = []
        for student in students.values():
            student["total_points"] = student["verified_tasks"] * 100
            student["progress"] = round(
                student["verified_tasks"] / student["total_tasks"] * 100
            ) if student["total_tasks"] else 0
            result.append(student)

        return jsonify({"success": True, "students": result})

    except Exception as e:
        print("Mentor progress summary error:", e)
        return jsonify({"success": False, "error": str(e)}), 500

# =========================
# Review submission
# =========================
@app.route("/api/submissions/<int:submission_id>/review", methods=["PUT"])
def review_submission(submission_id):
    data = request.json

    status = data.get("status")

    if status not in ["approved", "rejected"]:
        return jsonify({
            "success": False,
            "error": "Status must be approved or rejected"
        }), 400

    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    UPDATE submissions
                    SET status = %s
                    WHERE id = %s
                    RETURNING id, status
                """, (status, submission_id))

                result = cur.fetchone()

                if not result:
                    return jsonify({
                        "success": False,
                        "error": "Submission not found"
                    }), 404

                points_awarded = 0
                if status == "approved":
                    cur.execute("""
                        INSERT INTO student_points
                            (student_id, submission_id, points, reason)
                        SELECT student_id, %s, 100,
                               'Mentor approved screenshot proof'
                        FROM submissions
                        WHERE id = %s
                        AND NOT EXISTS (
                            SELECT 1 FROM student_points
                            WHERE submission_id = %s
                        )
                    """, (submission_id, submission_id, submission_id))
                    points_awarded = cur.rowcount * 100

                conn.commit()

        return jsonify({
            "success": True,
            "submission_id": result[0],
            "status": result[1],
            "points_awarded": points_awarded
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
# =========================
# Student sends mentor join request
# =========================
@app.route("/api/join-requests", methods=["POST"])
def create_join_request():
    data = request.json

    student_id = data.get("student_id")
    mentor_id = data.get("mentor_id")

    if not student_id or not mentor_id:
        return jsonify({
            "success": False,
            "error": "student_id and mentor_id are required"
        }), 400

    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                # Check student
                cur.execute("""
                    SELECT id, role
                    FROM users
                    WHERE id = %s
                """, (student_id,))

                student = cur.fetchone()

                if not student:
                    return jsonify({
                        "success": False,
                        "error": "Student not found"
                    }), 404

                if student[1] != "student":
                    return jsonify({
                        "success": False,
                        "error": "User is not a student"
                    }), 400

                # Check mentor
                cur.execute("""
                    SELECT id, role
                    FROM users
                    WHERE id = %s
                """, (mentor_id,))

                mentor = cur.fetchone()

                if not mentor:
                    return jsonify({
                        "success": False,
                        "error": "Mentor not found"
                    }), 404

                if mentor[1] != "mentor":
                    return jsonify({
                        "success": False,
                        "error": "User is not a mentor"
                    }), 400

                # Check existing request
                cur.execute("""
                    SELECT id, status
                    FROM mentor_join_requests
                    WHERE student_id = %s
                    AND mentor_id = %s
                """, (student_id, mentor_id))

                existing = cur.fetchone()

                if existing:
                    return jsonify({
                        "success": False,
                        "error": f"Request already exists with status: {existing[1]}"
                    }), 409

                # Create request
                cur.execute("""
                    INSERT INTO mentor_join_requests
                    (student_id, mentor_id, status)
                    VALUES (%s, %s, 'pending')
                    RETURNING id
                """, (student_id, mentor_id))

                request_id = cur.fetchone()[0]

                conn.commit()

        return jsonify({
            "success": True,
            "message": "Join request sent successfully",
            "request_id": request_id
        }), 201

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
# =========================
# Mentor views join requests
# =========================
@app.route("/api/mentor/join-requests/<int:mentor_id>", methods=["GET"])
def get_join_requests(mentor_id):

    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        r.id,
                        r.student_id,
                        u.name,
                        u.email,
                        r.status,
                        r.created_at
                    FROM mentor_join_requests r
                    JOIN users u
                        ON r.student_id = u.id
                    WHERE r.mentor_id = %s
                    ORDER BY r.created_at DESC
                """, (mentor_id,))

                rows = cur.fetchall()

        requests = []

        for row in rows:
            requests.append({
                "id": row[0],
                "student_id": row[1],
                "student_name": row[2],
                "student_email": row[3],
                "status": row[4],
                "created_at": str(row[5])
            })

        return jsonify({
            "success": True,
            "requests": requests
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
# =========================
# Mentor accepts/rejects request
# =========================
@app.route("/api/join-requests/<int:request_id>/review", methods=["PUT"])
def review_join_request(request_id):

    data = request.json
    status = data.get("status")
    group_id = data.get("group_id")

    if status not in ["accepted", "rejected"]:
        return jsonify({
            "success": False,
            "error": "Status must be accepted or rejected"
        }), 400

    if status == "accepted" and not group_id:
        return jsonify({
            "success": False,
            "error": "group_id is required when accepting"
        }), 400

    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                # Get request
                cur.execute("""
                    SELECT student_id, mentor_id, status
                    FROM mentor_join_requests
                    WHERE id = %s
                """, (request_id,))

                request_data = cur.fetchone()

                if not request_data:
                    return jsonify({
                        "success": False,
                        "error": "Join request not found"
                    }), 404

                student_id = request_data[0]
                mentor_id = request_data[1]

                if request_data[2] != "pending":
                    return jsonify({
                        "success": False,
                        "error": "This request has already been reviewed"
                    }), 400

                # If accepted, make sure group belongs to mentor
                if status == "accepted":

                    cur.execute("""
                        SELECT id
                        FROM mentor_groups
                        WHERE id = %s
                        AND mentor_id = %s
                    """, (group_id, mentor_id))

                    group = cur.fetchone()

                    if not group:
                        return jsonify({
                            "success": False,
                            "error": "Group does not belong to this mentor"
                        }), 403

                    # Add student to group
                    cur.execute("""
                        INSERT INTO group_members
                        (group_id, student_id)
                        VALUES (%s, %s)
                        ON CONFLICT (group_id, student_id)
                        DO NOTHING
                    """, (group_id, student_id))

                # Update request status
                cur.execute("""
                    UPDATE mentor_join_requests
                    SET status = %s
                    WHERE id = %s
                """, (status, request_id))

                conn.commit()

        return jsonify({
            "success": True,
            "message": f"Request {status} successfully"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
# =========================
# Get all mentors
# =========================
@app.route("/api/mentors", methods=["GET"])
def get_mentors():
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT id, name, email
                    FROM users
                    WHERE role = 'mentor'
                    ORDER BY name ASC
                """)

                rows = cur.fetchall()

        mentors = []

        for row in rows:
            mentors.append({
                "id": row[0],
                "name": row[1],
                "email": row[2]
            })

        return jsonify({
            "success": True,
            "mentors": mentors
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
# =========================
# Get student's join requests
# =========================
@app.route("/api/student/join-requests/<int:student_id>", methods=["GET"])
def get_student_join_requests(student_id):
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        r.id,
                        r.mentor_id,
                        u.name AS mentor_name,
                        r.status
                    FROM mentor_join_requests r
                    JOIN users u
                        ON r.mentor_id = u.id
                    WHERE r.student_id = %s
                    ORDER BY r.created_at DESC
                """, (student_id,))

                rows = cur.fetchall()

        requests = []

        for row in rows:
            requests.append({
                "id": row[0],
                "mentor_id": row[1],
                "mentor_name": row[2],
                "status": row[3]
            })

        return jsonify({
            "success": True,
            "requests": requests
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
# =========================
# Get mentor join requests
# =========================
@app.route("/api/mentor/join-requests/<int:mentor_id>", methods=["GET"])
def get_mentor_join_requests(mentor_id):
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        r.id,
                        r.student_id,
                        u.name,
                        u.email,
                        r.status,
                        r.created_at
                    FROM mentor_join_requests r
                    JOIN users u
                        ON r.student_id = u.id
                    WHERE r.mentor_id = %s
                    ORDER BY r.created_at DESC
                """, (mentor_id,))

                rows = cur.fetchall()

        requests = []

        for row in rows:
            requests.append({
                "id": row[0],
                "student_id": row[1],
                "student_name": row[2],
                "student_email": row[3],
                "status": row[4],
                "created_at": str(row[5])
            })

        return jsonify({
            "success": True,
            "requests": requests
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =========================
# Accept mentor join request
# =========================
@app.route(
    "/api/mentor/join-requests/<int:request_id>/accept",
    methods=["POST"]
)
def accept_join_request(request_id):

    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                # Find the request
                cur.execute("""
                    SELECT student_id, mentor_id, status
                    FROM mentor_join_requests
                    WHERE id = %s
                """, (request_id,))

                request_row = cur.fetchone()

                if not request_row:
                    return jsonify({
                        "success": False,
                        "error": "Join request not found"
                    }), 404

                student_id = request_row[0]
                mentor_id = request_row[1]
                status = request_row[2]

                if status != "pending":
                    return jsonify({
                        "success": False,
                        "error": "This request has already been processed"
                    }), 400

                # Find mentor's group
                cur.execute("""
                    SELECT id
                    FROM mentor_groups
                    WHERE mentor_id = %s
                    ORDER BY id ASC
                    LIMIT 1
                """, (mentor_id,))

                group_row = cur.fetchone()

                if not group_row:
                    return jsonify({
                        "success": False,
                        "error": "Mentor does not have a group"
                    }), 400

                group_id = group_row[0]

                # Add student to group
                cur.execute("""
                    INSERT INTO group_members
                        (group_id, student_id)
                    VALUES (%s, %s)
                    ON CONFLICT (group_id, student_id)
                    DO NOTHING
                """, (group_id, student_id))

                # Update request status
                cur.execute("""
                    UPDATE mentor_join_requests
                    SET status = 'accepted'
                    WHERE id = %s
                """, (request_id,))

                conn.commit()

        return jsonify({
            "success": True,
            "message": "Student accepted successfully",
            "group_id": group_id,
            "student_id": student_id
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({
            "success": False,
            "error": "Email and password are required"
        }), 400

    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT id, name, email, password, role
                    FROM users
                    WHERE email = %s
                """, (email,))

                user = cur.fetchone()

        if not user:
            return jsonify({
                "success": False,
                "error": "Invalid email or password"
            }), 401

        user_id = user[0]
        name = user[1]
        user_email = user[2]
        stored_password = user[3]
        role = user[4]

        if password != stored_password:
            return jsonify({
                "success": False,
                "error": "Invalid email or password"
            }), 401

        return jsonify({
            "success": True,
            "message": "Login successful",
            "user": {
                "id": user_id,
                "name": name,
                "email": user_email,
                "role": role
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
@app.route("/api/register", methods=["POST"])
def register():
    data = request.json

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    role = data.get("role")

    department = data.get("department")
    year = data.get("year")
    section = data.get("section")
    register_number = data.get("register_number")
    roll_number = data.get("roll_number")

    if not name or not email or not password or not role:
        return jsonify({
            "success": False,
            "error": "Name, email, password and role are required"
        }), 400

    if role not in ["student", "mentor"]:
        return jsonify({
            "success": False,
            "error": "Invalid role"
        }), 400

    # Academic details are required for students
    if role == "student":
        if (
            not department
            or not year
            or not section
            or not register_number
        ):
            return jsonify({
                "success": False,
                "error": "All student academic details are required"
            }), 400

    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                # Check existing email
                cur.execute("""
                    SELECT id
                    FROM users
                    WHERE email = %s
                """, (email,))

                existing_user = cur.fetchone()

                if existing_user:
                    return jsonify({
                        "success": False,
                        "error": "Email already registered"
                    }), 409

                # Create user
                cur.execute("""
                    INSERT INTO users (
                        name,
                        email,
                        password,
                        role,
                        department,
                        year,
                        section,
                        register_number,
                        roll_number
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    RETURNING id
                """, (
                    name,
                    email,
                    password,
                    role,
                    department,
                    year,
                    section,
                    register_number,
                    roll_number
                ))

                user_id = cur.fetchone()[0]

                # Create a default group for new mentor
                if role == "mentor":
                    cur.execute("""
                        INSERT INTO mentor_groups
                        (name, mentor_id)
                        VALUES (%s, %s)
                    """, (
                        f"{name}'s Group",
                        user_id
                    ))

                conn.commit()

        return jsonify({
            "success": True,
            "message": "Account created successfully!",
            "user_id": user_id
        }), 201

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
@app.route("/api/mentor/groups/<int:mentor_id>", methods=["GET"])
def get_mentor_groups(mentor_id):
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT id, name
                    FROM mentor_groups
                    WHERE mentor_id = %s
                    ORDER BY id ASC
                """, (mentor_id,))

                rows = cur.fetchall()

        groups = []

        for row in rows:
            groups.append({
                "id": row[0],
                "name": row[1]
            })

        return jsonify({
            "success": True,
            "groups": groups
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
@app.route("/api/student/group/<int:student_id>", methods=["GET"])
def get_student_group(student_id):
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        mg.id,
                        mg.name,
                        mg.mentor_id,
                        u.name AS mentor_name
                    FROM group_members gm
                    JOIN mentor_groups mg
                        ON gm.group_id = mg.id
                    JOIN users u
                        ON mg.mentor_id = u.id
                    WHERE gm.student_id = %s
                    LIMIT 1
                """, (student_id,))

                row = cur.fetchone()

        if not row:
            return jsonify({
                "success": True,
                "group": None
            })

        return jsonify({
            "success": True,
            "group": {
                "id": row[0],
                "name": row[1],
                "mentor_id": row[2],
                "mentor_name": row[3]
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
@app.route("/api/student/platforms", methods=["POST"])
def add_student_platform():
    data = request.json

    student_id = data.get("student_id")
    platform = data.get("platform")
    profile_url = data.get("profile_url")

    if not student_id or not platform or not profile_url:
        return jsonify({
            "success": False,
            "error": "student_id, platform and profile_url are required"
        }), 400

    profile_url = profile_url.strip()

    # =========================
    # Extract username
    # =========================
    username = None

    try:
        from urllib.parse import urlparse

        parsed_url = urlparse(profile_url)
        path_parts = [
            part
            for part in parsed_url.path.split("/")
            if part
        ]

        platform_lower = platform.lower()

        if platform_lower == "codeforces":
            # Expected:
            # https://codeforces.com/profile/username

            if (
                len(path_parts) >= 2
                and path_parts[0].lower() == "profile"
            ):
                username = path_parts[1]

        elif platform_lower == "leetcode":
            # Expected:
            # https://leetcode.com/u/username/

            if (
                len(path_parts) >= 2
                and path_parts[0].lower() == "u"
            ):
                username = path_parts[1]

        elif platform_lower == "skillrack":
            # SkillRack URL format can vary,
            # so we don't automatically extract yet.
            username = None

        if not username:
            return jsonify({
                "success": False,
                "error": (
                    "Could not extract username from this "
                    f"{platform} profile URL. Please check the URL."
                )
            }), 400

    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Invalid profile URL"
        }), 400

    # =========================
    # Save platform account
    # =========================
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                # Check student
                cur.execute("""
                    SELECT id
                    FROM users
                    WHERE id = %s
                    AND role = 'student'
                """, (student_id,))

                student = cur.fetchone()

                if not student:
                    return jsonify({
                        "success": False,
                        "error": "Student not found"
                    }), 404

                # Save / update account
                cur.execute("""
                    INSERT INTO student_platforms
                    (
                        student_id,
                        platform,
                        username,
                        profile_url,
                        verified,
                        verified_at
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        FALSE,
                        NULL
                    )

                    ON CONFLICT (student_id, platform)
                    DO UPDATE SET
                        username = EXCLUDED.username,
                        profile_url = EXCLUDED.profile_url,
                        verified = FALSE,
                        verified_at = NULL

                    RETURNING
                        id,
                        platform,
                        username,
                        profile_url,
                        verified
                """, (
                    student_id,
                    platform,
                    username,
                    profile_url
                ))

                row = cur.fetchone()

                conn.commit()

        return jsonify({
            "success": True,
            "message": "Platform profile saved successfully",
            "platform_account": {
                "id": row[0],
                "platform": row[1],
                "username": row[2],
                "profile_url": row[3],
                "verified": row[4]
            }
        }), 201

    except Exception as e:
        print("Platform account error:", e)

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
@app.route("/api/student/platforms/<int:student_id>", methods=["GET"])
def get_student_platforms(student_id):
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        id,
                        platform,
                        username,
                        profile_url,
                        verified,
                        verified_at
                    FROM student_platforms
                    WHERE student_id = %s
                    ORDER BY platform ASC
                """, (student_id,))

                rows = cur.fetchall()

        platforms = []

        for row in rows:
            platforms.append({
                "id": row[0],
                "platform": row[1],
                "username": row[2],
                "profile_url": row[3],
                "verified": row[4],
                "verified_at": (
                    str(row[5])
                    if row[5]
                    else None
                )
            })

        return jsonify({
            "success": True,
            "platforms": platforms
        })

    except Exception as e:
        print("Platform loading error:", e)

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
# =========================
# Helper: call the LeetCode verifier in-process
# =========================
def _call_leetcode_verifier(submission_id):
    """
    Calls verify_leetcode_submission() directly (no HTTP round trip)
    and normalizes its return value to (data_dict, status_code).

    Flask view functions can return either:
      - a Response object                (status defaults to 200)
      - a (Response-or-dict, status_code) tuple

    so we handle both shapes here in one place, used by both the
    per-submission flow (create_submission) and the all-users
    batch verification job below.
    """
    response = verify_leetcode_submission(submission_id)

    if isinstance(response, tuple):
        body, status_code = response
    else:
        body, status_code = response, 200

    if hasattr(body, "get_json"):
        data = body.get_json(silent=True) or {}
    elif isinstance(body, dict):
        data = body
    else:
        data = {}

    return data, status_code


# =========================
# Verify Codeforces Task
# =========================
@app.route("/api/verify/leetcode/<int:submission_id>", methods=["POST"])
def verify_leetcode_submission(submission_id):

    try:
        import re
        from urllib.parse import urlparse
        from curl_cffi import requests
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo

        # ==========================================================
        # 1. GET CODETRACK SUBMISSION + TASK
        # ==========================================================

        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute("""
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
                    INNER JOIN tasks t
                        ON s.task_id = t.id
                    WHERE s.id = %s
                """, (submission_id,))

                submission = cur.fetchone()

                if not submission:
                    return jsonify({
                        "success": False,
                        "error": "Submission not found"
                    }), 404

                db_submission_id = submission[0]
                task_id = submission[1]
                student_id = submission[2]
                answer = submission[3] or ""
                task_platform = submission[4]
                problem_identifier = submission[5]
                problem_url = submission[6]
                task_assigned_at = submission[7]

                # ==================================================
                # CHECK PLATFORM
                # ==================================================

                if not task_platform:
                    return jsonify({
                        "success": False,
                        "error": "Task platform is not set"
                    }), 400

                if task_platform.lower() != "leetcode":
                    return jsonify({
                        "success": False,
                        "error": "This verifier only supports LeetCode"
                    }), 400

                if not problem_identifier:
                    return jsonify({
                        "success": False,
                        "error": (
                            "Task has no LeetCode "
                            "problem identifier"
                        )
                    }), 400

                # ==================================================
                # 2. GET STUDENT'S LEETCODE ACCOUNT
                # ==================================================

                cur.execute("""
                    SELECT username
                    FROM student_platforms
                    WHERE student_id = %s
                    AND LOWER(platform) = 'leetcode'
                    LIMIT 1
                """, (student_id,))

                account = cur.fetchone()

                if not account:
                    return jsonify({
                        "success": False,
                        "verified": False,
                        "error": (
                            "Student has not connected "
                            "a LeetCode account"
                        )
                    }), 400

                username = account[0]

                # ==================================================
                # 3. GROUP MEMBERSHIP CHECK
                # ==================================================

                cur.execute("""
                    SELECT joined_at
                    FROM group_members
                    WHERE student_id = %s
                    AND group_id = (
                        SELECT group_id
                        FROM tasks
                        WHERE id = %s
                    )
                    LIMIT 1
                """, (
                    student_id,
                    task_id
                ))

                membership = cur.fetchone()

                if not membership:
                    return jsonify({
                        "success": False,
                        "verified": False,
                        "message": (
                            "Student is not a member "
                            "of the task group."
                        )
                    }), 403

                student_joined_at = membership[0]

        # ==========================================================
        # 4. DETERMINE ELIGIBILITY TIME
        # ==========================================================

        IST = ZoneInfo("Asia/Kolkata")

        if (
            task_assigned_at
            and task_assigned_at.tzinfo is None
        ):
            task_assigned_at = task_assigned_at.replace(
                tzinfo=IST
            )

        if (
            student_joined_at
            and student_joined_at.tzinfo is None
        ):
            student_joined_at = student_joined_at.replace(
                tzinfo=IST
            )

        eligibility_time = task_assigned_at

        if (
            student_joined_at
            and (
                eligibility_time is None
                or student_joined_at > eligibility_time
            )
        ):
            eligibility_time = student_joined_at

        # Older tasks may not have assignment or membership timestamps.
        # In that case, continue with the account, ID, status, and problem
        # checks instead of blocking an otherwise verifiable submission.
        if eligibility_time is None:
            eligibility_time = datetime.min.replace(tzinfo=IST)

        # ==========================================================
        # 5. EXTRACT EXACT LEETCODE SUBMISSION ID
        # ==========================================================

        submission_id_match = re.search(
            r'/submissions/(?:detail/)?(\d+)',
            answer
        )

        if not submission_id_match:

            submission_id_match = re.search(
                r'/submissions/detail/(\d+)',
                answer
            )

        if not submission_id_match:

            return jsonify({
                "success": False,
                "verified": False,
                "message": (
                    "Please submit the complete "
                    "LeetCode submission URL."
                )
            }), 400

        external_submission_id = (
            submission_id_match.group(1)
        )

        print(
            "Checking exact LeetCode submission:",
            external_submission_id
        )

                # ==========================================================
                # 6. VERIFY EXACT SUBMISSION USING LEETCODE GRAPHQL
                # ==========================================================

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

        response = requests.post(
            "https://leetcode.com/graphql",
            json={
                "query": graphql_query,
                "variables": {
                    "username": username,
                    "limit": 100
                }
            },
            headers={
                "content-type": "application/json",
                "accept": "application/json",
                "origin": "https://leetcode.com",
                "referer": "https://leetcode.com/",
            },
            impersonate="chrome",
            timeout=20
        )

        print(
            "LeetCode HTTP status:",
            response.status_code
        )

        if response.status_code != 200:

            print(
                "LeetCode response:",
                response.text[:1000]
            )

            return jsonify({
                "success": False,
                "verified": False,
                "verification_available": False,
                "message": (
                    "LeetCode could not be contacted "
                    "for exact submission verification."
                )
            }), 502

        api_data = response.json()

        print("=== LEETCODE DEBUG ===")
        print("USERNAME:", username)
        print("REQUESTED SUBMISSION:", external_submission_id)
        print("GRAPHQL RESPONSE:")
        print(api_data)
        if api_data.get("errors"):

            print(
                "LeetCode GraphQL errors:",
                api_data.get("errors")
            )

            return jsonify({
                "success": False,
                "verified": False,
                "verification_available": False,
                "message": (
                    "LeetCode returned an error "
                    "while checking the submission."
                )
            }), 502

        recent_submissions = (
            api_data
            .get("data", {})
            .get("recentAcSubmissionList")
            or []
        )

        submission_data = next(
            (
                item for item in recent_submissions
                if str(item.get("id")) == external_submission_id
            ),
            None
        )

        # ==========================================================
        # 7. SUBMISSION EXISTS?
        # ==========================================================

        if not submission_data:

            return jsonify({
                "success": False,
                "verified": False,
                "verification_available": True,
                "status": "submitted",
                "message": (
                    "The submitted ID was not found in the "
                    "connected account's recent accepted submissions. "
                    "Use an accepted submission URL from the same "
                    "LeetCode account."
                ),
                "leetcode_submission_id":
                    external_submission_id
            }), 422

        # ==========================================================
        # 8. CHECK ACCEPTED
        # ==========================================================

        status_display = "Accepted"

        # ==========================================================
        # 9. CHECK PROBLEM
        # ==========================================================

        question = submission_data

        actual_slug = (
            question.get("titleSlug")
            or ""
        ).lower()

        expected_slug = ""
        if problem_url:
            problem_path = urlparse(problem_url).path.strip("/").split("/")
            if "problems" in problem_path:
                problem_index = problem_path.index("problems")
                if len(problem_path) > problem_index + 1:
                    expected_slug = problem_path[problem_index + 1].lower()

        if not expected_slug:
            expected_slug = re.sub(
                r"[^a-z0-9]+",
                "-",
                problem_identifier.strip().lower()
            ).strip("-")

        if actual_slug != expected_slug:

            return jsonify({
                "success": True,
                "verified": False,
                "verification_available": True,
                "status": "rejected",
                "message": (
                    "The submitted LeetCode problem "
                    "does not match the assigned task."
                ),
                "expected_problem": expected_slug,
                "submitted_problem": actual_slug,
                "leetcode_submission_id":
                    external_submission_id
            })

        # ==========================================================
        # 10. CHECK SUBMISSION TIME
        # ==========================================================

        timestamp_value = (
            submission_data.get("timestamp")
        )

        if not timestamp_value:

            return jsonify({
                "success": False,
                "verified": False,
                "message": (
                    "LeetCode submission timestamp "
                    "was not available."
                )
            }), 502

        leetcode_time = datetime.fromtimestamp(
            int(timestamp_value),
            tz=timezone.utc
        )

        # ==========================================================
        # ANTI-REUSE CHECK
        # ==========================================================

        if leetcode_time <= eligibility_time:

            return jsonify({
                "success": True,
                "verified": False,
                "verification_available": True,
                "status": "rejected",
                "message": (
                    "This LeetCode submission was made "
                    "before the task became available."
                ),
                "leetcode_submission_id":
                    external_submission_id,
                "submission_time":
                    leetcode_time.isoformat(),
                "eligible_after":
                    eligibility_time.isoformat()
            })

        # ==========================================================
        # 11. CHECK IF SUBMISSION WAS ALREADY USED
        # ==========================================================

        with psycopg.connect(**DB_CONFIG) as conn:

            with conn.cursor() as cur:

                cur.execute("""
                    SELECT id
                    FROM submissions
                    WHERE external_submission_id = %s
                    AND id <> %s
                    LIMIT 1
                """, (
                    external_submission_id,
                    submission_id
                ))

                already_used = cur.fetchone()

                if already_used:

                    return jsonify({
                        "success": True,
                        "verified": False,
                        "verification_available": True,
                        "status": "rejected",
                        "message": (
                            "This LeetCode submission "
                            "has already been used "
                            "for another CodeTrack task."
                        ),
                        "leetcode_submission_id":
                            external_submission_id
                    })

                # ==================================================
                # 12. APPROVE
                # ==================================================

                cur.execute("""
                    UPDATE submissions
                    SET
                        status = 'approved',
                        external_submission_id = %s
                    WHERE id = %s
                """, (
                    external_submission_id,
                    submission_id
                ))

                # ==================================================
                # 13. AWARD POINTS ONCE
                # ==================================================

                cur.execute("""
                    INSERT INTO student_points
                    (
                        student_id,
                        submission_id,
                        points,
                        reason
                    )
                    SELECT
                        student_id,
                        %s,
                        100,
                        'LeetCode task verified'
                    FROM submissions
                    WHERE id = %s
                    AND NOT EXISTS (
                        SELECT 1
                        FROM student_points
                        WHERE submission_id = %s
                    )
                """, (
                    submission_id,
                    submission_id,
                    submission_id
                ))

                points_inserted = cur.rowcount

                conn.commit()

        # ==========================================================
        # 14. SUCCESS
        # ==========================================================

        return jsonify({
            "success": True,
            "verified": True,
            "verification_available": True,
            "status": "approved",
            "submission_id": submission_id,
            "points_awarded": (
                100
                if points_inserted == 1
                else 0
            ),
            "username": username,
            "problem": {
                "title":
                    question.get("title"),
                "title_slug":
                    actual_slug,
                "leetcode_submission_id":
                    external_submission_id,
                "timestamp":
                    timestamp_value,
                "status":
                    status_display
            },
            "message": (
                "LeetCode submission "
                "verified successfully! 🎉"
            )
        })

    # ==========================================================
    # CONNECTION ERROR
    # ==========================================================

    except requests.RequestException as e:

        print(
            "LeetCode API connection error:",
            e
        )

        return jsonify({
            "success": False,
            "verified": False,
            "verification_available": False,
            "message": (
                "Could not connect to LeetCode."
            )
        }), 502

    # ==========================================================
    # GENERAL ERROR
    # ==========================================================

    except Exception as e:

        print(
            "LeetCode verification error:",
            e
        )

        return jsonify({
            "success": False,
            "verified": False,
            "verification_available": False,
            "error": str(e)
        }), 500


# ==========================================================
# Automatic batch verification - checks ALL users' pending
# LeetCode submissions, not just the one just submitted.
# ==========================================================

def run_batch_leetcode_verification():
    """
    Finds every LeetCode submission across every student that
    has not yet been approved, and re-runs the verifier on each
    one. Safe to call repeatedly (already-approved/rejected-for-
    a-real-reason submissions are simply re-checked, not double-
    awarded, since verify_leetcode_submission() only inserts
    student_points once per submission_id).
    """

    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT s.id
                    FROM submissions s
                    INNER JOIN tasks t
                        ON s.task_id = t.id
                    WHERE LOWER(t.platform) = 'leetcode'
                    AND s.status != 'approved'
                """)
                pending_ids = [row[0] for row in cur.fetchall()]

    except Exception as e:
        print("Batch verification: could not load pending submissions:", e)
        return {
            "success": False,
            "error": str(e),
            "checked": 0,
            "results": []
        }

    results = []

    for submission_id in pending_ids:

        try:
            data, status_code = _call_leetcode_verifier(submission_id)

            results.append({
                "submission_id": submission_id,
                "status_code": status_code,
                "verified": bool(data.get("verified")),
                "message": data.get("message") or data.get("error")
            })

        except Exception as e:
            print(f"Batch verification error for submission {submission_id}:", e)
            results.append({
                "submission_id": submission_id,
                "status_code": 500,
                "verified": False,
                "message": str(e)
            })

    verified_count = sum(1 for r in results if r["verified"])

    print(
        f"[Batch LeetCode Verification] checked {len(results)} "
        f"pending submissions across all students, "
        f"{verified_count} newly verified."
    )

    return {
        "success": True,
        "checked": len(results),
        "verified": verified_count,
        "results": results
    }


@app.route("/api/verify/leetcode/batch", methods=["POST"])
def verify_leetcode_batch():
    """
    Manually trigger the same automatic check that the background
    scheduler runs on a timer (see start_verification_scheduler()
    below) - useful for testing, or for a mentor "Re-check all"
    button in the dashboard.
    """
    summary = run_batch_leetcode_verification()
    return jsonify(summary), (200 if summary.get("success") else 500)


@app.route("/api/student/tasks/<int:student_id>", methods=["GET"])
def get_student_tasks(student_id):
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        t.id,
                        t.title,
                        t.description,
                        t.task_date,
                        t.created_at,
                        t.platform,
                        t.problem_url,
                        t.problem_identifier,
                        mg.name AS group_name,

                        s.id AS submission_id,
                        s.status AS submission_status,
                        s.submitted_at

                    FROM tasks t

                    INNER JOIN mentor_groups mg
                        ON t.group_id = mg.id

                    INNER JOIN group_members gm
                        ON mg.id = gm.group_id

                    LEFT JOIN submissions s
                        ON s.task_id = t.id
                        AND s.student_id = %s

                    WHERE gm.student_id = %s

                    ORDER BY
                        t.task_date DESC,
                        t.id DESC
                """, (
                    student_id,
                    student_id
                ))

                rows = cur.fetchall()

        tasks = []

        for row in rows:

            submission_id = row[9]
            submission_status = row[10]

            # --------------------------------
            # Determine task completion
            # --------------------------------

            if submission_status == "approved":
                task_status = "completed"

            elif submission_status == "rejected":
                task_status = "rejected"

            elif submission_status == "submitted":
                task_status = "submitted"

            else:
                task_status = "pending"

            tasks.append({
                "id": row[0],
                "title": row[1],
                "description": row[2],
                "task_date": str(row[3]),
                "created_at": str(row[4]),

                "platform": row[5],
                "problem_url": row[6],
                "problem_identifier": row[7],

                "group_name": row[8],

                "submission_id": submission_id,

                "submission_status": submission_status,

                "task_status": task_status,

                "submitted_at": (
                    str(row[11])
                    if row[11]
                    else None
                )
            })

        return jsonify({
            "success": True,
            "tasks": tasks
        })

    except Exception as e:

        print(
            "Student task loading error:",
            e
        )

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
# ==========================================
# Student Points API
# ==========================================

@app.route("/api/student/points/<int:student_id>", methods=["GET"])
def get_student_points(student_id):
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                # ----------------------------------
                # Calculate total points
                # ----------------------------------
                cur.execute("""
                    SELECT COALESCE(SUM(points), 0)
                    FROM student_points
                    WHERE student_id = %s
                """, (student_id,))

                total_points = cur.fetchone()[0]

                # ----------------------------------
                # Count verified tasks
                # ----------------------------------
                cur.execute("""
                    SELECT COUNT(DISTINCT submission_id)
                    FROM student_points
                    WHERE student_id = %s
                """, (student_id,))

                verified_tasks = cur.fetchone()[0]

        return jsonify({
            "success": True,
            "total_points": int(total_points),
            "verified_tasks": int(verified_tasks)
        })

    except Exception as e:
        print("Student points error:", e)

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ==========================================================
# CodeTrack AI
# ==========================================================

@app.route("/api/ai/chat", methods=["POST"])
def codetrack_ai_chat():

    try:
        data = request.json or {}

        message = data.get("message", "").strip()

        if not message:
            return jsonify({
                "success": False,
                "error": "Message is required"
            }), 400

        # --------------------------------------------------
        # Optional student ID
        # --------------------------------------------------

        student_id = data.get("student_id")

        student_context = None

        # --------------------------------------------------
        # Get basic student information if student_id exists
        # --------------------------------------------------

        if student_id:

            try:
                with psycopg.connect(**DB_CONFIG) as conn:
                    with conn.cursor() as cur:

                        cur.execute("""
                            SELECT
                                name,
                                department,
                                year
                            FROM users
                            WHERE id = %s
                            AND role = 'student'
                        """, (student_id,))

                        student = cur.fetchone()

                        if student:

                            student_context = f"""
       Name: {student[0]}
       Department: {student[1] or 'Not specified'}
     Year: {student[2] or 'Not specified'}
"""

            except Exception as context_error:

                print(
                    "Student context error:",
                    context_error
                )

        # --------------------------------------------------
        # Build CodeTrack AI prompt
        # --------------------------------------------------

        final_prompt = build_prompt(
            message,
            student_context
        )

        # --------------------------------------------------
        # Ask local Qwen model
        # --------------------------------------------------

        result = ask_codetrack_ai(
            final_prompt
        )

        # --------------------------------------------------
        # Return AI response
        # --------------------------------------------------

        if not result.get("success"):

            return jsonify({
                "success": False,
                "error": result.get(
                    "error",
                    "CodeTrack AI failed"
                )
            }), 500

        return jsonify({
            "success": True,
            "response": result.get(
                "response",
                ""
            )
        })

    except Exception as e:

        print(
            "CodeTrack AI API error:",
            e
        )

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ==========================================================
# Background scheduler - runs batch verification for ALL
# users automatically, every few minutes, with no manual
# trigger required.
# ==========================================================

VERIFICATION_INTERVAL_MINUTES = 5


def start_verification_scheduler():
    from datetime import datetime
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        run_batch_leetcode_verification,
        trigger="interval",
        minutes=VERIFICATION_INTERVAL_MINUTES,
        id="leetcode_batch_verification",
        # run once right at startup instead of waiting a full interval
        next_run_time=datetime.now(),
    )
    scheduler.start()
    print(
        f"Automatic LeetCode verification scheduler started "
        f"(every {VERIFICATION_INTERVAL_MINUTES} minutes, all students)."
    )
    return scheduler


# ==========================================================
# Start Flask
# ==========================================================

if __name__ == "__main__":
    with psycopg.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "ALTER TABLE submissions "
                "ADD COLUMN IF NOT EXISTS screenshot_url TEXT"
            )
        conn.commit()

    # In Flask's debug/reloader mode, __main__ runs twice (parent
    # watcher + reloaded child). Only start the scheduler in the
    # actual serving process to avoid running the batch job twice.
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        start_verification_scheduler()

    app.run(debug=True)