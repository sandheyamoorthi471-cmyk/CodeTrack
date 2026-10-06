export const fetchStudentPlatformAccounts = async ({
  studentId,
  setPlatformAccounts,
  setPlatformUrls,
}) => {
  if (!studentId) return;

  try {
    const response = await fetch(
      `https://codetrack-backend-9no3.onrender.com/api/student/platforms/${studentId}`
    );

    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(
        data.error ||
          "Failed to load platform accounts"
      );
    }

    const accounts = data.platforms || [];

    setPlatformAccounts(accounts);

    const urls = {
      Codeforces: "",
      LeetCode: "",
    };

    accounts.forEach((account) => {
      if (
        Object.prototype.hasOwnProperty.call(
          urls,
          account.platform
        )
      ) {
        urls[account.platform] =
          account.profile_url || "";
      }
    });

    setPlatformUrls(urls);
  } catch (error) {
    console.error(
      "Platform account loading error:",
      error
    );
  }
};