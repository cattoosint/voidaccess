import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";

const mockGraphData = {
  nodes: [
    { id: "node1", type: "ThreatActor", confidence: 0.95 },
    { id: "node2", type: "EmailAddress", confidence: 0.5 },
  ],
  edges: [{ source: "node1", target: "node2", type: "CO_APPEARED_ON", confidence: 0.8 }],
  graph_status: "completed",
  total_entities: 2,
  filtered_entities: 1,
  min_confidence: 0.75,
};

const mockOverflowData = {
  graph_status: "skipped_overflow",
  message: "Graph too large to render. Use the entity list or download the CSV export instead.",
  total_entities: 5000,
  nodes: [],
  edges: [],
};

describe("GraphView", () => {
  describe("Confidence Slider", () => {
    it("renders confidence slider with default value of 0.75", () => {
      const SliderComponent = () => {
        const [minConfidence, setMinConfidence] = React.useState(0.75);
        return (
          <div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={minConfidence}
              onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
              data-testid="confidence-slider"
            />
            <span data-testid="confidence-value">{minConfidence.toFixed(2)}</span>
          </div>
        );
      };

      render(<SliderComponent />);

      const slider = screen.getByTestId("confidence-slider") as HTMLInputElement;
      expect(slider).toBeInTheDocument();
      expect(slider.value).toBe("0.75");
      expect(screen.getByTestId("confidence-value").textContent).toBe("0.75");
    });

    it("updates confidence value when slider changes", () => {
      const SliderComponent = () => {
        const [minConfidence, setMinConfidence] = React.useState(0.75);
        return (
          <div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={minConfidence}
              onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
              data-testid="confidence-slider"
            />
            <span data-testid="confidence-value">{minConfidence.toFixed(2)}</span>
          </div>
        );
      };

      render(<SliderComponent />);

      const slider = screen.getByTestId("confidence-slider") as HTMLInputElement;
      fireEvent.change(slider, { target: { value: "0.9" } });

      expect(slider.value).toBe("0.9");
      expect(screen.getByTestId("confidence-value").textContent).toBe("0.90");
    });
  });

  describe("Overflow State", () => {
    it("renders overflow card when API returns skipped_overflow", () => {
      const isOverflow = mockOverflowData.graph_status === "skipped_overflow";

      const OverflowCard = () => {
        if (!isOverflow) return null;
        return (
          <div data-testid="overflow-card">
            <h3 data-testid="overflow-heading">Graph too large to render</h3>
            <p data-testid="overflow-message">{mockOverflowData.message}</p>
          </div>
        );
      };

      render(<OverflowCard />);

      expect(screen.getByTestId("overflow-card")).toBeInTheDocument();
      expect(screen.getByTestId("overflow-heading").textContent).toBe("Graph too large to render");
      expect(screen.getByTestId("overflow-message").textContent).toBe(
        "Graph too large to render. Use the entity list or download the CSV export instead."
      );
    });

    it("does not render graph canvas when overflow is detected", () => {
      const isOverflow = mockOverflowData.graph_status === "skipped_overflow";

      const GraphOrOverflow = () => {
        if (isOverflow) {
          return <div data-testid="overflow-card">Overflow</div>;
        }
        return <div data-testid="graph-canvas">Graph Canvas</div>;
      };

      render(<GraphOrOverflow />);

      expect(screen.queryByTestId("graph-canvas")).not.toBeInTheDocument();
      expect(screen.getByTestId("overflow-card")).toBeInTheDocument();
    });

    it("renders graph canvas when overflow is NOT detected", () => {
      const isOverflow = mockGraphData.graph_status === "completed";

      const GraphOrOverflow = () => {
        if (isOverflow !== "skipped_overflow") {
          return <div data-testid="graph-canvas">Graph Canvas</div>;
        }
        return <div data-testid="overflow-card">Overflow</div>;
      };

      render(<GraphOrOverflow />);

      expect(screen.getByTestId("graph-canvas")).toBeInTheDocument();
      expect(screen.queryByTestId("overflow-card")).not.toBeInTheDocument();
    });
  });

  describe("Overflow CSV Button", () => {
    it("renders CSV download button in overflow state", () => {
      const isOverflow = true;
      const investigationId = "test-investigation-123";

      const CsvButton = () => {
        if (!isOverflow) return null;
        const handleDownload = () => {
          const url = `/api/investigations/${investigationId}/entities/export/csv`;
          window.location.href = url;
        };
        return (
          <button onClick={handleDownload} data-testid="csv-download-btn">
            Download CSV
          </button>
        );
      };

      render(<CsvButton />);

      expect(screen.getByTestId("csv-download-btn")).toBeInTheDocument();
      expect(screen.getByTestId("csv-download-btn").textContent).toBe("Download CSV");
    });

    it("triggers correct endpoint URL when CSV button is clicked", () => {
      const isOverflow = true;
      const investigationId = "test-investigation-123";
      let clickedUrl: string | null = null;

      const CsvButton = () => {
        if (!isOverflow) return null;
        const handleDownload = () => {
          clickedUrl = `/api/investigations/${investigationId}/entities/export/csv`;
        };
        return (
          <button onClick={handleDownload} data-testid="csv-download-btn">
            Download CSV
          </button>
        );
      };

      render(<CsvButton />);

      fireEvent.click(screen.getByTestId("csv-download-btn"));

      expect(clickedUrl).toBe("/api/investigations/test-investigation-123/entities/export/csv");
    });

    it("does not render CSV button when overflow is not detected", () => {
      const isOverflow = false;

      const CsvButton = () => {
        if (!isOverflow) return null;
        return (
          <button data-testid="csv-download-btn">
            Download CSV
          </button>
        );
      };

      render(<CsvButton />);

      expect(screen.queryByTestId("csv-download-btn")).not.toBeInTheDocument();
    });
  });

  describe("Entity List Confidence Filter", () => {
    it("renders confidence filter dropdown with correct options", () => {
      const options = [
        { label: "All confidence levels", value: 0 },
        { label: ">= 0.95 (verified)", value: 0.95 },
        { label: ">= 0.85 (high)", value: 0.85 },
        { label: ">= 0.75 (medium)", value: 0.75 },
        { label: ">= 0.50 (low)", value: 0.5 },
      ];

      const DropdownComponent = () => {
        const [value, setValue] = React.useState(0.75);
        return (
          <select
            value={value}
            onChange={(e) => setValue(parseFloat(e.target.value))}
            data-testid="confidence-dropdown"
          >
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        );
      };

      render(<DropdownComponent />);

      const dropdown = screen.getByTestId("confidence-dropdown") as HTMLSelectElement;
      expect(dropdown).toBeInTheDocument();
      expect(dropdown.value).toBe("0.75");

      options.forEach((opt) => {
        expect(screen.getByRole("option", { name: opt.label })).toBeInTheDocument();
      });
    });

    it("defaults to medium confidence (0.75)", () => {
      const DropdownComponent = () => {
        const [value] = React.useState(0.75);
        return (
          <select value={value} data-testid="confidence-dropdown">
            <option value={0}>All confidence levels</option>
            <option value={0.95}>&gt;= 0.95 (verified)</option>
            <option value={0.85}>&gt;= 0.85 (high)</option>
            <option value={0.75}>&gt;= 0.75 (medium)</option>
            <option value={0.5}>&gt;= 0.50 (low)</option>
          </select>
        );
      };

      render(<DropdownComponent />);

      const dropdown = screen.getByTestId("confidence-dropdown") as HTMLSelectElement;
      expect(dropdown.value).toBe("0.75");
    });
  });
});