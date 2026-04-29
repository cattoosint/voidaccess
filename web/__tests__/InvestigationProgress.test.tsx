import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { InvestigationProgress } from "@/components/InvestigationProgress";

jest.mock("@/lib/backend", () => ({
  getAuthHeaders: jest.fn(() => ({})),
}));

jest.spyOn(window, "EventSource").mockImplementation(
  (url: string) => {
    const listeners: Record<string, (event: MessageEvent) => void> = {};
    (window as Record<string, unknown>).__mockEs = {
      url,
      addEventListener: (event: string, handler: (event: MessageEvent) => void) => {
        listeners[event] = handler;
      },
      close: jest.fn(),
      _trigger: (data: Record<string, unknown>) => {
        const handler = listeners["message"];
        if (handler) {
          handler(new MessageEvent("message", { data: JSON.stringify(data) }));
        }
      },
    };
    return (window as Record<string, unknown>).__mockEs;
  }
);

describe("InvestigationProgress", () => {
  describe("test_progress_component_renders", () => {
    it("renders progress bar at 0% initially", () => {
      render(<InvestigationProgress investigationId="test-id" />);
      const bar = screen.getByText("0%");
      expect(bar).toBeInTheDocument();
    });

    it("shows initial step label", () => {
      render(<InvestigationProgress investigationId="test-id" />);
      expect(screen.getByText("Initializing...")).toBeInTheDocument();
    });
  });

  describe("test_progress_updates_on_sse", () => {
    it("updates progress bar when SSE message arrives", () => {
      render(<InvestigationProgress investigationId="test-id" />);
      const es = (window as Record<string, unknown>).__mockEs;
      es._trigger({ step: 5, step_label: "Extracting entities", progress: 38, status: "processing", entity_count: 10, page_count: 3 });
      expect(screen.getByText("38%")).toBeInTheDocument();
      expect(screen.getByText("Extracting entities")).toBeInTheDocument();
      expect(screen.getByText("10 entities found · 3 pages scraped")).toBeInTheDocument();
    });

    it("calls onComplete when done=true is received", () => {
      const onComplete = jest.fn();
      render(<InvestigationProgress investigationId="test-id" onComplete={onComplete} />);
      const es = (window as Record<string, unknown>).__mockEs;
      es._trigger({ step: 9, step_label: "Finalizing results", progress: 100, status: "completed", entity_count: 25, page_count: 8, done: true });
      expect(onComplete).toHaveBeenCalledTimes(1);
    });
  });

  describe("test_progress_cleanup", () => {
    it("asserts EventSource.close() called on unmount", () => {
      const close = jest.fn();
      (jest.spyOn(window, "EventSource") as unknown as jest.SpyInstance).mockImplementation(() => ({
        url: "",
        close: close,
        addEventListener: jest.fn(),
      }));
      const { unmount } = render(<InvestigationProgress investigationId="test-id" />);
      unmount();
      expect(close).toHaveBeenCalled();
    });
  });
});