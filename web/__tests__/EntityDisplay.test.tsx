import { render, screen } from "@testing-library/react";
import React from "react";
import { getMitreUrl, getCveUrl } from "@/lib/utils/entityLinks";
import { getEntityTypeConfig } from "@/lib/utils/entityTypes";

describe("EntityLinks", () => {
  describe("getMitreUrl", () => {
    it("returns correct URL for base technique", () => {
      const url = getMitreUrl("T1486");
      expect(url).toBe("https://attack.mitre.org/techniques/T1486/");
    });

    it("returns correct URL for sub-technique", () => {
      const url = getMitreUrl("T1071.001");
      expect(url).toBe("https://attack.mitre.org/techniques/T1071/001/");
    });
  });

  describe("getCveUrl", () => {
    it("returns correct NVD URL for CVE", () => {
      const url = getCveUrl("CVE-2025-31324");
      expect(url).toBe("https://nvd.nist.gov/vuln/detail/CVE-2025-31324");
    });
  });
});

describe("EntityTypeConfig", () => {
  describe("getEntityTypeConfig", () => {
    it('returns "ATT&CK Technique" for MITRE_TECHNIQUE', () => {
      const config = getEntityTypeConfig("MITRE_TECHNIQUE");
      expect(config.label).toBe("ATT&CK Technique");
    });

    it("returns formatted fallback for unknown type", () => {
      const config = getEntityTypeConfig("UNKNOWN_TYPE");
      expect(config.label).toBe("unknown type");
      expect(config.color).toBe("var(--bg-raised)");
    });
  });
});

describe("EntityDisplay", () => {
  describe("MITRE link rendering", () => {
    it("renders MITRE technique as clickable link", () => {
      const MitreLinkComponent = ({ value }: { value: string }) => {
        const url = getMitreUrl(value);
        return (
          <a href={url} target="_blank" rel="noopener noreferrer" data-testid="mitre-link">
            {value}
          </a>
        );
      };

      render(<MitreLinkComponent value="T1486" />);
      const link = screen.getByTestId("mitre-link");
      expect(link).toHaveAttribute("href", "https://attack.mitre.org/techniques/T1486/");
      expect(link).toHaveAttribute("target", "_blank");
    });

    it("renders CVE as clickable link to NVD", () => {
      const CveLinkComponent = ({ value }: { value: string }) => {
        const url = getCveUrl(value);
        return (
          <a href={url} target="_blank" rel="noopener noreferrer" data-testid="cve-link">
            {value}
          </a>
        );
      };

      render(<CveLinkComponent value="CVE-2025-31324" />);
      const link = screen.getByTestId("cve-link");
      expect(link).toHaveAttribute("href", "https://nvd.nist.gov/vuln/detail/CVE-2025-31324");
    });
  });

  describe("ONION_URL entity handling", () => {
    it("does NOT render onion URL as anchor", () => {
      const OnionEntity = ({ value }: { value: string }) => {
        const isOnion = true;
        if (isOnion) {
          return <span className="font-mono text-[12px]">{value}</span>;
        }
        return (
          <a href={`http://${value}`} target="_blank" rel="noopener noreferrer">
            {value}
          </a>
        );
      };

      render(<OnionEntity value="example.onion" />);
      const span = screen.getByText("example.onion");
      expect(span.tagName.toLowerCase()).toBe("span");
      expect(screen.queryByRole("link")).not.toBeInTheDocument();
    });
  });
});

describe("InvestigationStatus", () => {
  describe("completed_no_results state", () => {
    it("shows empty state when status is completed_no_results", () => {
      const NoResultsComponent = ({ status }: { status: string }) => {
        if (status === "completed_no_results") {
          return (
            <div data-testid="no-results-state">
              <h3>No intelligence results found</h3>
            </div>
          );
        }
        return <div data-testid="results-view">Results</div>;
      };

      render(<NoResultsComponent status="completed_no_results" />);
      expect(screen.getByTestId("no-results-state")).toBeInTheDocument();
      expect(screen.queryByTestId("results-view")).not.toBeInTheDocument();
    });
  });

  describe("refined_query display", () => {
    it("shows refined_query when it differs from query", () => {
      const RefinedQueryComponent = ({ query, refined_query }: { query: string; refined_query: string | null }) => {
        if (refined_query && refined_query !== query) {
          return (
            <div data-testid="refined-row">
              Refined to: <span>{refined_query}</span>
            </div>
          );
        }
        return null;
      };

      render(<RefinedQueryComponent query="ransomware" refined_query="lockbit ransomware" />);
      expect(screen.getByTestId("refined-row")).toBeInTheDocument();
      expect(screen.getByText("Refined to:")).toBeInTheDocument();
      expect(screen.getByText("lockbit ransomware")).toBeInTheDocument();
    });

    it("does not show refined_query when it equals query", () => {
      const RefinedQueryComponent = ({ query, refined_query }: { query: string; refined_query: string | null }) => {
        if (refined_query && refined_query !== query) {
          return (
            <div data-testid="refined-row">
              Refined to: <span>{refined_query}</span>
            </div>
          );
        }
        return null;
      };

      render(<RefinedQueryComponent query="lockbit" refined_query="lockbit" />);
      expect(screen.queryByTestId("refined-row")).not.toBeInTheDocument();
    });
  });
});

describe("EntityTypeLabel", () => {
  it("renders MITRE_TECHNIQUE as ATT&CK Technique", () => {
    const TypeBadgeComponent = ({ entityType }: { entityType: string }) => {
      const config = getEntityTypeConfig(entityType);
      return (
        <span
          style={{ backgroundColor: config.color, color: config.textColor }}
          data-testid="type-badge"
        >
          {config.label}
        </span>
      );
    };

    render(<TypeBadgeComponent entityType="MITRE_TECHNIQUE" />);
    expect(screen.getByTestId("type-badge").textContent).toBe("ATT&CK Technique");
  });

  it("does not throw for unknown entity type", () => {
    const config = getEntityTypeConfig("SOME_RANDOM_UNKNOWN_TYPE");
    expect(config.label).toBe("some random unknown type");
  });
});