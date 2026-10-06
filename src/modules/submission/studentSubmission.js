export const submitStudentProof = async ({
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
}) => {
  if (!selectedTask) {
    alert("Please select an active task first.");
    return;
  }

  if (selectedTask.task_status === "completed") {
    alert(
      "This task is already completed and verified. ✅"
    );
    return;
  }

  if (!problemUrl.trim()) {
    alert("Please enter the problem URL.");
    return;
  }

  setSubmitting(true);

  try {
    const formData = new FormData();

    formData.append("task_id", selectedTask.id);
    formData.append("student_id", studentId);
    formData.append(
      "answer",
      `${platform}: ${problemUrl}`
    );

    if (screenshot) {
      formData.append("screenshot", screenshot);
    }

    const response = await fetch(
      "https://codetrack-backend-9no3.onrender.com/api/submissions",
      {
        method: "POST",
        body: formData,
      }
    );

    const data = await response.json();

    console.log("Submission response:", data);

    if (!response.ok || !data.success) {
      alert(
        "Failed to submit proof: " +
          (data.error ||
            data.message ||
            "Unknown error")
      );
      return;
    }

    if (data.verified === true) {
      alert(
        "✅ Proof submitted and LeetCode verified successfully!\n\n" +
          "🎉 Submission Approved!"
      );
    } else {
      alert(
        "📤 Proof submitted successfully!\n\n" +
          "🟡 Verification pending.\n\n" +
          (data.message ||
            "No accepted submission found yet.")
      );
    }

    setProblemUrl("");
    setScreenshot(null);
    setSelectedTask(null);

    await fetchTasks();
    await fetchPoints();

  } catch (error) {
    console.error("Submission error:", error);

    alert(
      "Failed to submit proof: " +
        error.message
    );

  } finally {
    setSubmitting(false);
  }
};