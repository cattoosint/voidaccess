import { render, screen } from "@testing-library/react";
import React from "react";
import { InvestigationCard, InvestigationListItem } from "@/components/InvestigationCard";

const createMockInvestigation = (overrides: Partial<InvestigationListItem> = {}): InvestigationListItem => ({
  id: 1,
  query: "REvil ransomware dark web",
  refined_query: null,
  status: "completed",
  created_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
  completed_at: null,
  entity_count: 23,
  page_count: 3,
  graph_status: null,
  model_used: "claude-sonnet-4-5",
  ...overrides,
});

describe("InvestigationCard", () => {
  describe("renders query, status badge, relative time", () => {
    it("renders investigation query", () => {
      const investigation = createMockInvestigation({ query: "LockBit ransomware analysis" });
      render(<InvestigationCard investigation={investigation} onClick={jest.fn()} />);
      expect(screen.getByTestId("investigation-query")).toHaveTextContent("LockBit ransomware analysis");
    });

    it("renders status badge", () => {
      const investigation = createMockInvestigation({ status: "completed" });
      render(<InvestigationCard investigation={investigation} onClick={jest.fn()} />);
      expect(screen.getByText("Complete")).toBeInTheDocument();
    });

    it("renders relative time", () => {
      const investigation = createMockInvestigation();
      render(<InvestigationCard investigation={investigation} onClick={jest.fn()} />);
      expect(screen.getByTestId("investigation-time")).toBeInTheDocument();
    });
  });

  describe("refined_query display", () => {
    it("shows refined_query when it differs from query", () => {
      const investigation = createMockInvestigation({
        query: "ransomware",
        refined_query: "lockbit ransomware",
      });
      render(<InvestigationCard investigation={investigation} onClick={jest.fn()} />);
      expect(screen.getByTestId("refined-query-row")).toBeInTheDocument();
      expect(screen.getByText(/Refined to:/)).toBeInTheDocument();
      expect(screen.getByText("lockbit ransomware")).toBeInTheDocument();
    });

    it("does not show refined_query when it equals query", () => {
      const investigation = createMockInvestigation({
        query: "lockbit",
        refined_query: "lockbit",
      });
      render(<InvestigationCard investigation={investigation} onClick={jest.fn()} />);
      expect(screen.queryByTestId("refined-query-row")).not.toBeInTheDocument();
    });

    it("does not show refined_query when refined_query is null", () => {
      const investigation = createMockInvestigation({ refined_query: null });
      render(<InvestigationCard investigation={investigation} onClick={jest.fn()} />);
      expect(screen.queryByTestId("refined-query-row")).not.toBeInTheDocument();
    });
  });

  describe("graph overflow pill", () => {
    it("renders overflow pill when graph_status is skipped_overflow", () => {
      const investigation = createMockInvestigation({ graph_status: "skipped_overflow" });
      render(<InvestigationCard investigation={investigation} onClick={jest.fn()} />);
      expect(screen.getByTestId("graph-overflow-pill")).toBeInTheDocument();
      expect(screen.getByText("Graph overflow")).toBeInTheDocument();
    });

    it("does not render overflow pill when graph_status is built", () => {
      const investigation = createMockInvestigation({ graph_status: "built" });
      render(<InvestigationCard investigation={investigation} onClick={jest.fn()} />);
      expect(screen.queryByTestId("graph-overflow-pill")).not.toBeInTheDocument();
    });
  });

  describe("entity/page counts", () => {
    it("shows counts when entity_count and page_count are greater than 0", () => {
      const investigation = createMockInvestigation({ entity_count: 23, page_count: 3 });
      render(<InvestigationCard investigation={investigation} onClick={jest.fn()} />);
      expect(screen.getByTestId("investigation-counts")).toHaveTextContent("23 entities · 3 pages");
    });

    it("hides counts when both entity_count and page_count are 0", () => {
      const investigation = createMockInvestigation({ entity_count: 0, page_count: 0 });
      render(<InvestigationCard investigation={investigation} onClick={jest.fn()} />);
      expect(screen.queryByTestId("investigation-counts")).not.toBeInTheDocument();
    });
  });

  describe("onClick handler", () => {
    it("calls onClick when card is clicked", () => {
      const onClick = jest.fn();
      const investigation = createMockInvestigation();
      render(<InvestigationCard investigation={investigation} onClick={onClick} />);
      screen.getByTestId("investigation-card").click();
      expect(onClick).toHaveBeenCalledTimes(1);
    });
  });
});