export const fetchStudentPoints = async ({
  studentId,
  setTotalPoints,
  setVerifiedTasks,
  setLoadingPoints,
}) => {
  if (!studentId) {
    setLoadingPoints(false);
    return;
  }

  try {
    const response = await fetch(
      `http://127.0.0.1:5000/api/student/points/${studentId}`
    );

    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(
        data.error || "Failed to load points"
      );
    }

    setTotalPoints(data.total_points || 0);
    setVerifiedTasks(data.verified_tasks || 0);

  } catch (error) {
    console.error(
      "Points loading error:",
      error
    );
  } finally {
    setLoadingPoints(false);
  }
};