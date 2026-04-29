import { formatRelativeTime } from "@/lib/utils/formatRelativeTime";

describe("formatRelativeTime", () => {
  const now = new Date();

  const minutesAgo = (mins: number) => new Date(now.getTime() - mins * 60 * 1000).toISOString();
  const hoursAgo = (hrs: number) => new Date(now.getTime() - hrs * 60 * 60 * 1000).toISOString();
  const daysAgo = (days: number) => new Date(now.getTime() - days * 24 * 60 * 60 * 1000).toISOString();

  it("returns 'just now' for dates less than 1 minute ago", () => {
    const thirtySecondsAgo = new Date(now.getTime() - 30 * 1000).toISOString();
    expect(formatRelativeTime(thirtySecondsAgo)).toBe("just now");
  });

  it("returns '45m ago' for 45 minutes ago", () => {
    expect(formatRelativeTime(minutesAgo(45))).toBe("45m ago");
  });

  it("returns '3h ago' for 3 hours ago", () => {
    expect(formatRelativeTime(hoursAgo(3))).toBe("3h ago");
  });

  it("returns '2d ago' for 2 days ago", () => {
    expect(formatRelativeTime(daysAgo(2))).toBe("2d ago");
  });

  it("returns '1w ago' for 10 days ago (1w)", () => {
    expect(formatRelativeTime(daysAgo(10))).toBe("1w ago");
  });

  it("returns '1mo ago' for 45 days ago", () => {
    expect(formatRelativeTime(daysAgo(45))).toBe("1mo ago");
  });

  it("returns months for older dates", () => {
    expect(formatRelativeTime(daysAgo(90))).toBe("3mo ago");
  });
});