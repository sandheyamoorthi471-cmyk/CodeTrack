export const askStudentAI = async ({
  aiMessage,
  studentId,
  setAiResponse,
  setAiLoading,
}) => {
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
          message,
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