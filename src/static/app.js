document.addEventListener("DOMContentLoaded", () => {
  const activitiesList = document.getElementById("activities-list");
  const activitySelect = document.getElementById("activity");
  const signupForm = document.getElementById("signup-form");
  const signupContainer = document.getElementById("signup-container");
  const messageDiv = document.getElementById("message");
  const userMenuButton = document.getElementById("user-menu-button");
  const userMenu = document.getElementById("user-menu");
  const loginOpenButton = document.getElementById("login-open-button");
  const signedInMenu = document.getElementById("signed-in-menu");
  const signedInLabel = document.getElementById("signed-in-label");
  const logoutButton = document.getElementById("logout-button");
  const loginDialog = document.getElementById("login-dialog");
  const loginForm = document.getElementById("login-form");
  const loginError = document.getElementById("login-error");
  const loginCancelButton = document.getElementById("login-cancel-button");
  let isAuthenticated = false;
  let messageTimeout;

  function showMessage(message, type) {
    messageDiv.textContent = message;
    messageDiv.className = `message ${type}`;
    messageDiv.classList.remove("hidden");
    clearTimeout(messageTimeout);
    messageTimeout = setTimeout(() => {
      messageDiv.classList.add("hidden");
    }, 5000);
  }

  function updateAuthentication(authenticated, username) {
    isAuthenticated = authenticated;
    signupContainer.hidden = !authenticated;
    loginOpenButton.classList.toggle("hidden", authenticated);
    signedInMenu.classList.toggle("hidden", !authenticated);
    signedInLabel.textContent = authenticated ? `Signed in as ${username}` : "";
    userMenuButton.setAttribute("aria-label", authenticated ? "Teacher account" : "Teacher log in");
  }

  async function refreshAuthentication() {
    const response = await fetch("/auth/session");
    if (!response.ok) {
      throw new Error("Failed to check teacher session");
    }
    const session = await response.json();
    updateAuthentication(session.authenticated, session.username);
  }

  async function fetchActivities() {
    try {
      const response = await fetch("/activities");
      if (!response.ok) {
        throw new Error(`Activity request failed: ${response.status}`);
      }
      const activities = await response.json();
      activitiesList.replaceChildren();
      activitySelect.replaceChildren(activitySelect.options[0]);
      Object.entries(activities).forEach(([name, details]) => {
        const activityCard = document.createElement("div");
        activityCard.className = "activity-card";
        const spotsLeft =
          details.max_participants - details.participants.length;
        const title = document.createElement("h4");
        title.textContent = name;
        const description = document.createElement("p");
        description.textContent = details.description;
        const schedule = document.createElement("p");
        const scheduleLabel = document.createElement("strong");
        scheduleLabel.textContent = "Schedule:";
        schedule.append(scheduleLabel, ` ${details.schedule}`);
        const availability = document.createElement("p");
        availability.textContent = `Availability: ${spotsLeft} spots left`;
        const participantsContainer = document.createElement("div");
        participantsContainer.className = "participants-container";

        if (details.participants.length > 0) {
          const participantsSection = document.createElement("div");
          participantsSection.className = "participants-section";
          const participantsTitle = document.createElement("h5");
          participantsTitle.textContent = "Participants:";
          const participantsList = document.createElement("ul");
          participantsList.className = "participants-list";

          details.participants.forEach((email) => {
            const participant = document.createElement("li");
            const participantEmail = document.createElement("span");
            participantEmail.className = "participant-email";
            participantEmail.textContent = email;
            participant.appendChild(participantEmail);
            if (isAuthenticated) {
              const unregisterButton = document.createElement("button");
              unregisterButton.className = "delete-btn";
              unregisterButton.type = "button";
              unregisterButton.dataset.activity = name;
              unregisterButton.dataset.email = email;
              unregisterButton.setAttribute("aria-label", `Unregister ${email}`);
              unregisterButton.textContent = "Remove";
              participant.appendChild(unregisterButton);
            }
            participantsList.appendChild(participant);
          });

          participantsSection.append(participantsTitle, participantsList);
          participantsContainer.appendChild(participantsSection);
        } else {
          const emptyParticipants = document.createElement("p");
          const emptyText = document.createElement("em");
          emptyText.textContent = "No participants yet";
          emptyParticipants.appendChild(emptyText);
          participantsContainer.appendChild(emptyParticipants);
        }

        activityCard.append(
          title,
          description,
          schedule,
          availability,
          participantsContainer
        );
        activitiesList.appendChild(activityCard);

        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        activitySelect.appendChild(option);
      });
    } catch (error) {
      activitiesList.replaceChildren();
      const failureMessage = document.createElement("p");
      failureMessage.textContent =
        "Failed to load activities. Please try again later.";
      activitiesList.appendChild(failureMessage);
      console.error("Error fetching activities:", error);
    }
  }

  async function handleUnregister(button) {
    const activity = button.dataset.activity;
    const email = button.dataset.email;
    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(
          activity
        )}/unregister?email=${encodeURIComponent(email)}`,
        {
          method: "DELETE",
        }
      );
      const result = await response.json();
      if (response.ok) {
        showMessage(result.message, "success");
        await fetchActivities();
      } else {
        if (response.status === 401) {
          updateAuthentication(false);
          await fetchActivities();
        }
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      showMessage("Failed to unregister. Please try again.", "error");
      console.error("Error unregistering:", error);
    }
  }

  activitiesList.addEventListener("click", (event) => {
    const button = event.target.closest(".delete-btn");
    if (button && isAuthenticated) {
      handleUnregister(button);
    }
  });

  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = document.getElementById("email").value;
    const activity = document.getElementById("activity").value;
    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(
          activity
        )}/signup?email=${encodeURIComponent(email)}`,
        {
          method: "POST",
        }
      );
      const result = await response.json();
      if (response.ok) {
        showMessage(result.message, "success");
        signupForm.reset();
        await fetchActivities();
      } else {
        if (response.status === 401) {
          updateAuthentication(false);
          await fetchActivities();
        }
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      showMessage("Failed to sign up. Please try again.", "error");
      console.error("Error signing up:", error);
    }
  });

  userMenuButton.addEventListener("click", () => {
    const isExpanded = userMenuButton.getAttribute("aria-expanded") === "true";
    userMenuButton.setAttribute("aria-expanded", String(!isExpanded));
    userMenu.classList.toggle("hidden", isExpanded);
  });

  loginOpenButton.addEventListener("click", () => {
    userMenu.classList.add("hidden");
    userMenuButton.setAttribute("aria-expanded", "false");
    loginError.classList.add("hidden");
    loginForm.reset();
    loginDialog.showModal();
    document.getElementById("username").focus();
  });

  loginCancelButton.addEventListener("click", () => loginDialog.close());

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    loginError.classList.add("hidden");
    const formData = new FormData(loginForm);
    try {
      const response = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: formData.get("username"),
          password: formData.get("password"),
        }),
      });
      const result = await response.json();
      if (!response.ok) {
        loginError.textContent = result.detail || "Unable to log in.";
        loginError.classList.remove("hidden");
        return;
      }
      updateAuthentication(true, result.username);
      loginDialog.close();
      showMessage("Teacher signed in.", "success");
      await fetchActivities();
    } catch (error) {
      loginError.textContent = "Unable to log in. Please try again.";
      loginError.classList.remove("hidden");
      console.error("Error signing in:", error);
    }
  });

  logoutButton.addEventListener("click", async () => {
    try {
      const response = await fetch("/auth/logout", { method: "POST" });
      if (!response.ok) {
        throw new Error(`Logout request failed: ${response.status}`);
      }
      updateAuthentication(false);
      userMenu.classList.add("hidden");
      userMenuButton.setAttribute("aria-expanded", "false");
      showMessage("Teacher signed out.", "success");
      await fetchActivities();
    } catch (error) {
      showMessage("Unable to log out. Please try again.", "error");
      console.error("Error signing out:", error);
    }
  });

  async function initialize() {
    try {
      await refreshAuthentication();
    } catch (error) {
      console.error("Error checking teacher session:", error);
    }
    await fetchActivities();
  }

  initialize();
});
