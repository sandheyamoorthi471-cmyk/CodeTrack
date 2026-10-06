import os
import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
import psycopg
from werkzeug.utils import secure_filename

from codetracker_ai.ai import ask_codetrack_ai
from codetracker_ai.prompt import build_prompt

from verification.leetcode import (
    call_leetcode_verifier,
    verify_leetcode_submission as verify_leetcode_submission_logic,
    run_batch_leetcode_verification,
)

load_dotenv()

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "uploads",
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "codetrack"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
}


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type,Authorization"
    )
    response.headers["Access-Control-Allow-Methods"] = (
        "GET,POST,PUT,DELETE,OPTIONS"
    )
    return response


# ---------------------------------------------------------
# HOME
# ---------------------------------------------------------

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "CodeTrack Backend is Running!"
    })


# ---------------------------------------------------------
# UPLOADS
# ---------------------------------------------------------

@app.route("/uploads/<filename>", methods=["GET"])
def uploaded_file(filename):
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename,
    )


# ---------------------------------------------------------
# TEST DATABASE
# ---------------------------------------------------------

@app.route("/api/test-db", methods=["GET"])
def test_db():
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()

        return jsonify({
            "success": True,
            "message": "Database connected successfully.",
            "result": result[0],
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Database connection failed.",
            "error": str(error),
        }), 500


# ---------------------------------------------------------
# TASKS
# ---------------------------------------------------------

@app.route("/api/tasks", methods=["POST"])
def create_task():
    try:
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
                "message": "Group, title and task date are required."
            }), 400

        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
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
                    """,
                    (
                        group_id,
                        title,
                        description,
                        task_date,
                        platform,
                        problem_url,
                        problem_identifier,
                    ),
                )

                task_id = cur.fetchone()[0]

            conn.commit()

        return jsonify({
            "success": True,
            "message": "Task created successfully.",
            "task_id": task_id,
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Failed to create task.",
            "error": str(error),
        }), 500


# ---------------------------------------------------------
# SUBMISSIONS
# ---------------------------------------------------------

@app.route("/api/submissions", methods=["POST"])
def create_submission():
    try:
        student_id = request.form.get("student_id")
        task_id = request.form.get("task_id")
        answer = request.form.get("answer")

        screenshot = request.files.get("screenshot")

        if not student_id or not task_id:
            return jsonify({
                "success": False,
                "message": "Student ID and task ID are required."
            }), 400

        screenshot_url = None

        if screenshot:
            original_name = secure_filename(
                screenshot.filename or "screenshot"
            )

            extension = ""

            if "." in original_name:
                extension = "." + original_name.rsplit(".", 1)[1]

            filename = f"{uuid.uuid4().hex}{extension}"

            screenshot.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename,
                )
            )

            screenshot_url = f"/uploads/{filename}"

        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    INSERT INTO submissions (
                        task_id,
                        student_id,
                        answer,
                        status,
                        screenshot_url
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        task_id,
                        student_id,
                        answer,
                        "submitted",
                        screenshot_url,
                    ),
                )

                submission_id = cur.fetchone()[0]

            conn.commit()

        # Try automatic LeetCode verification
        verification_data = None
        verification_status = None

        try:
            verification_data, verification_status = (
                call_leetcode_verifier(
                    submission_id,
                    DB_CONFIG,
                )
            )
        except Exception as verification_error:
            print(
                "Automatic LeetCode verification error:",
                verification_error,
            )

        return jsonify({
            "success": True,
            "message": "Submission created successfully.",
            "submission_id": submission_id,
            "screenshot_url": screenshot_url,
            "verification": verification_data,
            "verification_status": verification_status,
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Failed to create submission.",
            "error": str(error),
        }), 500


# ---------------------------------------------------------
# MENTOR SUBMISSIONS
# ---------------------------------------------------------

@app.route(
    "/api/mentor/submissions/<int:mentor_id>",
    methods=["GET"],
)
def mentor_submissions(mentor_id):
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        s.id,
                        s.task_id,
                        s.student_id,
                        u.name AS student_name,
                        u.email AS student_email,
                        t.title,
                        t.platform,
                        t.problem_url,
                        s.answer,
                        s.status,
                        s.submitted_at,
                        s.screenshot_url,
                        s.external_submission_id
                    FROM submissions s
                    JOIN users u
                        ON u.id = s.student_id
                    JOIN tasks t
                        ON t.id = s.task_id
                    JOIN mentor_groups g
                        ON g.id = t.group_id
                    WHERE g.mentor_id = %s
                    ORDER BY s.submitted_at DESC
                    """,
                    (mentor_id,),
                )

                rows = cur.fetchall()

        submissions = []

        for row in rows:
            submissions.append({
                "id": row[0],
                "task_id": row[1],
                "student_id": row[2],
                "student_name": row[3],
                "student_email": row[4],
                "title": row[5],
                "platform": row[6],
                "problem_url": row[7],
                "answer": row[8],
                "status": row[9],
                "submitted_at": row[10].isoformat()
                if row[10]
                else None,
                "screenshot_url": row[11],
                "external_submission_id": row[12],
            })

        return jsonify({
            "success": True,
            "submissions": submissions,
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Failed to fetch mentor submissions.",
            "error": str(error),
        }), 500


# ---------------------------------------------------------
# MENTOR PROGRESS
# ---------------------------------------------------------

@app.route(
    "/api/mentor/progress/<int:mentor_id>",
    methods=["GET"],
)
def mentor_progress(mentor_id):
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        u.id,
                        u.name,
                        u.email,
                        COUNT(s.id) AS total_submissions,
                        COUNT(
                            CASE
                                WHEN s.status = 'approved'
                                THEN 1
                            END
                        ) AS approved_submissions
                    FROM group_members gm
                    JOIN mentor_groups g
                        ON g.id = gm.group_id
                    JOIN users u
                        ON u.id = gm.student_id
                    LEFT JOIN submissions s
                        ON s.student_id = u.id
                    WHERE g.mentor_id = %s
                    GROUP BY u.id, u.name, u.email
                    ORDER BY u.name
                    """,
                    (mentor_id,),
                )

                rows = cur.fetchall()

        progress = []

        for row in rows:
            progress.append({
                "student_id": row[0],
                "name": row[1],
                "email": row[2],
                "total_submissions": row[3],
                "approved_submissions": row[4],
            })

        return jsonify({
            "success": True,
            "students": progress,
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Failed to fetch mentor progress.",
            "error": str(error),
        }), 500


# ---------------------------------------------------------
# REVIEW SUBMISSION
# ---------------------------------------------------------

@app.route(
    "/api/submissions/<int:submission_id>/review",
    methods=["PUT"],
)
def review_submission(submission_id):
    try:
        data = request.json

        status = data.get("status")

        if status not in ["approved", "rejected"]:
            return jsonify({
                "success": False,
                "message": "Invalid status."
            }), 400

        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE submissions
                    SET status = %s
                    WHERE id = %s
                    RETURNING id, student_id
                    """,
                    (
                        status,
                        submission_id,
                    ),
                )

                updated = cur.fetchone()

                if not updated:
                    return jsonify({
                        "success": False,
                        "message": "Submission not found."
                    }), 404

                if status == "approved":

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
                                updated[1],
                                submission_id,
                                100,
                                "Approved coding submission",
                            ),
                        )

            conn.commit()

        return jsonify({
            "success": True,
            "message": f"Submission {status}.",
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Failed to review submission.",
            "error": str(error),
        }), 500


# ---------------------------------------------------------
# JOIN REQUESTS
# ---------------------------------------------------------

@app.route(
    "/api/join-requests",
    methods=["POST"],
)
def create_join_request():
    try:
        data = request.json

        student_id = data.get("student_id")
        mentor_id = data.get("mentor_id")

        if not student_id or not mentor_id:
            return jsonify({
                "success": False,
                "message": "Student ID and mentor ID are required."
            }), 400

        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT id
                    FROM mentor_join_requests
                    WHERE student_id = %s
                    AND mentor_id = %s
                    AND status = 'pending'
                    LIMIT 1
                    """,
                    (
                        student_id,
                        mentor_id,
                    ),
                )

                existing = cur.fetchone()

                if existing:
                    return jsonify({
                        "success": False,
                        "message": "Join request already exists."
                    }), 400

                cur.execute(
                    """
                    INSERT INTO mentor_join_requests (
                        student_id,
                        mentor_id,
                        status
                    )
                    VALUES (%s, %s, 'pending')
                    RETURNING id
                    """,
                    (
                        student_id,
                        mentor_id,
                    ),
                )

                request_id = cur.fetchone()[0]

            conn.commit()

        return jsonify({
            "success": True,
            "message": "Join request sent.",
            "request_id": request_id,
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Failed to send join request.",
            "error": str(error),
        }), 500


@app.route(
    "/api/mentor/join-requests/<int:mentor_id>",
    methods=["GET"],
)
def get_join_requests(mentor_id):
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        r.id,
                        r.student_id,
                        u.name,
                        u.email,
                        r.status,
                        r.created_at
                    FROM mentor_join_requests r
                    JOIN users u
                        ON u.id = r.student_id
                    WHERE r.mentor_id = %s
                    ORDER BY r.created_at DESC
                    """,
                    (mentor_id,),
                )

                rows = cur.fetchall()

        requests_list = []

        for row in rows:
            requests_list.append({
                "id": row[0],
                "student_id": row[1],
                "student_name": row[2],
                "student_email": row[3],
                "status": row[4],
                "created_at": row[5].isoformat()
                if row[5]
                else None,
            })

        return jsonify({
            "success": True,
            "requests": requests_list,
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Failed to fetch join requests.",
            "error": str(error),
        }), 500


@app.route(
    "/api/join-requests/<int:request_id>/review",
    methods=["PUT"],
)
def review_join_request(request_id):
    try:
        data = request.json

        status = data.get("status")

        if status not in ["approved", "rejected"]:
            return jsonify({
                "success": False,
                "message": "Invalid status."
            }), 400

        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        student_id,
                        mentor_id
                    FROM mentor_join_requests
                    WHERE id = %s
                    """,
                    (request_id,),
                )

                row = cur.fetchone()

                if not row:
                    return jsonify({
                        "success": False,
                        "message": "Join request not found."
                    }), 404

                student_id = row[0]
                mentor_id = row[1]

                cur.execute(
                    """
                    UPDATE mentor_join_requests
                    SET status = %s
                    WHERE id = %s
                    """,
                    (
                        status,
                        request_id,
                    ),
                )

                if status == "approved":

                    cur.execute(
                        """
                        SELECT id
                        FROM mentor_groups
                        WHERE mentor_id = %s
                        ORDER BY id
                        LIMIT 1
                        """,
                        (mentor_id,),
                    )

                    group = cur.fetchone()

                    if not group:
                        cur.execute(
                            """
                            INSERT INTO mentor_groups (
                                name,
                                mentor_id
                            )
                            VALUES (%s, %s)
                            RETURNING id
                            """,
                            (
                                "My Group",
                                mentor_id,
                            ),
                        )

                        group_id = cur.fetchone()[0]

                    else:
                        group_id = group[0]

                    cur.execute(
                        """
                        INSERT INTO group_members (
                            group_id,
                            student_id
                        )
                        VALUES (%s, %s)
                        ON CONFLICT (group_id, student_id)
                        DO NOTHING
                        """,
                        (
                            group_id,
                            student_id,
                        ),
                    )

            conn.commit()

        return jsonify({
            "success": True,
            "message": f"Join request {status}.",
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Failed to review join request.",
            "error": str(error),
        }), 500


# ---------------------------------------------------------
# MENTORS
# ---------------------------------------------------------

@app.route("/api/mentors", methods=["GET"])
def get_mentors():
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        id,
                        name,
                        email,
                        department,
                        year
                    FROM users
                    WHERE LOWER(role) = 'mentor'
                    ORDER BY name
                    """
                )

                rows = cur.fetchall()

        mentors = []

        for row in rows:
            mentors.append({
                "id": row[0],
                "name": row[1],
                "email": row[2],
                "department": row[3],
                "year": row[4],
            })

        return jsonify({
            "success": True,
            "mentors": mentors,
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Failed to fetch mentors.",
            "error": str(error),
        }), 500


# ---------------------------------------------------------
# STUDENT JOIN REQUESTS
# ---------------------------------------------------------

@app.route(
    "/api/student/join-requests/<int:student_id>",
    methods=["GET"],
)
def get_student_join_requests(student_id):
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        r.id,
                        r.mentor_id,
                        u.name AS mentor_name,
                        u.email AS mentor_email,
                        r.status,
                        r.created_at
                    FROM mentor_join_requests r
                    JOIN users u
                        ON u.id = r.mentor_id
                    WHERE r.student_id = %s
                    ORDER BY r.created_at DESC
                    """,
                    (student_id,),
                )

                rows = cur.fetchall()

        requests_list = []

        for row in rows:
            requests_list.append({
                "id": row[0],
                "mentor_id": row[1],
                "mentor_name": row[2],
                "mentor_email": row[3],
                "status": row[4],
                "created_at": row[5].isoformat()
                if row[5]
                else None,
            })

        return jsonify({
            "success": True,
            "requests": requests_list,
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Failed to fetch student join requests.",
            "error": str(error),
        }), 500


# ---------------------------------------------------------
# ACCEPT JOIN REQUEST
# ---------------------------------------------------------

@app.route(
    "/api/mentor/join-requests/<int:request_id>/accept",
    methods=["POST"],
)
def accept_join_request(request_id):
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        student_id,
                        mentor_id
                    FROM mentor_join_requests
                    WHERE id = %s
                    """,
                    (request_id,),
                )

                row = cur.fetchone()

                if not row:
                    return jsonify({
                        "success": False,
                        "message": "Join request not found."
                    }), 404

                student_id = row[0]
                mentor_id = row[1]

                cur.execute(
                    """
                    UPDATE mentor_join_requests
                    SET status = 'approved'
                    WHERE id = %s
                    """,
                    (request_id,),
                )

                cur.execute(
                    """
                    SELECT id
                    FROM mentor_groups
                    WHERE mentor_id = %s
                    ORDER BY id
                    LIMIT 1
                    """,
                    (mentor_id,),
                )

                group = cur.fetchone()

                if not group:
                    cur.execute(
                        """
                        INSERT INTO mentor_groups (
                            name,
                            mentor_id
                        )
                        VALUES (%s, %s)
                        RETURNING id
                        """,
                        (
                            "My Group",
                            mentor_id,
                        ),
                    )

                    group_id = cur.fetchone()[0]

                else:
                    group_id = group[0]

                cur.execute(
                    """
                    INSERT INTO group_members (
                        group_id,
                        student_id
                    )
                    VALUES (%s, %s)
                    ON CONFLICT (group_id, student_id)
                    DO NOTHING
                    """,
                    (
                        group_id,
                        student_id,
                    ),
                )

            conn.commit()

        return jsonify({
            "success": True,
            "message": "Student added to mentor group.",
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Failed to accept join request.",
            "error": str(error),
        }), 500


# ---------------------------------------------------------
# LOGIN
# ---------------------------------------------------------

@app.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.json

        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({
                "success": False,
                "message": "Email and password are required."
            }), 400

        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        id,
                        name,
                        email,
                        password,
                        role,
                        department,
                        year,
                        section,
                        register_number,
                        roll_number
                    FROM users
                    WHERE LOWER(email) = LOWER(%s)
                    LIMIT 1
                    """,
                    (email,),
                )

                user = cur.fetchone()

        if not user:
            return jsonify({
                "success": False,
                "message": "User not found."
            }), 404

        if user[3] != password:
            return jsonify({
                "success": False,
                "message": "Invalid password."
            }), 401

        return jsonify({
            "success": True,
            "message": "Login successful.",
            "user": {
                "id": user[0],
                "name": user[1],
                "email": user[2],
                "role": user[4],
                "department": user[5],
                "year": user[6],
                "section": user[7],
                "register_number": user[8],
                "roll_number": user[9],
            },
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Login failed.",
            "error": str(error),
        }), 500


# ---------------------------------------------------------
# REGISTER
# ---------------------------------------------------------

@app.route("/api/register", methods=["POST"])
def register():
    try:
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
                "message": "Name, email, password and role are required."
            }), 400

        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT id
                    FROM users
                    WHERE LOWER(email) = LOWER(%s)
                    LIMIT 1
                    """,
                    (email,),
                )

                existing = cur.fetchone()

                if existing:
                    return jsonify({
                        "success": False,
                        "message": "Email already registered."
                    }), 409

                cur.execute(
                    """
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
                    """,
                    (
                        name,
                        email,
                        password,
                        role,
                        department,
                        year,
                        section,
                        register_number,
                        roll_number,
                    ),
                )

                user_id = cur.fetchone()[0]

            conn.commit()

        return jsonify({
            "success": True,
            "message": "Registration successful.",
            "user_id": user_id,
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Registration failed.",
            "error": str(error),
        }), 500


# ---------------------------------------------------------
# MENTOR GROUPS
# ---------------------------------------------------------

@app.route(
    "/api/mentor/groups/<int:mentor_id>",
    methods=["GET"],
)
def mentor_groups(mentor_id):
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        id,
                        name,
                        created_at
                    FROM mentor_groups
                    WHERE mentor_id = %s
                    ORDER BY id
                    """,
                    (mentor_id,),
                )

                rows = cur.fetchall()

        groups = []

        for row in rows:
            groups.append({
                "id": row[0],
                "name": row[1],
                "created_at": row[2].isoformat()
                if row[2]
                else None,
            })

        return jsonify({
            "success": True,
            "groups": groups,
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Failed to fetch mentor groups.",
            "error": str(error),
        }), 500


# ---------------------------------------------------------
# STUDENT GROUP
# ---------------------------------------------------------

@app.route(
    "/api/student/group/<int:student_id>",
    methods=["GET"],
)
def student_group(student_id):
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        g.id,
                        g.name,
                        g.mentor_id,
                        u.name,
                        u.email
                    FROM group_members gm
                    JOIN mentor_groups g
                        ON g.id = gm.group_id
                    JOIN users u
                        ON u.id = g.mentor_id
                    WHERE gm.student_id = %s
                    ORDER BY g.id
                    LIMIT 1
                    """,
                    (student_id,),
                )

                row = cur.fetchone()

        if not row:
            return jsonify({
                "success": True,
                "group": None,
            })

        return jsonify({
            "success": True,
            "group": {
                "id": row[0],
                "name": row[1],
                "mentor_id": row[2],
                "mentor_name": row[3],
                "mentor_email": row[4],
            },
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Failed to fetch student group.",
            "error": str(error),
        }), 500


# ---------------------------------------------------------
# STUDENT PLATFORM
# ---------------------------------------------------------

@app.route(
    "/api/student/platforms",
    methods=["POST"],
)
def save_student_platform():
    try:
        data = request.json

        student_id = data.get("student_id")
        platform = data.get("platform")
        username = data.get("username")
        profile_url = data.get("profile_url")

        if not student_id or not platform or not username:
            return jsonify({
                "success": False,
                "message": (
                    "Student ID, platform and username are required."
                ),
            }), 400

        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    INSERT INTO student_platforms (
                        student_id,
                        platform,
                        username,
                        profile_url,
                        verified
                    )
                    VALUES (%s, %s, %s, %s, FALSE)
                    ON CONFLICT (student_id, platform)
                    DO UPDATE SET
                        username = EXCLUDED.username,
                        profile_url = EXCLUDED.profile_url
                    RETURNING id
                    """,
                    (
                        student_id,
                        platform,
                        username,
                        profile_url,
                    ),
                )

                platform_id = cur.fetchone()[0]

            conn.commit()

        return jsonify({
            "success": True,
            "message": "Platform saved successfully.",
            "id": platform_id,
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Failed to save platform.",
            "error": str(error),
        }), 500


@app.route(
    "/api/student/platforms/<int:student_id>",
    methods=["GET"],
)
def get_student_platforms(student_id):
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        id,
                        platform,
                        username,
                        profile_url,
                        verified,
                        verified_at
                    FROM student_platforms
                    WHERE student_id = %s
                    ORDER BY platform
                    """,
                    (student_id,),
                )

                rows = cur.fetchall()

        platforms = []

        for row in rows:
            platforms.append({
                "id": row[0],
                "platform": row[1],
                "username": row[2],
                "profile_url": row[3],
                "verified": row[4],
                "verified_at": row[5].isoformat()
                if row[5]
                else None,
            })

        return jsonify({
            "success": True,
            "platforms": platforms,
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Failed to fetch student platforms.",
            "error": str(error),
        }), 500


# ---------------------------------------------------------
# LEETCODE MANUAL VERIFICATION
# ---------------------------------------------------------

@app.route(
    "/api/verify/leetcode/<int:submission_id>",
    methods=["POST"],
)
def verify_leetcode_submission_route(submission_id):
    data, status_code = verify_leetcode_submission_logic(
        submission_id,
        DB_CONFIG,
    )

    return jsonify(data), status_code


# ---------------------------------------------------------
# LEETCODE BATCH VERIFICATION
# ---------------------------------------------------------

@app.route(
    "/api/verify/leetcode/batch",
    methods=["POST"],
)
def verify_leetcode_batch():
    summary = run_batch_leetcode_verification(
        DB_CONFIG
    )

    status_code = 200 if summary.get("success") else 500

    return jsonify(summary), status_code


# ---------------------------------------------------------
# STUDENT TASKS
# ---------------------------------------------------------

@app.route(
    "/api/student/tasks/<int:student_id>",
    methods=["GET"],
)
def student_tasks(student_id):
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        t.id,
                        t.group_id,
                        t.title,
                        t.description,
                        t.task_date,
                        t.platform,
                        t.problem_url,
                        t.problem_identifier,
                        t.assigned_at,
                        s.id AS submission_id,
                        s.status AS submission_status,
                        s.answer,
                        s.screenshot_url,
                        s.external_submission_id
                    FROM tasks t
                    JOIN group_members gm
                        ON gm.group_id = t.group_id
                    LEFT JOIN submissions s
                        ON s.task_id = t.id
                        AND s.student_id = %s
                    WHERE gm.student_id = %s
                    ORDER BY t.task_date DESC, t.id DESC
                    """,
                    (
                        student_id,
                        student_id,
                    ),
                )

                rows = cur.fetchall()

        tasks = []

        for row in rows:
            tasks.append({
                "id": row[0],
                "group_id": row[1],
                "title": row[2],
                "description": row[3],
                "task_date": row[4].isoformat()
                if row[4]
                else None,
                "platform": row[5],
                "problem_url": row[6],
                "problem_identifier": row[7],
                "assigned_at": row[8].isoformat()
                if row[8]
                else None,
                "submission_id": row[9],
                "submission_status": row[10],
                "answer": row[11],
                "screenshot_url": row[12],
                "external_submission_id": row[13],
            })

        return jsonify({
            "success": True,
            "tasks": tasks,
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Failed to fetch student tasks.",
            "error": str(error),
        }), 500


# ---------------------------------------------------------
# STUDENT POINTS
# ---------------------------------------------------------

@app.route(
    "/api/student/points/<int:student_id>",
    methods=["GET"],
)
def student_points(student_id):
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        COALESCE(SUM(points), 0),
                        COUNT(
                            DISTINCT CASE
                                WHEN points > 0
                                THEN submission_id
                            END
                        )
                    FROM student_points
                    WHERE student_id = %s
                    """,
                    (student_id,),
                )

                row = cur.fetchone()

        return jsonify({
            "success": True,
            "total_points": row[0],
            "verified_tasks": row[1],
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "Failed to fetch student points.",
            "error": str(error),
        }), 500


# ---------------------------------------------------------
# CODETRACK AI
# ---------------------------------------------------------

@app.route(
    "/api/ai/chat",
    methods=["POST"],
)
def ai_chat():
    try:
        data = request.json

        student_id = data.get("student_id")
        message = data.get("message")

        if not message:
            return jsonify({
                "success": False,
                "message": "Message is required."
            }), 400

        student_name = None
        department = None
        year = None

        if student_id:
            try:
                with psycopg.connect(**DB_CONFIG) as conn:
                    with conn.cursor() as cur:

                        cur.execute(
                            """
                            SELECT
                                name,
                                department,
                                year
                            FROM users
                            WHERE id = %s
                            """,
                            (student_id,),
                        )

                        user = cur.fetchone()

                        if user:
                            student_name = user[0]
                            department = user[1]
                            year = user[2]

            except Exception as user_error:
                print(
                    "Could not load student information:",
                    user_error,
                )

        prompt = build_prompt(
            message=message,
            student_name=student_name,
            department=department,
            year=year,
        )

        response = ask_codetrack_ai(prompt)

        return jsonify({
            "success": True,
            "response": response,
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": "AI request failed.",
            "error": str(error),
        }), 500


# ---------------------------------------------------------
# SCHEDULED LEETCODE VERIFICATION
# ---------------------------------------------------------

def scheduled_leetcode_verification():
    try:
        run_batch_leetcode_verification(
            DB_CONFIG
        )
    except Exception as error:
        print(
            "Scheduled LeetCode verification error:",
            error,
        )


def start_verification_scheduler():
    try:
        from apscheduler.schedulers.background import (
            BackgroundScheduler,
        )

        scheduler = BackgroundScheduler()

        scheduler.add_job(
            scheduled_leetcode_verification,
            "interval",
            minutes=5,
            id="leetcode_verification",
            replace_existing=True,
        )

        scheduler.start()

        print(
            "Automatic LeetCode verification scheduler "
            "started (every 5 minutes, all students)."
        )

        return scheduler

    except Exception as error:
        print(
            "Could not start verification scheduler:",
            error,
        )

        return None


# ---------------------------------------------------------
# STARTUP
# ---------------------------------------------------------

if __name__ == "__main__":

    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    ALTER TABLE submissions
                    ADD COLUMN IF NOT EXISTS screenshot_url TEXT
                    """
                )

            conn.commit()

    except Exception as error:
        print(
            "Database startup check failed:",
            error,
        )

    start_verification_scheduler()

    port = int(os.getenv("PORT", "5000"))

    app.run(
        debug=True,
        host="0.0.0.0",
        port=port
    )