"""Validate course content without reading student projects or secret files."""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

import markdown
import yaml


SECTIONS = ("syllabus", "labs", "lectures", "assessment", "materials")
STUDENT_EXTRAS = ("solutions/README.md",)


def student_pages(root: Path) -> list[Path]:
    pages = [root / "README.md"]
    for section in SECTIONS:
        pages.extend(sorted((root / section).rglob("*.md")))
    pages.extend(root / name for name in STUDENT_EXTRAS)
    return pages


def number(text: object) -> Decimal:
    return Decimal(str(text).replace(",", ".").replace("**", "").strip())


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    match = re.match(r"\A---\n(.*?)\n---(?:\n|$)(.*)\Z", text, re.S)
    if not match:
        raise ValueError("unclosed YAML front matter")
    data = yaml.safe_load(match[1])
    if not isinstance(data, dict):
        raise ValueError("front matter must be a mapping")
    return data, match[2]


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.targets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if value and ((tag == "a" and key == "href") or (tag == "img" and key == "src")):
                self.targets.append(value)


def validate(root: Path, staged: bool = False) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    pages = student_pages(root)
    for path in pages:
        relative = path.relative_to(root).as_posix()
        if not path.is_file():
            errors.append(f"{relative}: required page is missing")
            continue
        text = path.read_text(encoding="utf-8")
        try:
            _, body = split_frontmatter(text)
        except (ValueError, yaml.YAMLError) as exc:
            errors.append(f"{relative}: invalid metadata: {exc}")
            continue
        if re.search(r"\bTODO\b|\bFIXME\b", body):
            errors.append(f"{relative}: unfinished author placeholder")
        obsolete = (
            r"репозиторий не (?:нужен|требуется)",
            r"для ЛР №1 нужен только PDF",
            r"PDF, без репозитория",
            r"загрузите.*(?:учебн\w* диск|диск\w* отч[её]т)",
            r"PDF загружается.*диск",
        )
        if any(re.search(pattern, body, re.I) for pattern in obsolete):
            errors.append(f"{relative}: obsolete first-lab or shared-drive submission policy")
        links = Links()
        links.feed(markdown.markdown(body, extensions=["fenced_code", "tables", "toc"]))
        for href in links.targets:
            url = urlsplit(href)
            if url.scheme or url.netloc or not url.path:
                continue
            target = (path.parent / unquote(url.path)).resolve()
            if not target.is_relative_to(root) or not target.exists():
                errors.append(f"{relative}: missing local link {href}")

    first_lab = (root / "labs/01-docker.md").read_text(encoding="utf-8")
    if "solutions/reports/lab-1/" not in first_lab or "исходники LaTeX" not in first_lab:
        errors.append("lab-1: repository PDF and LaTeX sources must be required")
    report_root = root / "materials/report-latex"
    expected = {"main.tex", "Paper.tex", "gost.sty"}
    actual = {p.name for p in report_root.iterdir()} if report_root.is_dir() else set()
    if actual != expected:
        errors.append(f"LaTeX template: expected only three source files, got {sorted(actual)}")
    if expected <= actual:
        main = (report_root / "main.tex").read_text(encoding="utf-8")
        if r"\input{Paper}" not in main or r"\usepackage{gost}" not in main:
            errors.append("LaTeX template: main.tex must load Paper.tex and gost.sty")

    lab_files = sorted((root / "labs").glob("[0-9][0-9]-*.md"))
    lab_numbers: list[int] = []
    minimum_total = Decimal(0)
    maximum_total = Decimal(0)
    assessment = (root / "assessment/README.md").read_text(encoding="utf-8")
    home = (root / "README.md").read_text(encoding="utf-8")
    index = (root / "labs/README.md").read_text(encoding="utf-8")
    for path in lab_files:
        try:
            meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
            lab = meta["lab"]
            if type(lab) is not int or not meta.get("title"):
                raise ValueError("lab must be an integer and title must not be empty")
            low, high = number(meta["min_score"]), number(meta["max_score"])
            if not low.is_finite() or not high.is_finite() or not 0 < low <= high:
                raise ValueError("invalid score interval")
            if low * 2 != high:
                raise ValueError("current course requires minimum = maximum / 2")
            if int(path.name[:2]) != lab:
                raise ValueError("lab number differs from filename")
            lab_numbers.append(lab)
            minimum_total += low
            maximum_total += high
            passport = re.search(
                r"\|\s*Минимум\s*\|\s*Максимум\s*\|[^\n]*\n[^\n]+\n\|\s*([^|]+)\|\s*([^|]+)\|",
                body,
            )
            if not passport or (number(passport[1]), number(passport[2])) != (low, high):
                raise ValueError("passport differs from min_score/max_score")
            criteria = re.search(
                r"^## Критерии приема результатов\s*\n(.*?)(?=^## |\Z)",
                body, re.M | re.S,
            )
            if not criteria:
                raise ValueError("criteria section is missing")
            scores: list[Decimal] = []
            declared_total = None
            for row in criteria[1].splitlines():
                cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
                if not row.startswith("|") or len(cells) != 2:
                    continue
                try:
                    score = number(cells[1])
                except InvalidOperation:
                    continue
                if "Итого" in cells[0]:
                    declared_total = score
                else:
                    scores.append(score)
            if declared_total != high or sum(scores, Decimal(0)) != high:
                raise ValueError("criteria sum or total differs from max_score")
            row = next((line for line in assessment.splitlines() if f"../labs/{path.name})" in line), "")
            cells = row.strip().strip("|").split("|")
            if len(cells) != 3 or (number(cells[1]), number(cells[2])) != (low, high):
                raise ValueError("assessment table differs from metadata")
            for label, text in (("README", home), ("lab index", index)):
                row = next((line for line in text.splitlines() if f"{path.name})" in line), "")
                pair = row.strip().strip("|").split("|")[-1].split("/")
                if len(pair) != 2 or (number(pair[0]), number(pair[1])) != (low, high):
                    raise ValueError(f"{label} scores differ from metadata")
        except (ValueError, KeyError, InvalidOperation, yaml.YAMLError) as exc:
            errors.append(f"labs/{path.name}: {exc}")
    if sorted(lab_numbers) != list(range(1, 7)):
        errors.append("labs: expected unique mandatory works 1 through 6")
    if (minimum_total, maximum_total) != (Decimal(35), Decimal(70)):
        errors.append("labs: current course total must be 35 / 70")
    total_row = next((row for row in assessment.splitlines() if row.startswith("| Итого |")), "")
    try:
        cells = total_row.strip().strip("|").split("|")
        if (number(cells[1]), number(cells[2])) != (minimum_total, maximum_total):
            raise ValueError
    except (ValueError, IndexError, InvalidOperation):
        errors.append("assessment: total row differs from laboratory totals")

    config = yaml.load(
        (root / ".github/docs/mkdocs.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )

    def check_nav(item: object) -> None:
        if isinstance(item, list):
            for child in item:
                check_nav(child)
        elif isinstance(item, dict):
            for child in item.values():
                check_nav(child)
        elif isinstance(item, str) and not urlsplit(item).scheme:
            target = root / item
            if not target.is_file() or target not in pages:
                errors.append(f"nav: missing or non-student page {item}")

    check_nav(config.get("nav", []))
    if staged:
        stage = root / ".site-src/docs"
        expected = {page.relative_to(root).as_posix() for page in pages if page.is_file()}
        actual = {path.relative_to(stage).as_posix() for path in stage.rglob("*.md")}
        if actual != expected:
            errors.append(f"staging: unexpected={sorted(actual - expected)}, missing={sorted(expected - actual)}")
        for path in stage.rglob("*"):
            rel = path.relative_to(stage)
            if path.is_symlink() or any(part.startswith(".") for part in rel.parts):
                errors.append(f"staging: hidden file or symlink {rel}")
            if any(part in {".github", "meta", "node_modules", "__pycache__", "venv"} for part in rel.parts):
                errors.append(f"staging: infrastructure leaked: {rel}")
            if path.name == "00-template.md":
                errors.append(f"staging: author template leaked: {rel}")
            if rel.parts and rel.parts[0] == "solutions" and path.is_file() and rel.as_posix() not in STUDENT_EXTRAS:
                errors.append(f"staging: student project leaked: {rel}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="also check generated publication boundaries")
    args = parser.parse_args()
    errors = validate(Path(__file__).resolve().parents[2], staged=args.staged)
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print("Course checks passed: links, metadata, scores, navigation, minimal LaTeX template, submission policy"
          + (", publication boundaries." if args.staged else "."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
