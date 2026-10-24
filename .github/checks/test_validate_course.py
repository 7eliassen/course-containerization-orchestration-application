"""Regression tests: deliberately broken copies must fail validation."""

from pathlib import Path
import shutil
import tempfile
import unittest

from validate_course import validate


class CourseChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "course"
        shutil.copytree(
            Path(__file__).resolve().parents[2], self.root,
            ignore=shutil.ignore_patterns(".git", ".site-src", "site", "__pycache__", ".venv"),
        )

    def mutate(self, path: str, old: str, new: str) -> None:
        target = self.root / path
        text = target.read_text(encoding="utf-8")
        self.assertIn(old, text)
        target.write_text(text.replace(old, new, 1), encoding="utf-8")

    def test_valid_course(self) -> None:
        self.assertEqual(validate(self.root), [])

    def test_missing_link(self) -> None:
        self.mutate("README.md", "syllabus/start.md", "syllabus/missing.md")
        self.assertTrue(any("missing local link" in message for message in validate(self.root)))

    def test_bad_frontmatter(self) -> None:
        self.mutate("syllabus/course.md", 'title: "Контейнеризация', 'title: [ "Контейнеризация')
        self.assertTrue(any("invalid metadata" in message for message in validate(self.root)))

    def test_score_mismatch(self) -> None:
        self.mutate("labs/05-kubernetes.md", "max_score: 15", "max_score: 20")
        self.assertTrue(any("labs/05-" in message for message in validate(self.root)))

    def test_criteria_mismatch(self) -> None:
        self.mutate("labs/05-kubernetes.md", "| 1. Подготовка образа | 4 |", "| 1. Подготовка образа | 3 |")
        self.assertTrue(any("criteria sum" in message for message in validate(self.root)))

    def test_summary_mismatch(self) -> None:
        self.mutate("assessment/README.md", "| 7,5 | 15 |", "| 7,5 | 20 |")
        self.assertTrue(any("assessment table" in message for message in validate(self.root)))

    def test_bad_navigation(self) -> None:
        self.mutate(".github/docs/mkdocs.yml", "materials/faq.md", "materials/absent.md")
        self.assertTrue(any("nav:" in message for message in validate(self.root)))

    def test_unfinished_student_page(self) -> None:
        self.mutate("materials/faq.md", "# Частые вопросы", "# Частые вопросы\n\nTODO")
        self.assertTrue(any("unfinished" in message for message in validate(self.root)))

    def test_publication_leak(self) -> None:
        leak = self.root / ".site-src/docs/.github/private.md"
        leak.parent.mkdir(parents=True)
        leak.write_text("must not be published", encoding="utf-8")
        self.assertTrue(any("staging:" in message for message in validate(self.root, staged=True)))

    def test_old_first_lab_policy(self) -> None:
        self.mutate("labs/01-docker.md", "## Формат сдачи", "## Формат сдачи\n\nРепозиторий не нужен.")
        self.assertTrue(any("obsolete" in message for message in validate(self.root)))

    def test_missing_first_lab_sources(self) -> None:
        self.mutate("labs/01-docker.md", "solutions/reports/lab-1/", "local-only/")
        self.assertTrue(any("lab-1:" in message for message in validate(self.root)))

    def test_missing_latex_source(self) -> None:
        (self.root / "materials/report-latex/Paper.tex").unlink()
        self.assertTrue(any("LaTeX template:" in message for message in validate(self.root)))

    def test_extra_template_asset(self) -> None:
        (self.root / "materials/report-latex/unnecessary.zip").write_bytes(b"test")
        self.assertTrue(any("LaTeX template:" in message for message in validate(self.root)))


if __name__ == "__main__":
    unittest.main()
