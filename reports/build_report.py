"""Builds reports/F1_EDA_Report.pdf from the text below and the figures in reports/figures.

Run from the repo root:  python reports/build_report.py

Dashboard screenshots: save them as reports/screenshots/dashboard_1.png, dashboard_2.png and
dashboard_3.png, then run the script again. Missing screenshots show as a placeholder box.
"""
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether, NextPageTemplate, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

HERE = Path(__file__).parent
FIG = HERE / "figures"
SHOTS = HERE / "screenshots"
OUT = HERE / "F1_EDA_Report.pdf"

RED = colors.HexColor("#FF2B17")
DARK = colors.HexColor("#15151E")
MUTED = colors.HexColor("#6B6B76")
RULE = colors.HexColor("#DDDDE3")

# ------------------------------------------------------------------ styles
base = getSampleStyleSheet()
body = ParagraphStyle("Body", parent=base["BodyText"], fontName="Helvetica", fontSize=10.5, leading=15,
                      spaceAfter=6, textColor=DARK)
h1 = ParagraphStyle("H1", parent=body, fontName="Helvetica-Bold", fontSize=18, leading=22, spaceBefore=4,
                    spaceAfter=10, textColor=DARK)
h2 = ParagraphStyle("H2", parent=body, fontName="Helvetica-Bold", fontSize=12.5, leading=16, spaceBefore=10,
                    spaceAfter=4, textColor=DARK, keepWithNext=1)
caption = ParagraphStyle("Caption", parent=body, fontSize=9, leading=12.5, textColor=MUTED, spaceAfter=14)
bullet = ParagraphStyle("Bullet", parent=body, leftIndent=14, bulletIndent=3, spaceAfter=3)
cell = ParagraphStyle("Cell", parent=body, fontSize=9, leading=12, spaceAfter=0)
cell_bold = ParagraphStyle("CellBold", parent=cell, fontName="Helvetica-Bold")


def p(text, style=body):
    return Paragraph(text, style)


def bullets(items):
    return [Paragraph(t, bullet, bulletText="•") for t in items]


def table(rows, widths, header=True):
    data = [[Paragraph(str(c), cell_bold if header and i == 0 else cell) for c in row] for i, row in enumerate(rows)]
    t = Table(data, colWidths=widths, hAlign="LEFT")
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
             ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if header:
        style += [("LINEBELOW", (0, 0), (-1, 0), 1.2, RED)]
    t.setStyle(TableStyle(style))
    return t


def figure(name, text, width=16 * cm):
    """An image from reports/figures with a caption, kept on one page."""
    path = FIG / f"{name}.png"
    w, h = ImageReader(str(path)).getSize()
    return KeepTogether([Image(str(path), width=width, height=width * h / w), Spacer(1, 4), p(text, caption)])


def screenshot(n, text):
    """A dashboard screenshot if it exists, otherwise a clearly marked placeholder."""
    path = SHOTS / f"dashboard_{n}.png"
    if path.exists():
        w, h = ImageReader(str(path)).getSize()
        width = 16 * cm
        return KeepTogether([Image(str(path), width=width, height=width * h / w), Spacer(1, 4), p(text, caption)])
    box = Table([[p(f"<b>SCREENSHOT PLACEHOLDER {n}</b><br/>Save the screenshot as "
                    f"reports/screenshots/dashboard_{n}.png and run build_report.py again.",
                    ParagraphStyle("ph", parent=body, alignment=TA_CENTER, textColor=MUTED))]],
                colWidths=[16 * cm], rowHeights=[4.8 * cm])
    box.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1, RED), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6F6F8"))]))
    return KeepTogether([box, Spacer(1, 4), p(text, caption)])


# ------------------------------------------------------------------ page templates
class ReportDoc(BaseDocTemplate):
    def __init__(self, filename):
        super().__init__(filename, pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                         topMargin=2.2 * cm, bottomMargin=2.2 * cm,
                         title="Is the Race Decided on Saturday? An EDA of Formula 1 (1950-2024)",
                         author="Majed Alotaibi")
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="main")
        self.addPageTemplates([PageTemplate(id="title", frames=frame, onPage=title_page),
                               PageTemplate(id="body", frames=frame, onPage=footer)])

    def afterFlowable(self, flowable):
        # every H1 and H2 heading goes into the table of contents with its page number
        if isinstance(flowable, Paragraph) and flowable.style.name in ("H1", "H2"):
            level = 0 if flowable.style.name == "H1" else 1
            self.notify("TOCEntry", (level, flowable.getPlainText(), self.page))


def title_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(DARK)
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canvas.setFillColor(RED)
    canvas.rect(2.2 * cm, A4[1] - 6.0 * cm, 3 * cm, 0.25 * cm, fill=1, stroke=0)
    canvas.restoreState()


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.line(2.2 * cm, 1.5 * cm, A4[0] - 2.2 * cm, 1.5 * cm)
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(2.2 * cm, 1.0 * cm, "F1 EDA Report  |  Majed Alotaibi")
    canvas.drawRightString(A4[0] - 2.2 * cm, 1.0 * cm, str(doc.page))
    canvas.restoreState()


# ------------------------------------------------------------------ content
story = []

# 1. Title page
white = ParagraphStyle("TitleWhite", parent=h1, textColor=colors.white, fontSize=30, leading=36)
sub = ParagraphStyle("SubWhite", parent=body, textColor=colors.HexColor("#C8C8D0"), fontSize=13, leading=19)
story += [Spacer(1, 4.2 * cm),
          p("Is the Race Decided on Saturday?", white),
          p("An exploratory data analysis of Formula 1, 1950 to 2024", sub),
          Spacer(1, 7 * cm),
          p("<b>Majed Alotaibi</b><br/>AI undergraduate, University of Hail<br/>Unit 3 Final Project<br/>"
            f"{date.today():%B %Y}", sub),
          NextPageTemplate("body"), PageBreak()]

# 2. Table of contents
toc = TableOfContents()
toc.levelStyles = [ParagraphStyle("TOC1", parent=body, fontName="Helvetica-Bold", fontSize=11, leftIndent=0,
                                  spaceBefore=6),
                   ParagraphStyle("TOC2", parent=body, fontSize=10, leftIndent=16, spaceBefore=0, spaceAfter=0)]
story += [Paragraph("Table of Contents", ParagraphStyle("TOCTitle", parent=h1)), toc, PageBreak()]

# 3. Introduction
story += [p("1. Introduction", h1), p("Dataset", h2),
          p("I used the <b>Formula 1 World Championship (1950-2020)</b> dataset by Rohan Rao on Kaggle. "
            "It is built from the Ergast API and, despite the name, it is updated past 2020. The version I "
            "downloaded covers every race up to the end of the 2024 season. It has 14 CSV files. I used five "
            "of them, plus the circuits file for names in the dashboard:"),
          table([["File", "Rows", "What it holds"],
                 ["results.csv (main table)", "26,759", "One row per driver per race: grid, position, points, laps, status"],
                 ["races.csv", "1,125", "Year, round, circuit, race name and date"],
                 ["drivers.csv", "861", "Driver names and nationality"],
                 ["constructors.csv", "212", "Team names and nationality"],
                 ["status.csv", "139", "Text label for each finishing status"],
                 ["circuits.csv", "77", "Circuit name and country"]],
                [4.6 * cm, 1.8 * cm, 10.2 * cm]),
          Spacer(1, 8),
          p("I picked this dataset because I am an F1 fan and already had questions about the sport. It is also "
            "a real relational dataset, so the tables have to be joined by ID and there is real cleaning work to do."),
          p("Problem definition", h2),
          p("The dataset covers every Formula 1 World Championship race from 1950 to 2024: who started where, "
            "who finished where, the points scored, and why a driver retired if they did not finish."),
          p("<b>Main question: is the race decided on Saturday?</b> In other words, how much does qualifying "
            "(grid position) decide the result on Sunday?"),
          *bullets(["How strongly does grid position predict finishing position, and has that link grown stronger since 2010?",
                    "Does one constructor dominate each era?",
                    "Have cars become more reliable (fewer DNFs, fewer mechanical failures)?"]),
          p("Insights I expect to find", h2),
          *bullets(["Pole position wins a large share of races, and the grid matters more in the modern era.",
                    "Each era has one team that wins far more than the rest.",
                    "DNF rates fall a lot over time, mostly because cars break down less."]),
          p("For the grid vs result questions I use 2010-2024, because the cars and rules in that period are more "
            "comparable. For reliability and dominance I use the full 1950-2024 range. All 75 seasons are complete."),
          PageBreak()]

# 4. Data exploration
story += [p("2. Data Exploration", h1),
          p("I first loaded every file with a plain <font face='Courier'>read_csv</font> and looked at "
            "<font face='Courier'>head()</font>, <font face='Courier'>shape</font>, <font face='Courier'>info()</font>, "
            "<font face='Courier'>describe()</font> and <font face='Courier'>isnull().sum()</font>, first for "
            "results.csv and then for the merged table."),
          p("What the raw data showed", h2),
          *bullets(["results.csv has 26,759 rows and 18 columns. After joining the other tables by raceId, driverId, "
                    "constructorId, statusId and circuitId the merged table still has 26,759 rows, so no row was lost "
                    "or duplicated by the joins.",
                    "<font face='Courier'>isnull().sum()</font> said nothing was missing. That was wrong. Missing values "
                    "are stored as the text <font face='Courier'>\\N</font>, so pandas read them as normal strings.",
                    "Because of this, <font face='Courier'>position</font>, <font face='Courier'>milliseconds</font> "
                    "and <font face='Courier'>fastestLapSpeed</font> were loaded as text (object) instead of numbers.",
                    "<font face='Courier'>fastestLapTime</font> is text like \"1:27.452\".",
                    "Grid runs from 0 to 34. A grid of 0 means a pit-lane start or no grid slot.",
                    "Finishing order (<font face='Courier'>positionOrder</font>) goes up to 39 and laps up to 200 "
                    "(the Indianapolis 500 was part of the championship in the 1950s).",
                    "There are 139 different status labels, from \"Finished\" and \"+1 Lap\" to \"Engine\", \"Magneto\" and \"Collision\"."]),
          p("Missing values after reading \\N correctly", h2),
          table([["Column", "Missing", "Why it is missing"],
                 ["position", "10,953", "Driver was not classified (DNF, DNQ and so on)"],
                 ["milliseconds / time", "19,079", "Race time only exists for classified finishers"],
                 ["fastestLapTime / fastestLapSpeed", "18,507", "Fastest lap data only exists from 2004"]],
                [5.4 * cm, 2.2 * cm, 9 * cm]),
          PageBreak()]

# 5. Data cleaning
story += [p("3. Data Cleaning", h1),
          p("All cleaning is done in the notebook (Step 4) and the result is saved as "
            "<font face='Courier'>data/clean_data.csv</font> (26,759 rows, 32 columns). The steps:"),
          *bullets(["<b>Missing values.</b> Read every file with <font face='Courier'>na_values=['\\\\N']</font>. "
                    "The before and after table in the notebook shows the counts above appear only after this step.",
                    "<b>Text to numbers.</b> Converted position, milliseconds and fastestLapSpeed with "
                    "<font face='Courier'>pd.to_numeric</font>.",
                    "<b>Lap time.</b> Turned fastestLapTime (\"1:27.452\") into seconds (87.452) in a new column "
                    "<font face='Courier'>fastest_lap_sec</font>.",
                    "<b>Grid 0.</b> 1,638 rows have grid 0. I kept them but added <font face='Courier'>grid_clean</font> "
                    "where 0 becomes NaN, and used grid_clean for every grid analysis.",
                    "<b>Name clashes.</b> Several tables have a <font face='Courier'>name</font> column. They became "
                    "race_name, team and circuit_name. I also built driver = forename + surname.",
                    "<b>Year range.</b> Kept 1950-2024 only, so no partial season is included.",
                    "<b>Duplicates.</b> <font face='Courier'>df.duplicated().sum()</font> is 0. There are 91 cases of the "
                    "same driver twice in one race. These are real 1950s shared drives, so I kept them."]),
          p("New columns", h2),
          table([["Column", "Meaning"],
                 ["finished", "True if status is \"Finished\" or \"+n Lap(s)\". These drivers were classified."],
                 ["starter", "False for did not qualify, did not prequalify, withdrew, did not start, excluded, not classified."],
                 ["dnf", "A starter who did not finish."],
                 ["dnf_type", "Mechanical, Crash/collision or Other. Built by grouping the 130+ status labels."],
                 ["decade", "1950, 1960 ... 2020."],
                 ["podium / win", "positionOrder of 3 or better / positionOrder equal to 1."]],
                [3.4 * cm, 13.2 * cm]),
          Spacer(1, 6),
          p("For dnf_type, crash/collision covers Accident, Collision, Collision damage, Spun off, Puncture, Damage "
            "and Debris. Other covers labels like Retired, Disqualified and driver illness. Everything else "
            "(engine, gearbox, brakes, hydraulics, magneto ...) counts as mechanical."),
          PageBreak()]

# 6. EDA
story += [p("4. Exploratory Data Analysis", h1),
          p("All plots use the same style: dark background, red for the main point and grey for the rest. "
            "Each title states the finding."),
          p("Univariate", h2),
          figure("01_laps_completed_hist",
                 "Figure 1. Laps completed as a share of the winner's laps, all starters 1950-2024. About half of "
                 "the starters reach the end (red bar). The flat tail is retirements, with a spike in the first laps."),
          figure("02_top_constructors_wins",
                 "Figure 2. Top 10 constructors by race wins, 1950-2024. Ferrari leads. Mercedes got most of its "
                 "wins in only 11 seasons."),
          figure("03_dnf_reasons_modern",
                 "Figure 3. Top 10 DNF reasons, 2010-2024. Collision is the biggest single label. Mechanical "
                 "problems are split over many labels, so as a group they are still the largest."),
          figure("04_points_by_team_box",
                 "Figure 4. Points per car per race, 2010-2024, top 6 teams by points. Mercedes and Red Bull both have "
                 "a median of 12 points. The dots at 50 and 36 are the double-points race in Abu Dhabi 2014."),
          CondPageBreak(10 * cm), p("Bivariate and multivariate", h2),
          figure("05_grid_vs_finish_scatter",
                 "Figure 5. Grid vs finishing position, classified finishers 2010-2024, with jitter and a linear trend. "
                 "The correlation is 0.78.", width=13.5 * cm),
          figure("06_podium_rate_by_grid",
                 "Figure 6. Podium rate by grid slot, 2010-2024. 80% from pole, 20% from P5 and about 4% from P8 to P10."),
          figure("07_dnf_rate_by_decade",
                 "Figure 7. DNF rate among starters per decade (red) and the mechanical part only (grey). About half "
                 "of starters retired until the 1980s. In the 2020s it is 14%, and mechanical DNFs are 6%."),
          figure("08_top_constructor_by_era",
                 "Figure 8. Win share of the top constructor in each era. Mercedes in 2014-2020 (74%) is the most "
                 "dominant team in the data."),
          figure("09_correlation_heatmap",
                 "Figure 9. Correlation between numeric columns, classified finishers 1950-2024. Grid vs finishing "
                 "position (0.68) is the strongest link that is not built into the scoring rules.", width=12 * cm),
          figure("10_grid_finish_heatmap",
                 "Figure 10. Where each grid slot finished, 2010-2024 (each row adds to 100%). The bright diagonal "
                 "shows most drivers finish close to where they start. Pole ends in a win 51% of the time."),
          PageBreak()]

# 7. Dashboard
story += [p("5. Dashboard Overview", h1),
          p("The Streamlit dashboard (<font face='Courier'>app/app.py</font>) loads clean_data.csv and lets the user "
            "explore the same questions. Run it with <font face='Courier'>streamlit run app/app.py</font>."),
          *bullets(["<b>Filter bar:</b> pinned to the top of the page instead of a sidebar, so the charts get the full "
                    "width. It has a season range slider (default 2010-2024), a constructor multiselect, a circuit "
                    "dropdown and a reset button. The dataset description is at the bottom of the page.",
                    "<b>Headline:</b> the main question with a short answer that changes with the filters, and four stat "
                    "tiles: wins from pole, wins from the front row, finishers within 3 places of their grid slot, and DNF "
                    "rate. Each tile shows how far the selection is from the 1950-2024 value.",
                    "<b>Qualifying tab:</b> win, podium or points rate by grid slot (switchable), a grid vs result heatmap "
                    "and the distribution of places gained or lost.",
                    "<b>Dominance tab:</b> the leading team's share of wins in every season, the teams with the most wins, "
                    "and a table of the top team in each era.",
                    "<b>Reliability tab:</b> DNF rate per season (all and mechanical) and what ended the race in each decade.",
                    "<b>Drivers tab:</b> pick a driver to see starts, wins, podiums, pole starts, places gained and "
                    "podiums per season.",
                    "<b>Predict tab:</b> pick a grid slot, team and season and the logistic regression gives a podium "
                    "chance, with the chance from every grid slot shown as a bar chart.",
                    "<b>Data tab:</b> a preview of the filtered rows, summary statistics and a CSV download.",
                    "Every chart has hover details, and each tab ends with a short insight written from the filtered data."]),
          Spacer(1, 6),
          screenshot(1, "Figure 11. The filter bar, the headline answer and the four stat tiles."),
          screenshot(2, "Figure 12. Qualifying tab: rate by grid slot, grid vs result heatmap and places gained."),
          screenshot(3, "Figure 13. Predict tab: podium chance for a chosen grid slot, team and season."),
          PageBreak()]

# 8. Insights & conclusion
story += [p("6. Insights and Conclusion", h1), p("Main insights", h2),
          *bullets(["<b>Qualifying decides most of the race.</b> Since 2010 the pole sitter won 51% of races, the front "
                    "row won 77%, and only 4 of 305 races were won from outside the top 10.",
                    "<b>Grid predicts the finish.</b> The correlation is 0.78 for classified finishers, and 67% of them "
                    "finish within 3 places of their grid slot.",
                    "<b>One team rules each era.</b> Mercedes won 102 of 138 races (74%) from 2014 to 2020. Red Bull "
                    "won 21 of 22 races in 2023.",
                    "<b>Cars are far more reliable.</b> The DNF rate among starters fell from about 49% in the 1950s to "
                    "14% in the 2020s. Mechanical DNFs fell from 38% of starters to 6%.",
                    "<b>Retirements today.</b> Since 2010, 51% of retirements are mechanical, 41% are crashes or "
                    "collisions and 8% are other reasons."]),
          p("Key numbers", h2),
          table([["Stat", "Value"],
                 ["Rows / races / drivers / constructors / seasons", "26,759 / 1,125 / 861 / 211 / 75"],
                 ["Podium rate by grid P1 to P10, 2010-2024", "80, 69, 51, 35, 20, 14, 8, 3, 4, 4 %"],
                 ["DNF rate among starters, 1950s to 2020s", "49, 49, 47, 55, 50, 32, 19, 14 %"],
                 ["Top era winners", "1950s Ferrari 34%, 1960s Lotus-Climax 22%, 1970s Ferrari 26%, 1980s McLaren 36%, "
                                     "1990s Williams 38%, 2000s Ferrari 49%, 2010-13 Red Bull 53%, 2014-20 Mercedes 74%, "
                                     "2021-24 Red Bull 64%"],
                 ["Most wins, 1950-2024", "Hamilton 105, Schumacher 91, Verstappen 63"]],
                [6.6 * cm, 10 * cm]),
          p("Podium model", h2),
          p("A logistic regression predicts a podium from grid slot, team (top 6 plus Other) and year, trained on "
            "2010-2024 starters with a stratified 80/20 split. It reaches precision 0.71, recall 0.53, F1 0.61 and "
            "ROC-AUC 0.92. A dummy model that always says \"no podium\" gets 0 for precision, recall and F1, and 0.50 "
            "ROC-AUC. Grid slot does most of the work."),
          p("Conclusion", h2),
          p("The race is not fully decided on Saturday, but most of it is. Grid position and the car explain most of "
            "the result, and Sunday mostly moves drivers by a few places."),
          p("What I learned", h2),
          *bullets(["How to join several tables by ID and check that a merge did not lose or duplicate rows.",
                    "Missing values are not always NaN. Here they were the text \\N and isnull() missed them.",
                    "How to turn 130+ messy labels into a few groups that answer a question.",
                    "A model needs a baseline. Accuracy alone looks good even for a model that does nothing."]),
          p("Limitations", h2),
          *bullets(["The points system changed several times, so I compare positions and wins instead of points across eras.",
                    "Status labels are not consistent across decades, so the mechanical vs crash split is approximate.",
                    "There is no weather, tyre or strategy data in these tables.",
                    "Grids before the 1980s had different sizes, so grid slots are not fully comparable across eras."]),
          p("Future recommendations", h2),
          *bullets(["Add the pit_stops and lap_times tables to see where places are gained or lost during the race.",
                    "Compare street circuits with permanent tracks.",
                    "Improve the podium model with qualifying gaps, driver form and circuit type."]),
          PageBreak()]

# 9. References
story += [p("7. References", h1),
          *bullets(["Rao, R. Formula 1 World Championship (1950-2020). Kaggle. "
                    "https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020",
                    "Ergast Developer API (original source of the data). https://ergast.com/mrd/",
                    "pandas: https://pandas.pydata.org",
                    "NumPy: https://numpy.org",
                    "Matplotlib: https://matplotlib.org",
                    "seaborn: https://seaborn.pydata.org",
                    "Plotly: https://plotly.com/python/",
                    "Streamlit: https://streamlit.io",
                    "scikit-learn: https://scikit-learn.org",
                    "ReportLab (used to build this PDF): https://www.reportlab.com"])]

ReportDoc(str(OUT)).multiBuild(story)
print("wrote", OUT)
