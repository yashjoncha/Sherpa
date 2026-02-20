"""Generate FAB (Family and Business Learning) project context PDF for RAG ingestion."""

from fpdf import FPDF
from pathlib import Path


OUTPUT_PATH = Path(__file__).resolve().parent.parent / "pdf" / "fab_project_context.pdf"


class FABPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "FAB - Project Context", align="R")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(30, 30, 30)
        self.ln(4)
        self.cell(0, 10, title)
        self.ln(8)
        self.set_draw_color(60, 60, 60)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def sub_title(self, title):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(50, 50, 50)
        self.ln(2)
        self.cell(0, 8, title)
        self.ln(6)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def bullet(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        self.cell(0, 6, f"    -  {text}")
        self.ln(5)

    def key_value(self, key, value):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(40, 40, 40)
        self.cell(50, 6, f"{key}:")
        self.set_font("Helvetica", "", 10)
        self.cell(0, 6, value)
        self.ln(6)

    def status_row(self, label, status):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(40, 40, 40)
        self.cell(60, 6, f"{label}:")
        self.set_font("Helvetica", "", 10)
        self.cell(0, 6, status)
        self.ln(6)


def build_pdf():
    pdf = FABPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── Page 1: Project Overview ──────────────────────────────
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 15, "FAB", align="C")
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 8, "Family and Business Learning", align="C")
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 8, "Family Advisory Behavioral Intelligence Platform", align="C")
    pdf.ln(6)
    pdf.cell(0, 8, "Survey-driven Family Communication Analysis Dashboard", align="C")
    pdf.ln(14)

    pdf.section_title("Product Overview")
    pdf.body_text(
        "FAB is a digital advisory support platform designed for family business ecosystems. "
        "Advisors use the platform to conduct structured behavioral and communication surveys "
        "within family-run organizations to assess interpersonal dynamics and governance patterns."
    )

    pdf.sub_title("The Platform Enables")
    for item in [
        "Collection of structured survey data from family members",
        "Behavioral mapping across stakeholders",
        "Communication pattern analysis",
        "Advisory-led intervention planning",
        "Automated report generation (FFE and IFR)",
    ]:
        pdf.bullet(item)

    pdf.ln(4)
    pdf.sub_title("Report Types")
    pdf.body_text(
        "FFE (Family Functioning Evaluation): Evaluates overall family functioning patterns "
        "across the business unit."
    )
    pdf.body_text(
        "IFR (Interpersonal Functioning Report): Analyzes interpersonal dynamics and "
        "communication patterns between individual family members."
    )

    pdf.sub_title("Reports Provide Insights Into")
    for item in [
        "Family relationship dynamics",
        "Communication breakdowns",
        "Behavioral alignment/misalignment",
        "Governance conflicts",
        "Leadership influence patterns",
    ]:
        pdf.bullet(item)

    pdf.ln(4)
    pdf.sub_title("Primary Goal")
    pdf.body_text(
        "Enable advisors to identify communication gaps and behavioral misalignments "
        "within family business units and provide insight-driven intervention strategies "
        "using survey-based diagnostic reporting."
    )

    # ── Page 2: Team ──────────────────────────────────────────
    pdf.add_page()

    pdf.section_title("Team Allocation")
    pdf.body_text(
        "All listed members are actively contributing to FAB across development "
        "and reporting workflows."
    )
    for name in [
        "Yash",
        "Sakshi",
        "Rohit",
        "Siddhi",
        "Sagar",
        "Tanvi",
        "Esha",
        "Ria",
        "Sanika",
    ]:
        pdf.bullet(name)

    # ── Sprint Context ────────────────────────────────────────
    pdf.ln(6)
    pdf.section_title("Sprint Context")

    pdf.key_value("Sprint Name", "Pikachu")
    pdf.key_value("Start", "Ongoing")
    pdf.key_value("End", "24 February 2026")
    pdf.ln(4)

    pdf.sub_title("Sprint Objective")
    pdf.body_text("Enhancement and stabilization of reporting infrastructure including:")
    for item in [
        "FFE report generation pipeline",
        "IFR behavioral output formatting",
        "Survey result aggregation logic",
        "Advisor dashboard reporting views",
        "Report delivery performance optimization",
    ]:
        pdf.bullet(item)

    pdf.ln(4)
    pdf.sub_title("Focus Area")
    pdf.body_text("Survey -> Analysis -> Report Generation Lifecycle")

    # ── Page 3: Sprint Status ─────────────────────────────────
    pdf.add_page()

    pdf.section_title("Current Sprint Status")

    pdf.sub_title("Blocked Tickets")
    pdf.body_text("None currently blocked.")

    pdf.sub_title("Tickets At Risk")
    pdf.body_text("No tickets are currently expected to miss the 24 Feb sprint deadline.")

    pdf.sub_title("Workload Observations")
    pdf.body_text(
        "Team is collectively aligned toward reporting module completion. "
        "No immediate resource bottlenecks identified."
    )

    pdf.sub_title("Recent Development Activity (Last 2-3 Days)")
    for item in [
        "Improvements to report generation flow",
        "Backend optimizations for behavioral scoring",
        "UI-level updates for advisor report access",
        "Enhancements in survey data processing for FFE/IFR outputs",
    ]:
        pdf.bullet(item)

    pdf.ln(6)
    pdf.status_row("Sprint Health", "On Track")
    pdf.status_row("Deadline Risk", "Low")
    pdf.status_row("System Stability", "Moderate (reporting enhancements underway)")

    # ── Save ──────────────────────────────────────────────────
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUTPUT_PATH))
    print(f"PDF saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    build_pdf()
