import "./App.css";

import Login from "./pages/login";
import StudentDashboard from "./pages/studentdashboard";
import MentorDashboard from "./pages/mentordashboard";

function App() {
  const savedUser = localStorage.getItem(
    "codetrackUser"
  );

  // Not logged in
  if (!savedUser) {
    return <Login />;
  }

  const user = JSON.parse(savedUser);

  // Mentor
  if (user.role === "mentor") {
    return <MentorDashboard />;
  }

  // Student
  if (user.role === "student") {
    return <StudentDashboard />;
  }

  // Unknown role
  localStorage.removeItem("codetrackUser");

  return <Login />;
}

export default App;