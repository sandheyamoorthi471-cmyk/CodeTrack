import { useState, useEffect } from "react";
import { fetchStudentTasks } from "../tasks/studentTasks";
import { submitStudentProof } from "../submission/studentSubmission";
import { fetchStudentPlatformAccounts } from "../verification/studentPlatforms";
import { fetchStudentPoints } from "../points/studentPoints";
function StudentDashboard() {
  // =========================
  // Get logged-in student
  // =========================
  const savedUser = localStorage.getItem("codetrackUser");
  const user = savedUser ? JSON.parse(savedUser) : null;
  const studentId = user?.id;


  // =========================
  // Timer
  // =========================
  const [seconds, setSeconds] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [focusMode, setFocusMode] = useState(false);
  const [focusWarning, setFocusWarning] = useState("");

  // =========================
  // Tasks
  // =========================
  const [tasks, setTasks] = useState([]);
  const [loadingTasks, setLoadingTasks] = useState(true);

  // =========================
  // Mentors
  // =========================
  const [mentors, setMentors] = useState([]);
  const [selectedMentor, setSelectedMentor] = useState("");
  const [joinRequests, setJoinRequests] = useState([]);
  const [loadingMentors, setLoadingMentors] = useState(true);
  const [mentorError, setMentorError] = useState("");

  // =========================
  // Submission
  // =========================
  const [platform, setPlatform] = useState("LeetCode");
  const [problemUrl, setProblemUrl] = useState("");
  const [screenshot, setScreenshot] = useState(null);
  const [selectedTask, setSelectedTask] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // =========================
  // Points
  // =========================
  const [totalPoints, setTotalPoints] = useState(0);
  const [verifiedTasks, setVerifiedTasks] = useState(0);
  const [loadingPoints, setLoadingPoints] = useState(true);

  // =========================
  // Coding Platform Accounts
  // =========================
  const [platformAccounts, setPlatformAccounts] = useState([]);

  const [platformUrls, setPlatformUrls] = useState({
    Codeforces: "",
    LeetCode: "",
  });

  const [savingPlatform, setSavingPlatform] = useState("");
// =========================
// CodeTrack AI
// =========================
const [aiMessage, setAiMessage] = useState("");
const [aiResponse, setAiResponse] = useState("");
const [aiLoading, setAiLoading] = useState(false);
  // =========================
  // Fetch mentors
  // =========================
  const fetchMentors = async () => {
    setLoadingMentors(true);
    setMentorError("");

    try {
      const response = await fetch(
        "http://127.0.0.1:5000/api/mentors"
      );

      if (!response.ok) {
        throw new Error(
          "Server error: " + response.status
        );
      }

      const data = await response.json();

      if (!data.success) {
        throw new Error(
          data.error || "Failed to load mentors"
        );
      }

      setMentors(data.mentors || []);
    } catch (error) {
      console.error(
        "Mentor loading error:",
        error
      );

      setMentorError(
        "Unable to load mentors. Make sure Flask is running."
      );
    } finally {
      setLoadingMentors(false);
    }
  };

  // =========================
  // Fetch student's join requests
  // =========================
  const fetchJoinRequests = async () => {
    if (!studentId) return;

    try {
      const response = await fetch(
        `http://127.0.0.1:5000/api/student/join-requests/${studentId}`
      );

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.error || "Failed to load join requests"
        );
      }

      setJoinRequests(data.requests || []);
    } catch (error) {
      console.error(
        "Join request loading error:",
        error
      );
    }
  };

  // =========================
  // Fetch student's tasks
  // =========================
  const fetchTasks = () => {
  fetchStudentTasks(
    studentId,
    setTasks,
    setSelectedTask,
    setLoadingTasks
  );
};

  // =========================
  // Fetch student's points
  // =========================
  const fetchPoints = () => {
  fetchStudentPoints({
    studentId,
    setTotalPoints,
    setVerifiedTasks,
    setLoadingPoints,
  });
};

  // =========================
  // Fetch platform accounts
  // =========================
  const fetchPlatformAccounts = () => {
  fetchStudentPlatformAccounts({
    studentId,
    setPlatformAccounts,
    setPlatformUrls,
  });
};

  // =========================
  // Initial loading
  // =========================
  useEffect(() => {
    fetchMentors();
    fetchJoinRequests();
    fetchTasks();
    fetchPoints();
    fetchPlatformAccounts();
  }, []);

  // =========================
  // Timer
  // =========================
  useEffect(() => {
    let timer;

    if (isRunning) {
      timer = setInterval(() => {
        setSeconds((prev) => prev + 1);
      }, 1000);
    }

    return () => clearInterval(timer);
  }, [isRunning]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!focusMode) return;

      if (document.hidden) {
        setFocusWarning(
          "Coding timer is running. Return to CodeTrack when you finish."
        );
      } else {
        setFocusWarning(
          "Focus session active. Keep working on the selected coding task."
        );
      }
    };

    document.addEventListener(
      "visibilitychange",
      handleVisibilityChange
    );

    return () => {
      document.removeEventListener(
        "visibilitychange",
        handleVisibilityChange
      );
    };
  }, [focusMode]);

  const startFocusSession = () => {
    if (!selectedTask) {
      setFocusWarning("Choose a task before starting your focus session.");
      return;
    }

    setFocusMode(true);
    setFocusWarning("");
    setIsRunning(true);

    if (selectedTask?.problem_url) {
      window.open(
        selectedTask.problem_url,
        "_blank",
        "noopener,noreferrer"
      );
    }
  };

  const endFocusSession = () => {
    setFocusMode(false);
    setIsRunning(false);
    setFocusWarning("");
  };

  // =========================
  // Timer formatting
  // =========================
  const minutes = Math.floor(
    seconds / 60
  );

  const remainingSeconds =
    seconds % 60;

  const formattedTime =
    String(minutes).padStart(2, "0") +
    ":" +
    String(remainingSeconds).padStart(
      2,
      "0"
    );

  // =========================
  // Progress
  // =========================
  const progressPercentage =
    Math.min(
      (seconds / 3600) * 100,
      100
    );

  // =========================
  // Send mentor join request
  // =========================
  const handleJoinRequest = async () => {
    if (!selectedMentor) {
      alert(
        "Please select a mentor first."
      );
      return;
    }

    try {
      const response = await fetch(
        "http://127.0.0.1:5000/api/join-requests",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            student_id: studentId,
            mentor_id: Number(
              selectedMentor
            ),
          }),
        }
      );

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.error ||
            "Failed to send request"
        );
      }

      alert(
        "Join request sent successfully! 📨"
      );

      setSelectedMentor("");

      fetchJoinRequests();

    } catch (error) {
      console.error(
        "Join request error:",
        error
      );

      alert(
        "Failed to send join request: " +
          error.message
      );
    }
  };

  // =========================
  // Save platform profile
  // =========================
  const handleSavePlatform = async (
    platformName
  ) => {
    const profileUrl =
      platformUrls[platformName]?.trim();

    if (!profileUrl) {
      alert(
        `Please enter your ${platformName} profile URL.`
      );
      return;
    }

    setSavingPlatform(platformName);

    try {
      const response = await fetch(
        "http://127.0.0.1:5000/api/student/platforms",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            student_id: studentId,
            platform: platformName,
            profile_url: profileUrl,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.error ||
            "Failed to save platform profile"
        );
      }

      alert(
        `${platformName} profile connected successfully! 🔗`
      );

      await fetchPlatformAccounts();

    } catch (error) {
      console.error(
        "Platform profile save error:",
        error
      );

      alert(
        "Failed to connect profile: " +
          error.message
      );
    } finally {
      setSavingPlatform("");
    }
  };

  // =========================
  // Submit coding proof
  // =========================
  const handleSubmitProof = () => {
  submitStudentProof({
    selectedTask,
    problemUrl,
    platform,
    screenshot,
    studentId,
    setSubmitting,
    setProblemUrl,
    setScreenshot,
    setSelectedTask,
    fetchTasks,
    fetchPoints,
  });
};

  // =========================
  // Latest join request
  // =========================
  const latestRequest =
    joinRequests.length > 0
      ? joinRequests[0]
      : null;

  // =========================
  // Separate tasks
  // =========================
  const activeTasks = tasks.filter(
    (task) =>
      task.task_status !==
      "completed"
  );

  const completedTasks = tasks.filter(
    (task) =>
      task.task_status ===
      "completed"
  );
// =========================
// CodeTrack AI
// =========================
const handleAskAI = async () => {
  const message = aiMessage.trim();

  if (!message) {
    alert("Please enter a question.");
    return;
  }

  setAiLoading(true);
  setAiResponse("");

  try {
    const response = await fetch(
      "http://127.0.0.1:5000/api/ai/chat",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: message,
          student_id: studentId,
        }),
      }
    );

    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(
        data.error || "CodeTrack AI failed"
      );
    }

    setAiResponse(data.response || "");

  } catch (error) {
    console.error(
      "CodeTrack AI error:",
      error
    );

    setAiResponse(
      "❌ CodeTrack AI could not respond. Please make sure Ollama and Flask are running."
    );

  } finally {
    setAiLoading(false);
  }
};
  // =========================
  // Logout
  // =========================
  const handleLogout = () => {
    localStorage.clear();
    window.location.href = "/";
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

        <h1>CodeTrack</h1>

        <div>
          <span>Student</span>

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
          Welcome back! 👋
        </h2>

        <p>
          Keep your coding streak alive.
        </p>

        <div className="coding-easy-banner" aria-label="Coding is easy">
          <span className="coding-easy-spark" aria-hidden="true">✦</span>
          <span className="coding-easy-text">Coding is easy</span>
          <span className="coding-easy-cursor" aria-hidden="true" />
        </div>

        {/* =========================
    CodeTrack AI
========================= */}
<section className="section-card">

  <h2>🤖 CodeTrack AI</h2>

  <p>
    Your personal coding assistant. Ask about
    programming, algorithms, errors, or your
    CodeTrack tasks.
  </p>

  <textarea
    value={aiMessage}
    onChange={(e) =>
      setAiMessage(e.target.value)
    }
    placeholder="Ask CodeTrack AI something..."
    rows={4}
    style={{
      width: "100%",
      boxSizing: "border-box",
      resize: "vertical",
      marginTop: "10px",
      padding: "14px",
      borderRadius: "12px",
      border: "1px solid rgba(255,255,255,0.2)",
      background: "rgba(255,255,255,0.06)",
      color: "inherit",
      fontSize: "16px",
    }}
  />

  <button
    onClick={handleAskAI}
    disabled={aiLoading}
    style={{
      marginTop: "12px",
    }}
  >
    {aiLoading
      ? "🤖 Thinking..."
      : "Ask CodeTrack AI 🚀"}
  </button>

  {aiResponse && (
    <div
      style={{
        marginTop: "20px",
        padding: "18px",
        borderRadius: "14px",
        background:
          "rgba(0,123,255,0.08)",
        border:
          "1px solid rgba(0,123,255,0.25)",
        whiteSpace: "pre-wrap",
        lineHeight: "1.6",
      }}
    >
      <h3>🤖 CodeTrack AI</h3>

      <p>
        {aiResponse}
      </p>
    </div>
  )}

</section>

        {/* =========================
            Stats
        ========================= */}
        <section className="stats">

          <div className="card">

            <h3>
              🏆 Total Points
            </h3>

            <p>
              {loadingPoints
                ? "Loading..."
                : totalPoints}
            </p>

            <small>
              Earned from verified tasks
            </small>

          </div>

          <div className="card">

            <h3>
              ✅ Verified Tasks
            </h3>

            <p>
              {loadingPoints
                ? "Loading..."
                : verifiedTasks}
            </p>

            <small>
              Automatically verified
            </small>

          </div>

          <div className="card">

            <h3>
              ⏱️ Focus Time
            </h3>

            <p>
              {formattedTime}
            </p>

          </div>

          <div className="card">

            <h3
              style={{
                color: "#007bff",
              }}
            >
              🎯 Today's Goal
            </h3>

            <p>
              60 Minutes
            </p>

          </div>

        </section>

        {/* =========================
            Mentor Selection
        ========================= */}
        <section className="section-card">

          {latestRequest &&
          latestRequest.status ===
            "accepted" ? (

            <>
              <h2>
                👨‍🏫 Your Mentor
              </h2>

              <div className="mentor-info">

                <h3>
                  {
                    latestRequest.mentor_name
                  }
                </h3>

                <p>
                  🟢 Mentor request accepted
                </p>

              </div>
            </>

          ) : (

            <>
              <h2>
                👨‍🏫 Choose Your Mentor
              </h2>

              <p>
                Select a mentor and send a
                request to join their student
                group.
              </p>

              {mentorError && (
                <p
                  style={{
                    color: "red",
                  }}
                >
                  {mentorError}
                </p>
              )}

              {latestRequest &&
              latestRequest.status ===
                "pending" && (

                <p>
                  ⏳ Waiting for{" "}
                  <strong>
                    {
                      latestRequest.mentor_name
                    }
                  </strong>{" "}
                  to approve your request.
                </p>

              )}

              <label>
                Mentor
              </label>

              <select
                value={selectedMentor}
                onChange={(e) =>
                  setSelectedMentor(
                    e.target.value
                  )
                }
              >

                <option value="">
                  {loadingMentors
                    ? "Loading mentors..."
                    : "Select a mentor"}
                </option>

                {!loadingMentors &&
                  mentors.map(
                    (mentor) => (

                      <option
                        key={mentor.id}
                        value={mentor.id}
                      >
                        {mentor.name} —{" "}
                        {mentor.email}
                      </option>

                    )
                  )}

              </select>

              <button
                onClick={
                  handleJoinRequest
                }
                disabled={
                  loadingMentors ||
                  latestRequest?.status ===
                    "pending"
                }
              >
                Send Join Request 📨
              </button>

            </>

          )}

        </section>

        {/* =========================
            Coding Platform Accounts
        ========================= */}
        <section className="section-card">

          <h2>
            🔗 Coding Platform Accounts
          </h2>

          <p>
            Connect your coding-platform
            profile so CodeTrack can use it
            for automatic task verification.
          </p>

          <label>
            Codeforces Profile URL
          </label>

          <input
            type="text"
            placeholder="https://codeforces.com/profile/username"
            value={
              platformUrls.Codeforces
            }
            onChange={(e) =>
              setPlatformUrls({
                ...platformUrls,
                Codeforces:
                  e.target.value,
              })
            }
          />

          <button
            onClick={() =>
              handleSavePlatform(
                "Codeforces"
              )
            }
            disabled={
              savingPlatform ===
              "Codeforces"
            }
          >
            {savingPlatform ===
            "Codeforces"
              ? "Connecting..."
              : "Connect Codeforces"}
          </button>

          <label>
            LeetCode Profile URL
          </label>

          <input
            type="text"
            placeholder="https://leetcode.com/u/username/"
            value={
              platformUrls.LeetCode
            }
            onChange={(e) =>
              setPlatformUrls({
                ...platformUrls,
                LeetCode:
                  e.target.value,
              })
            }
          />

          <button
            onClick={() =>
              handleSavePlatform(
                "LeetCode"
              )
            }
            disabled={
              savingPlatform ===
              "LeetCode"
            }
          >
            {savingPlatform ===
            "LeetCode"
              ? "Connecting..."
              : "Connect LeetCode"}
          </button>

          <label>
            SkillRack Profile
          </label>

          <input
            type="text"
            placeholder="SkillRack support coming next"
            disabled
          />

          <button disabled>
            SkillRack — Coming Soon
          </button>

          {platformAccounts.length >
            0 && (

            <div
              style={{
                marginTop: "25px",
              }}
            >

              <h3>
                Connected Accounts
              </h3>
              {platformAccounts.map(
                (account) => (

                  <div
                    key={account.id}
                    style={{
                      marginBottom: "18px",
                      padding: "12px",
                      borderRadius: "12px",
                      background:
                        "rgba(255,255,255,0.06)",
                    }}
                  >

                    <p>
                      <strong>
                        {account.platform}
                      </strong>
                    </p>

                    <p>
                      Username:{" "}
                      {account.username}
                    </p>

                    <p>
                      Status:{" "}

                      {account.verified
                        ? "🟢 Verified"
                        : "🟡 Connected — verification pending"}
                    </p>

                    {account.profile_url && (

                      <p
                        style={{
                          wordBreak:
                            "break-all",
                        }}
                      >
                        Profile:{" "}
                        {account.profile_url}
                      </p>

                    )}

                  </div>

                )
              )}

            </div>

          )}

        </section>

        {/* =========================
            My Tasks
        ========================= */}
        <section className="section-card">

          <h2>
            📚 My Tasks
          </h2>

          {loadingTasks && (
            <p>
              Loading tasks...
            </p>
          )}

          {!loadingTasks &&
            activeTasks.length === 0 && (
              <p>
                🎉 No active tasks! You are all caught up.
              </p>
            )}

          {!loadingTasks &&
            activeTasks.map((task) => (

              <div
                className="problem"
                key={task.id}
              >

                <div>

                  <h3>
                    {task.title}
                  </h3>

                  <p>
                    {task.description}
                  </p>

                  <p>
                    👥 {task.group_name}
                  </p>

                  <p>
                    📅 {task.task_date}
                  </p>

                  <p>
                    {task.task_status === "completed"
                      ? "✅ Solved"
                      : task.task_status === "submitted"
                        ? "🟡 Submitted - verification pending"
                        : task.task_status === "rejected"
                          ? "❌ Verification rejected"
                          : "⚪ Not solved"}
                  </p>

                  {task.platform && (
                    <p>
                      💻 Platform:{" "}
                      <strong>
                        {task.platform}
                      </strong>
                    </p>
                  )}

                  {task.problem_identifier && (
                    <p>
                      🧩 Problem:{" "}
                      <strong>
                        {task.problem_identifier}
                      </strong>
                    </p>
                  )}

                  {task.problem_url && (
                    <p>
                      🔗{" "}
                      <a
                        href={task.problem_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Open Problem
                      </a>
                    </p>
                  )}

                </div>

                <button
                  onClick={() => {

                    setSelectedTask(task);

                    document
                      .getElementById(
                        "submit-proof"
                      )
                      ?.scrollIntoView({
                        behavior: "smooth",
                      });

                  }}
                >
                  Start Task
                </button>

              </div>

            ))}

        </section>

        <section className="section-card">

          <h2>
            ✅ Solved Problems
          </h2>

          {completedTasks.length === 0 ? (
            <p>No solved problems yet.</p>
          ) : (
            completedTasks.map((task) => (
              <div className="problem" key={`completed-${task.id}`}>
                <h3>{task.title}</h3>
                <p>
                  ✅ Solved
                  {task.problem_identifier
                    ? ` - ${task.problem_identifier}`
                    : ""}
                </p>
                <p>📅 {task.task_date}</p>
              </div>
            ))
          )}

        </section>

        {/* =========================
            Today's Coding Goal
        ========================= */}
        <section className="section-card">

          <h2>
            🎯 Today's Coding Goal
          </h2>

          <p>
            Target: 60 Minutes
          </p>

          <div
            style={{
              width: "100%",
              height: "18px",
              background:
                "rgba(255,255,255,0.15)",
              border:
                "1px solid rgba(255,255,255,0.25)",
              borderRadius: "999px",
              overflow: "hidden",
              margin: "20px 0",
              boxSizing: "border-box",
            }}
          >

            <div
              style={{
                height: "100%",
                width: `${progressPercentage}%`,
                background:
                  "linear-gradient(90deg, #00d4ff, #007bff)",
                borderRadius: "999px",
                transition:
                  "width 0.5s ease",
              }}
            />

          </div>

          <p>
            <strong>
              {Math.floor(
                progressPercentage
              )}%
            </strong>{" "}
            completed
          </p>

          <p>
            {Math.floor(seconds / 60)} / 60
            minutes completed
          </p>

          <h2>
            ⏱️ {formattedTime}
          </h2>

          <label htmlFor="focus-task-select">
            Choose a task to work on
          </label>
          <select
            id="focus-task-select"
            value={selectedTask?.id || ""}
            onChange={(event) => {
              const task = activeTasks.find(
                (item) => String(item.id) === event.target.value
              );
              setSelectedTask(task || null);
              setFocusWarning("");
            }}
            disabled={focusMode}
          >
            <option value="">Select an assigned task</option>
            {activeTasks.map((task) => (
              <option key={task.id} value={task.id}>
                {task.title}
                {task.problem_identifier
                  ? ` - ${task.problem_identifier}`
                  : ""}
              </option>
            ))}
          </select>

          {focusMode && (
            <p className="focus-mode-status">
              🔒 Focus mode active. Stay on CodeTrack while solving.
            </p>
          )}

          {focusWarning && (
            <p className="focus-mode-warning">
              ⚠️ {focusWarning}
            </p>
          )}

          <button
            onClick={startFocusSession}
          >
            Start Focus Session
          </button>

          <button
            onClick={() => setIsRunning(false)}
          >
            Pause
          </button>

          {focusMode && (
            <button onClick={endFocusSession}>
              End Focus Session
            </button>
          )}

          <button
            onClick={() => {
              setSeconds(0);
              setIsRunning(false);
            }}
          >
            Reset
          </button>

        </section>

        {/* =========================
            Submit Proof
        ========================= */}
        <section
          className="section-card"
          id="submit-proof"
        >

          <h2>
            📸 Submit Coding Proof
          </h2>

          {selectedTask && (

            <p>
              📝 Task:{" "}

              <strong>
                {selectedTask.title}
              </strong>
            </p>

          )}

          {!selectedTask && (
            <p>
              Select an active task above to submit proof.
            </p>
          )}

          <label>
            Platform
          </label>

          <select
            value={platform}
            onChange={(e) =>
              setPlatform(e.target.value)
            }
          >

            <option value="LeetCode">
              LeetCode
            </option>

            <option value="CodeChef">
              CodeChef
            </option>

            <option value="HackerRank">
              HackerRank
            </option>

            <option value="Codeforces">
              Codeforces
            </option>

            <option value="AtCoder">
              AtCoder
            </option>

            <option value="Skillrack">
              Skillrack
            </option>

            <option value="Other">
              Other
            </option>

          </select>

          <label>
            {platform === "LeetCode"
              ? "LeetCode submission URL"
              : "Problem URL"}
          </label>

          <input
            type="text"
            placeholder={
              platform === "LeetCode"
                ? "Paste the complete submission URL"
                : "Paste your problem URL"
            }
            value={problemUrl}
            onChange={(e) =>
              setProblemUrl(e.target.value)
            }
          />

          <label>
            Upload Screenshot
          </label>

          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={(e) =>
              setScreenshot(e.target.files?.[0] || null)
            }
          />

          <button
            onClick={handleSubmitProof}
            disabled={
              submitting ||
              !selectedTask
            }
          >
            {submitting
              ? "Submitting..."
              : "Submit Proof"}
          </button>

        </section>

      </main>

    </div>
  );
}

export default StudentDashboard;