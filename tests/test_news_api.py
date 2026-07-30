import unittest

from src.news_api import _ArticleBodyParser, _parse_article


class NewsApiParsingTests(unittest.TestCase):
    def test_parses_article_and_decodes_source(self) -> None:
        article = _parse_article(
            {
                "uuid": "article-id",
                "title": "Заголовок",
                "description": None,
                "snippet": "Короткое описание",
                "url": "https://example.com/article",
                "image_url": "https://cdn.example.com/poster.jpg",
                "source": "example.com%20%20",
                "published_at": "2026-07-30T10:00:00Z",
            }
        )

        self.assertIsNotNone(article)
        self.assertEqual(article.description, "Короткое описание")
        self.assertEqual(article.source, "example.com")

    def test_extracts_text_from_article_body(self) -> None:
        parser = _ArticleBodyParser()
        parser.feed(
            '<div itemprop="articleBody"><p>Первый <a href="#">абзац</a>.</p>'
            "<script>ignore()</script><p>Второй абзац.</p></div>"
        )

        self.assertEqual(parser.text, "Первый абзац. Второй абзац.")

    def test_rejects_unsafe_article_url_and_ignores_unsafe_image(self) -> None:
        self.assertIsNone(
            _parse_article(
                {
                    "uuid": "bad",
                    "title": "Заголовок",
                    "url": "javascript:alert(1)",
                }
            )
        )
        article = _parse_article(
            {
                "uuid": "safe",
                "title": "Заголовок",
                "url": "https://example.com/article",
                "image_url": "https://user:password@example.com/poster.jpg",
            }
        )
        self.assertIsNotNone(article)
        self.assertIsNone(article.image_url)


if __name__ == "__main__":
    unittest.main()
