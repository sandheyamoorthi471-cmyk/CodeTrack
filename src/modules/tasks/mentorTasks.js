export const postMentorTask = async ({
  taskTitle,
  description,
  platform,
  taskUrl,
  problemIdentifier,
  deadline,
  selectedGroup,
  setTaskTitle,
  setDescription,
  setPlatform,
  setTaskUrl,
  setProblemIdentifier,
  setDeadline,
  fetchStudentProgress,
}) => {
  if (
    !taskTitle.trim() ||
    !description.trim() ||
    !platform ||
    !taskUrl.trim() ||
    !deadline
  ) {
    alert("Please fill all required task fields.");
    return;
  }

  if (!selectedGroup) {
    alert("Please select a student group.");
    return;
  }

  try {
    const response = await fetch(
      "http://127.0.0.1:5000/api/tasks",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          group_id: Number(selectedGroup),
          title: taskTitle.trim(),
          description: description.trim(),
          task_date: deadline.split("T")[0],
          platform,
          problem_url: taskUrl.trim(),
          problem_identifier: problemIdentifier.trim(),
        }),
      }
    );

    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(
        data.error || "Failed to create task"
      );
    }

    alert("Task posted successfully! 🎉");

    setTaskTitle("");
    setDescription("");
    setPlatform("");
    setTaskUrl("");
    setProblemIdentifier("");
    setDeadline("");

    await fetchStudentProgress();

  } catch (error) {
    console.error(error);

    alert(
      "Failed to post task: " +
        error.message
    );
  }
};