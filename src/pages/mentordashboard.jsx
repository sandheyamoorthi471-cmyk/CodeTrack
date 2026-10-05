import { useEffect, useState } from "react";

function MentorDashboard() {

  // =========================
  // Logged-in mentor
  // =========================

  const savedUser =
    localStorage.getItem("codetrackUser");

  const user =
    savedUser
      ? JSON.parse(savedUser)
      : null;

  const mentorId = user?.id;


  // =========================
  // Groups
  // =========================

  const [groups, setGroups] = useState([]);

  const [selectedGroup, setSelectedGroup] =
    useState("");

  const [loadingGroups, setLoadingGroups] =
    useState(true);


  // =========================
  // Task form
  // =========================

  const [taskTitle, setTaskTitle] =
    useState("");

  const [description, setDescription] =
    useState("");

  const [platform, setPlatform] =
    useState("");

  const [taskUrl, setTaskUrl] =
    useState("");

  const [problemIdentifier, setProblemIdentifier] =
    useState("");

  const [deadline, setDeadline] =
    useState("");


  // =========================
  // Join requests
  // =========================

  const [joinRequests, setJoinRequests] =
    useState([]);

  const [loadingRequests, setLoadingRequests] =
    useState(true);


  // =========================
  // Student progress
  // =========================

  const [students, setStudents] =
    useState([]);

  const [loadingStudents, setLoadingStudents] =
    useState(true);


  // =========================
  // Fetch groups
  // =========================

  const fetchGroups = async () => {

    if (!mentorId) return;

    setLoadingGroups(true);

    try {

      const response = await fetch(
        `http://127.0.0.1:5000/api/mentor/groups/${mentorId}`
      );

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.error ||
          "Failed to load groups"
        );
      }

      setGroups(data.groups || []);

      if (
        data.groups &&
        data.groups.length > 0
      ) {
        setSelectedGroup(
          String(data.groups[0].id)
        );
      }

    } catch (error) {

      console.error(
        "Group loading error:",
        error
      );

    } finally {

      setLoadingGroups(false);

    }
  };


  // =========================
  // Fetch join requests
  // =========================

  const fetchJoinRequests = async () => {

    if (!mentorId) return;

    try {

      const response = await fetch(
        `http://127.0.0.1:5000/api/mentor/join-requests/${mentorId}`
      );

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.error ||
          "Failed to load join requests"
        );
      }

      setJoinRequests(
        data.requests || []
      );

    } catch (error) {

      console.error(
        "Join request error:",
        error
      );

    } finally {

      setLoadingRequests(false);

    }
  };


  // =========================
  // Fetch student progress
  // =========================

  const fetchStudentProgress = async () => {

    if (!mentorId) {
      setLoadingStudents(false);
      return;
    }

    setLoadingStudents(true);

    try {

      const response = await fetch(
        `http://127.0.0.1:5000/api/mentor/progress/${mentorId}`
      );

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.error ||
          "Failed to load student progress"
        );
      }

      setStudents(
        data.students || []
      );

    } catch (error) {

      console.error(
        "Student progress error:",
        error
      );

    } finally {

      setLoadingStudents(false);

    }
  };


  // =========================
  // Initial loading
  // =========================

  useEffect(() => {

    fetchGroups();
    fetchJoinRequests();
    fetchStudentProgress();

  }, [mentorId]);


  // =========================
  // Accept request
  // =========================

  const handleAccept = async (
    requestId
  ) => {

    try {

      const response = await fetch(
        `http://127.0.0.1:5000/api/mentor/join-requests/${requestId}/accept`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
        }
      );

      const data =
        await response.json();

      if (
        !response.ok ||
        !data.success
      ) {
        throw new Error(
          data.error ||
          "Failed to accept request"
        );
      }

      alert(
        "Student accepted successfully! ✅"
      );

      await fetchJoinRequests();
      await fetchGroups();
      await fetchStudentProgress();

    } catch (error) {

      console.error(error);

      alert(
        "Failed to accept student: " +
        error.message
      );

    }
  };


  // =========================
  // Reject request
  // =========================

  const handleReject = async (
    requestId
  ) => {

    try {

      const response = await fetch(
        `http://127.0.0.1:5000/api/mentor/join-requests/${requestId}/review`,
        {
          method: "PUT",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            status: "rejected",
          }),
        }
      );

      const data =
        await response.json();

      if (
        !response.ok ||
        !data.success
      ) {
        throw new Error(
          data.error ||
          "Failed to reject request"
        );
      }

      alert(
        "Student request rejected. ❌"
      );

      fetchJoinRequests();

    } catch (error) {

      console.error(error);

      alert(
        "Failed to reject request: " +
        error.message
      );

    }
  };


  const handleReviewSubmission = async (
    submissionId,
    status
  ) => {
    try {
      const response = await fetch(
        `http://127.0.0.1:5000/api/submissions/${submissionId}/review`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ status }),
        }
      );
      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.error || "Review failed");
      }

      await fetchStudentProgress();
    } catch (error) {
      alert("Failed to review submission: " + error.message);
    }
  };


  // =========================
  // Post task
  // =========================

  const handlePostTask = async () => {

    if (
      !taskTitle.trim() ||
      !description.trim() ||
      !platform ||
      !taskUrl.trim() ||
      !deadline
    ) {

      alert(
        "Please fill all required task fields."
      );

      return;
    }

    if (!selectedGroup) {

      alert(
        "Please select a student group."
      );

      return;
    }

    try {

      const response = await fetch(
        "http://127.0.0.1:5000/api/tasks",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({

            group_id:
              Number(selectedGroup),

            title:
              taskTitle.trim(),

            description:
              description.trim(),

            task_date:
              deadline.split("T")[0],

            platform:
              platform,

            problem_url:
              taskUrl.trim(),

            problem_identifier:
              problemIdentifier.trim(),

          }),
        }
      );

      const data =
        await response.json();

      if (
        !response.ok ||
        !data.success
      ) {
        throw new Error(
          data.error ||
          "Failed to create task"
        );
      }

      alert(
        "Task posted successfully! 🎉"
      );

      setTaskTitle("");
      setDescription("");
      setPlatform("");
      setTaskUrl("");
      setProblemIdentifier("");
      setDeadline("");

      // Refresh progress because
      // students now have another task.
      await fetchStudentProgress();

    } catch (error) {

      console.error(error);

      alert(
        "Failed to post task: " +
        error.message
      );

    }
  };


  // =========================
  // Logout
  // =========================

  const handleLogout = () => {

    localStorage.removeItem(
      "codetrackUser"
    );

    window.location.reload();

  };


  // =========================
  // Render
  // =========================

  return (

    <div className="dashboard">

      {/* =========================
          Navbar
      ========================= */}

      <header className="navbar">

        <h1>
          CodeTrack
        </h1>

        <div>

          <span>
            Mentor
          </span>

          <button
            onClick={handleLogout}
          >
            Logout
          </button>

        </div>

      </header>


      <main className="dashboard-content">

        {/* =========================
            Welcome
        ========================= */}

        <h2>
          Welcome{" "}
          {user?.name || "Mentor"} 👋
        </h2>

        <p>
          Manage your students and daily
          coding tasks.
        </p>


        {/* =========================
            Student Progress
        ========================= */}

        <section className="section-card">

          <h2>
            📊 Student Progress
          </h2>

          {loadingStudents && (
            <p>
              Loading student progress...
            </p>
          )}

          {!loadingStudents &&
            students.length === 0 && (
              <p>
                👥 No students in your groups yet.
              </p>
            )}

          {!loadingStudents &&
            students.map((student) => (

              <div
                className="problem"
                key={
                  `${student.group_id}-${student.student_id}`
                }
              >

                <div>

                  <h3>
                    👨‍🎓{" "}
                    {student.student_name}
                  </h3>

                  <p>
                    📧{" "}
                    {student.student_email}
                  </p>

                  <p>
                    👥 Group:{" "}
                    <strong>
                      {student.group_name}
                    </strong>
                  </p>

                  <p>
                    📝 Tasks:{" "}
                    <strong>
                      {student.submitted_tasks}
                    </strong>
                    {" / "}
                    {student.total_tasks}
                  </p>

                  <p>
                    ✅ Verified:{" "}
                    <strong>
                      {student.verified_tasks}
                    </strong>
                  </p>

                  <p>
                    🏆 Points:{" "}
                    <strong>
                      {student.total_points}
                    </strong>
                  </p>

                  <p>
                    📈 Progress:{" "}
                    <strong>
                      {student.progress}%
                    </strong>
                  </p>

                  {student.review_tasks > 0 && (
                    <p>
                      🖼️ <strong>
                        {student.review_tasks} proof screenshot(s) need mentor review
                      </strong>
                    </p>
                  )}

                  <div>
                    <strong>Problems</strong>
                    {student.problems?.length ? (
                      student.problems.map((problem) => (
                        <div key={problem.task_id}>
                          <p>
                            {problem.status === "solved" ? "✅" : "⏳"}{" "}
                            {problem.title || problem.problem_identifier}
                            {problem.problem_identifier && (
                              <> ({problem.problem_identifier})</>
                            )}
                            {" - "}
                            {problem.status === "solved"
                              ? "Solved"
                              : problem.status === "submitted"
                                ? "Submitted"
                                : "Not solved"}
                          </p>
                          {problem.needs_review && (
                            <p>
                              ⚠️ Automatic verification failed. Mentor review required.
                            </p>
                          )}
                          {problem.screenshot_url && (
                            <p>
                              <a
                                href={`http://127.0.0.1:5000${problem.screenshot_url}`}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                View proof screenshot
                              </a>
                            </p>
                          )}
                          {problem.screenshot_url &&
                            problem.submission_id &&
                            problem.status !== "solved" && (
                              <p>
                                <button
                                  onClick={() =>
                                    handleReviewSubmission(
                                      problem.submission_id,
                                      "approved"
                                    )
                                  }
                                >
                                  Approve screenshot
                                </button>{" "}
                                <button
                                  onClick={() =>
                                    handleReviewSubmission(
                                      problem.submission_id,
                                      "rejected"
                                    )
                                  }
                                >
                                  Reject
                                </button>
                              </p>
                            )}
                        </div>
                      ))
                    ) : (
                      <p>No assigned problems yet.</p>
                    )}
                  </div>

                </div>

              </div>

            ))}

        </section>


        {/* =========================
            Student Leaderboard
        ========================= */}

        <section className="section-card">

          <h2>
            🏆 Group Points
          </h2>

          {students.length === 0 ? (

            <p>
              No student points yet.
            </p>

          ) : (

            students.map(
              (student, index) => (

                <div
                  className="problem"
                  key={
                    `leaderboard-${student.group_id}-${student.student_id}`
                  }
                >

                  <div>

                    <h3>
                      #{index + 1}{" "}
                      {student.student_name}
                    </h3>

                    <p>
                      👥{" "}
                      {student.group_name}
                    </p>

                  </div>

                  <strong>
                    🏆{" "}
                    {student.total_points}
                    {" points"}
                  </strong>

                </div>

              )
            )

          )}

        </section>


        {/* =========================
            Join Requests
        ========================= */}

        <section className="section-card">

          <h2>
            📨 Student Join Requests
          </h2>

          {loadingRequests && (
            <p>
              Loading requests...
            </p>
          )}

          {!loadingRequests &&
            joinRequests.length === 0 && (
              <p>
                📭 No student requests yet.
              </p>
            )}

          {!loadingRequests &&
            joinRequests.map(
              (request) => (

                <div
                  className="problem"
                  key={request.id}
                >

                  <div>

                    <h3>
                      👨‍🎓{" "}
                      {request.student_name}
                    </h3>

                    <p>
                      📧{" "}
                      {request.student_email}
                    </p>

                    <p>
                      Status:{" "}
                      <strong>
                        {request.status ===
                        "pending"
                          ? "🟡 Pending"
                          : request.status ===
                            "accepted"
                          ? "🟢 Accepted"
                          : "🔴 Rejected"}
                      </strong>
                    </p>

                  </div>

                  {request.status ===
                    "pending" && (

                    <div>

                      <button
                        onClick={() =>
                          handleAccept(
                            request.id
                          )
                        }
                      >
                        ✅ Accept
                      </button>

                      <button
                        onClick={() =>
                          handleReject(
                            request.id
                          )
                        }
                      >
                        ❌ Reject
                      </button>

                    </div>

                  )}

                </div>

              )
            )}

        </section>


        {/* =========================
            My Groups
        ========================= */}

        <section className="section-card">

          <h2>
            👥 My Student Groups
          </h2>

          {loadingGroups && (
            <p>
              Loading groups...
            </p>
          )}

          {!loadingGroups &&
            groups.length === 0 && (
              <p>
                No groups found.
              </p>
            )}

          {!loadingGroups &&
            groups.length > 0 && (

              <>
                <label>
                  Select Group
                </label>

                <select
                  value={selectedGroup}
                  onChange={(e) =>
                    setSelectedGroup(
                      e.target.value
                    )
                  }
                >

                  {groups.map(
                    (group) => (

                      <option
                        key={group.id}
                        value={group.id}
                      >
                        {group.name}
                      </option>

                    )
                  )}

                </select>

              </>

            )}

        </section>


        {/* =========================
            Create Daily Task
        ========================= */}

        <section className="section-card">

          <h2>
            📝 Create Daily Task
          </h2>

          <label>
            Task Title
          </label>

          <input
            type="text"
            placeholder="Example: Solve 2 Array Problems"
            value={taskTitle}
            onChange={(e) =>
              setTaskTitle(
                e.target.value
              )
            }
          />

          <label>
            Description
          </label>

          <textarea
            placeholder="Describe what students need to do..."
            value={description}
            onChange={(e) =>
              setDescription(
                e.target.value
              )
            }
          />

          <label>
            Platform
          </label>

          <select
            value={platform}
            onChange={(e) =>
              setPlatform(
                e.target.value
              )
            }
          >

            <option value="">
              Select platform
            </option>

            <option value="leetcode">
              LeetCode
            </option>

            <option value="codeforces">
              Codeforces
            </option>

            <option value="hackerrank">
              HackerRank
            </option>

            <option value="other">
              Other
            </option>

          </select>

          <label>
            Problem URL
          </label>

          <input
            type="url"
            placeholder="https://..."
            value={taskUrl}
            onChange={(e) =>
              setTaskUrl(
                e.target.value
              )
            }
          />

          <label>
            Problem Identifier
          </label>

          <input
            type="text"
            placeholder="Example: two-sum"
            value={
              problemIdentifier
            }
            onChange={(e) =>
              setProblemIdentifier(
                e.target.value
              )
            }
          />

          <label>
            Deadline
          </label>

          <input
            type="datetime-local"
            value={deadline}
            onChange={(e) =>
              setDeadline(
                e.target.value
              )
            }
          />

          <button
            type="button"
            onClick={
              handlePostTask
            }
          >
            Post Task
          </button>

        </section>

      </main>

    </div>

  );
}

export default MentorDashboard;