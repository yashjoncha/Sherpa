"""Generate Sparkable AI project context PDF for RAG ingestion."""

from fpdf import FPDF
from pathlib import Path


OUTPUT_PATH = Path(__file__).resolve().parent.parent / "pdf" / "sparkable_ai_project_context.pdf"


class SparkablePDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "Sparkable AI - Project Context", align="R")
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
        # underline
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
    pdf = SparkablePDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── Page 1: Project Overview ──────────────────────────────
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 15, "Sparkable AI", align="C")
    pdf.ln(12)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 8, "Service-Based AI Brand Identity Generation Platform", align="C")
    pdf.ln(6)
    pdf.cell(0, 8, "Guided Brand Design Workflow System", align="C")
    pdf.ln(14)

    pdf.section_title("Product Overview")
    pdf.body_text(
        "Sparkable AI is an AI-assisted brand identity creation platform that enables "
        "users to generate end-to-end brand design guides through a structured, "
        "wizard-based input system."
    )

    pdf.sub_title("Users Define")
    for item in [
        "Brand Vision",
        "Communication Tone",
        "Color Preferences",
        "Typography Styles",
        "Visual Inspiration",
        "Design References",
    ]:
        pdf.bullet(item)

    pdf.ln(4)
    pdf.body_text(
        "Through a 16-step guided form interface, the platform collects brand-specific "
        "inputs which are then used to generate:"
    )

    pdf.sub_title("Generated Outputs")
    for item in [
        "Brand Guides",
        "Color Systems",
        "Logo Directions",
        "Mood Boards",
        "Visual Identity Frameworks",
    ]:
        pdf.bullet(item)

    pdf.ln(4)
    pdf.sub_title("Post Submission Workflow")
    pdf.body_text(
        "After a user submits their brand guide inputs, the Super Admin reviews the guide "
        "and assigns a Lead Designer. The Lead Designer then assigns execution team members "
        "including a Primary Designer and Secondary Designers. Designers collaborate on "
        "execution, with strict access control ensuring designers can only view their "
        "assigned guides."
    )

    # ── Page 2: Roles & Team ──────────────────────────────────
    pdf.add_page()

    pdf.section_title("Role-Based Workflow")

    roles = [
        ("Regular User", "Creates and submits brand guide inputs via the wizard interface."),
        ("Account Admin", "Manages internal team members within their account."),
        ("Super Admin", "Reviews submitted guides and assigns Lead Designers."),
        (
            "Lead Designer",
            "Assigns execution team including Primary Designer and Secondary Designers.",
        ),
        (
            "Designers",
            "Work only on assigned brand guides. Strict access isolation is enforced.",
        ),
    ]
    for role, desc in roles:
        pdf.sub_title(role)
        pdf.body_text(desc)

    pdf.section_title("Team Allocation")
    for name in ["Yash", "Siddhi", "Sanika"]:
        pdf.bullet(name)

    # ── Page 3: Sprint Context ────────────────────────────────
    pdf.add_page()

    pdf.section_title("Sprint Context")

    pdf.key_value("Sprint Name", "Pikachu")
    pdf.key_value("Start", "Ongoing")
    pdf.key_value("End", "24 February 2026")
    pdf.ln(4)

    pdf.sub_title("Sprint Objective")
    pdf.body_text("Improve UX across:")
    for item in [
        "User dashboard navigation",
        "Brand guide creation wizard",
        "Assets & guides listing",
        "Designer workflow visibility",
        "Guide submission experience",
    ]:
        pdf.bullet(item)

    pdf.ln(4)
    pdf.sub_title("Focus Area")
    pdf.body_text("User Journey Optimization (Input -> Assignment -> Execution)")

    # ── Sprint Status ─────────────────────────────────────────
    pdf.section_title("Current Sprint Status")

    pdf.sub_title("Blocked Tickets")
    pdf.body_text("None currently blocked.")

    pdf.sub_title("Tickets At Risk")
    pdf.body_text("No tickets are currently expected to miss the 24 Feb sprint deadline.")

    pdf.sub_title("Workload Observations")
    pdf.body_text(
        "Team currently focused on UX-level enhancements. "
        "Minimal backend dependency observed."
    )

    pdf.sub_title("Recent Development Activity (Last 2-3 Days)")
    for item in [
        "Carousel UI improvements in dashboard",
        "Enhanced visual navigation in brand guide flow",
        "Minor accessibility adjustments",
        "Layout refinements for guide preview components",
    ]:
        pdf.bullet(item)

    pdf.ln(6)
    pdf.status_row("Sprint Health", "On Track")
    pdf.status_row("Deadline Risk", "Low")
    pdf.status_row("System Stability", "Stable")

    # ── Save ──────────────────────────────────────────────────
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUTPUT_PATH))
    print(f"PDF saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    build_pdf()
