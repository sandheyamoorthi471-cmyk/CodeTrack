import { useState } from "react";

function Login() {
  const [isRegistering, setIsRegistering] = useState(false);

  // Login
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // Registration
  const [name, setName] = useState("");
  const [registerEmail, setRegisterEmail] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");
  const [role, setRole] = useState("student");

  // Student academic details
  const [department, setDepartment] = useState("");
  const [year, setYear] = useState("");
  const [section, setSection] = useState("");
  const [registerNumber, setRegisterNumber] = useState("");
  const [rollNumber, setRollNumber] = useState("");

  const [loading, setLoading] = useState(false);

  // ---------------- LOGIN ----------------

  const handleLogin = async (e) => {
    e.preventDefault();

    if (!email.trim() || !password.trim()) {
      alert("Please enter email and password.");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(
        "https://codetrack-backend-9no3.onrender.com/api/login",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            email: email.trim(),
            password: password,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.error || "Login failed"
        );
      }

      localStorage.setItem(
        "codetrackUser",
        JSON.stringify(data.user)
      );

      alert(
        `Login successful! Welcome ${data.user.name} 👋`
      );

      window.location.reload();

    } catch (error) {
      console.error("Login error:", error);

      alert(
        "Login failed: " + error.message
      );
    } finally {
      setLoading(false);
    }
  };

  // ---------------- REGISTER ----------------

  const handleRegister = async (e) => {
    e.preventDefault();

    if (
      !name.trim() ||
      !registerEmail.trim() ||
      !registerPassword.trim()
    ) {
      alert("Please fill all required fields.");
      return;
    }

    if (registerPassword.length < 6) {
      alert(
        "Password must be at least 6 characters."
      );
      return;
    }

    if (role === "student") {
      if (
        !department ||
        !year ||
        !section.trim() ||
        !registerNumber.trim()
      ) {
        alert(
          "Please fill all student academic details."
        );
        return;
      }
    }

    setLoading(true);

    try {
      const response = await fetch(
        "https://codetrack-backend-9no3.onrender.com/api/register",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            name: name.trim(),
            email: registerEmail.trim(),
            password: registerPassword,
            role: role,

            department:
              role === "student"
                ? department
                : null,

            year:
              role === "student"
                ? Number(year)
                : null,

            section:
              role === "student"
                ? section.trim()
                : null,

            register_number:
              role === "student"
                ? registerNumber.trim()
                : null,

            roll_number:
              role === "student"
                ? rollNumber.trim()
                : null,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.error || "Registration failed"
        );
      }

      alert(
        "Account created successfully! 🎉 Please login."
      );

      // Clear fields
      setName("");
      setRegisterEmail("");
      setRegisterPassword("");
      setRole("student");

      setDepartment("");
      setYear("");
      setSection("");
      setRegisterNumber("");
      setRollNumber("");

      setIsRegistering(false);

    } catch (error) {
      console.error(
        "Registration error:",
        error
      );

      alert(
        "Registration failed: " +
          error.message
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dashboard">

      <main className="dashboard-content">

        <section className="section-card">

          <h1>CodeTrack</h1>

          {!isRegistering ? (
            <>
              {/* LOGIN */}

              <h2>🔐 Login</h2>

              <form onSubmit={handleLogin}>

                <label>Email</label>

                <input
                  type="email"
                  placeholder="Enter your email"
                  value={email}
                  onChange={(e) =>
                    setEmail(e.target.value)
                  }
                />

                <label>Password</label>

                <input
                  type="password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) =>
                    setPassword(e.target.value)
                  }
                />

                <button
                  type="submit"
                  disabled={loading}
                >
                  {loading
                    ? "Logging in..."
                    : "Login"}
                </button>

              </form>

              <p>
                Don't have an account?
              </p>

              <button
                type="button"
                onClick={() =>
                  setIsRegistering(true)
                }
              >
                Create Account 📝
              </button>
            </>
          ) : (
            <>
              {/* CREATE ACCOUNT */}

              <h2>📝 Create Account</h2>

              <form onSubmit={handleRegister}>

                <label>Name</label>

                <input
                  type="text"
                  placeholder="Enter your name"
                  value={name}
                  onChange={(e) =>
                    setName(e.target.value)
                  }
                />

                <label>Email</label>

                <input
                  type="email"
                  placeholder="Enter your email"
                  value={registerEmail}
                  onChange={(e) =>
                    setRegisterEmail(
                      e.target.value
                    )
                  }
                />

                <label>Password</label>

                <input
                  type="password"
                  placeholder="Create a password"
                  value={registerPassword}
                  onChange={(e) =>
                    setRegisterPassword(
                      e.target.value
                    )
                  }
                />

                <label>Account Type</label>

                <select
                  value={role}
                  onChange={(e) =>
                    setRole(e.target.value)
                  }
                >
                  <option value="student">
                    Student
                  </option>

                  <option value="mentor">
                    Mentor
                  </option>
                </select>

                {/* STUDENT DETAILS */}

                {role === "student" && (
                  <>
                    <h3>
                      🎓 Academic Details
                    </h3>

                    <label>
                      Department
                    </label>

                    <select
                      value={department}
                      onChange={(e) =>
                        setDepartment(
                          e.target.value
                        )
                      }
                    >
                      <option value="">
                        Select Department
                      </option>

                      <option value="CSE 🖥️">
                        CSE
                      </option>

                      <option value="ECE 📡">
                        ECE
                      </option>

                      <option value="EEE ⚡">
                        EEE
                      </option>

                      <option value="MECH 🛠️">
                        Mechanical
                      </option>

                      <option value="CIVIL 🏗️">
                        Civil
                      </option>

                      <option value="IT 🖥️">
                        Information Technology
                      </option>

                      <option value="CHEM 🧪">
                        Chemical
                      </option>

                      <option value="BIO ⚕️">
                        Biotechnology
                      </option>

                      <option value="Artificial Intelligence and Data Science 🤖">
                        Artificial Intelligence and Data Science
                      </option>

                      <option value="AIML 📊">
                        AIML
                      </option>

                      <option value="Mechatronics 🔩">
                        Mechatronics
                      </option>

                    </select>

                    <label>
                      Year
                    </label>

                    <select
                      value={year}
                      onChange={(e) =>
                        setYear(e.target.value)
                      }
                    >
                      <option value="">
                        Select Year
                      </option>

                      <option value="1">
                        1st Year
                      </option>

                      <option value="2">
                        2nd Year
                      </option>

                      <option value="3">
                        3rd Year
                      </option>

                      <option value="4">
                        4th Year
                      </option>
                    </select>

                    <label>
                      Section
                    </label>

                    <input
                      type="text"
                      placeholder="Example: A"
                      value={section}
                      onChange={(e) =>
                        setSection(
                          e.target.value
                        )
                      }
                    />

                    <label>
                      Register Number
                    </label>

                    <input
                      type="text"
                      placeholder="Enter register number"
                      value={registerNumber}
                      onChange={(e) =>
                        setRegisterNumber(
                          e.target.value
                        )
                      }
                    />

                    <label>
                      Roll Number
                    </label>

                    <input
                      type="text"
                      placeholder="Enter roll number (optional)"
                      value={rollNumber}
                      onChange={(e) =>
                        setRollNumber(
                          e.target.value
                        )
                      }
                    />
                  </>
                )}
                {role === "mentor" && (
                  <>
                    <h3>
                      🏢 Mentor Details
                    </h3>
                    <label>department</label>
                    <select
                      value={department}
                      onChange={(e) =>
                        setDepartment(
                          e.target.value
                        )
                      }
                    >
                      <option value="">
                        Select Department
                      </option>

                      <option value="CSE 🖥️">
                        CSE
                      </option>

                      <option value="ECE 📡">
                        ECE
                      </option>

                      <option value="EEE ⚡">
                        EEE
                      </option>

                      <option value="MECH 🛠️">
                        Mechanical
                      </option>

                      <option value="CIVIL 🏗️">
                        Civil
                      </option>

                      <option value="IT 🖥️">
                        Information Technology
                      </option>

                      <option value="CHEM 🧪">
                        Chemical
                      </option>

                      <option value="BIO ⚕️">
                        Biotechnology
                      </option>

                      <option value="Artificial Intelligence and Data Science 🤖">
                        Artificial Intelligence and Data Science
                      </option>

                      <option value="AIML 📊">
                        AIML
                      </option>

                      <option value="Mechatronics 🔩">
                        Mechatronics
                      </option>

                    </select>

                  </>
                )}

                <button
                  type="submit"
                  disabled={loading}
                >
                  {loading
                    ? "Creating Account..."
                    : "Create Account 🚀"}
                </button>

              </form>

              <p>
                Already have an account?
              </p>

              <button
                type="button"
                onClick={() =>
                  setIsRegistering(false)
                }
              >
                Back to Login 🔐
              </button>
            </>
          )}

        </section>

      </main>

    </div>
  );
}

export default Login;