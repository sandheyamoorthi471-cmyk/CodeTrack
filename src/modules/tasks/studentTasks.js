export const fetchStudentTasks = async (
  studentId,
  setTasks,
  setSelectedTask,
  setLoadingTasks
) => {
  if (!studentId) {
    setLoadingTasks(false);
    return;
  }

  try {
    const response = await fetch(
      `https://codetrack-backend-9no3.onrender.com/api/student/tasks/${studentId}`
    );

    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(
        data.error || "Failed to load tasks"
      );
    }

    const loadedTasks = data.tasks || [];

    setTasks(loadedTasks);

    const firstActiveTask = loadedTasks.find(
      (task) =>
        task.task_status !== "completed"
    );

    if (firstActiveTask) {
      setSelectedTask(firstActiveTask);
    } else {
      setSelectedTask(null);
    }
  } catch (error) {
    console.error(
      "Task loading error:",
      error
    );
  } finally {
    setLoadingTasks(false);
  }
};