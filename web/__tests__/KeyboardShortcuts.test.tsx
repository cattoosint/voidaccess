import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { useRouter } from "next/navigation";
import { useKeyboardShortcuts, ALL_SHORTCUTS } from "@/hooks/useKeyboardShortcuts";

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

function TestComponent({ onHelp, onClose }: {
  onHelp?: () => void;
  onClose?: () => void;
}) {
  useKeyboardShortcuts({ onHelp, onClose });
  return <div data-testid="test-comp">test</div>;
}

describe("useKeyboardShortcuts", () => {
  describe("test_shortcut_n_navigates", () => {
    it("pressing N navigates to /investigations/new", () => {
      const router = require("next/navigation").useRouter();
      render(<TestComponent />);
      fireEvent.keyDown(document, { key: "N" });
      expect(router.push).toHaveBeenCalledWith("/investigations/new");
    });

    it("pressing lowercase n also navigates", () => {
      const router = require("next/navigation").useRouter();
      render(<TestComponent />);
      fireEvent.keyDown(document, { key: "n" });
      expect(router.push).toHaveBeenCalledWith("/investigations/new");
    });
  });

  describe("test_shortcut_m_navigates", () => {
    it("pressing M navigates to /monitors", () => {
      const router = require("next/navigation").useRouter();
      render(<TestComponent />);
      fireEvent.keyDown(document, { key: "M" });
      expect(router.push).toHaveBeenCalledWith("/monitors");
    });
  });

  describe("test_shortcut_h_opens_help", () => {
    it("pressing H calls onHelp", () => {
      const onHelp = jest.fn();
      render(<TestComponent onHelp={onHelp} />);
      fireEvent.keyDown(document, { key: "H" });
      expect(onHelp).toHaveBeenCalledTimes(1);
    });

    it("pressing ? calls onHelp", () => {
      const onHelp = jest.fn();
      render(<TestComponent onHelp={onHelp} />);
      fireEvent.keyDown(document, { key: "?" });
      expect(onHelp).toHaveBeenCalledTimes(1);
    });
  });

  describe("test_shortcut_escape_calls_onClose", () => {
    it("pressing Escape calls onClose", () => {
      const onClose = jest.fn();
      render(<TestComponent onClose={onClose} />);
      fireEvent.keyDown(document, { key: "Escape" });
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  describe("test_shortcut_ignored_in_input", () => {
    it("pressing N while focused on input does not navigate", () => {
      const router = require("next/navigation").useRouter();
      render(
        <div>
          <input type="text" data-testid="input" />
          <TestComponent />
        </div>
      );
      const input = screen.getByTestId("input");
      input.focus();
      fireEvent.keyDown(input, { key: "N" });
      expect(router.push).not.toHaveBeenCalled();
    });

    it("pressing / while focused on textarea does not focus search", () => {
      render(
        <div>
          <textarea data-testid="textarea" />
          <TestComponent />
        </div>
      );
      const textarea = screen.getByTestId("textarea");
      textarea.focus();
      const result = fireEvent.keyDown(textarea, { key: "/" });
      expect(result).toBe(false);
    });
  });
});