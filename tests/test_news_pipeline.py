import unittest

from backend.ingestion.news.chunker import build_chunks
from backend.ingestion.news.extractor import extract_from_text
from backend.ingestion.news.pipeline import process_news_article
from backend.ingestion.news.sentiment import analyze_sentiment
from backend.ingestion.news.topics import detect_topics


class NewsPipelineTests(unittest.TestCase):
    def test_topic_detection_earnings(self):
        topics = detect_topics("Company beat earnings expectations with strong revenue growth")
        self.assertIn("earnings", topics)

    def test_sentiment_positive(self):
        result = analyze_sentiment("Shares surge on strong growth and record high profits")
        self.assertEqual(result.label, "positive")
        self.assertGreater(result.score, 0)

    def test_sentiment_negative(self):
        result = analyze_sentiment("Stock fall after weak earnings and downgrade risk")
        self.assertEqual(result.label, "negative")

    def test_chunk_metadata_fields(self):
        article = extract_from_text(
            "Acme Corp reported revenue growth in Q1.\n\nMargins improved across segments.",
            title="Acme Q1 Update",
            publisher="Example News",
            publication_date="2024-03-15",
        )
        sentiment = analyze_sentiment(article.body)
        topics = detect_topics(article.body, industry="Manufacturing")
        chunks = build_chunks(
            article,
            doc_id="doc-1",
            industry="Manufacturing",
            topics=topics,
            sentiment=sentiment,
        )
        self.assertGreater(len(chunks), 0)
        self.assertEqual(chunks[0].publisher, "Example News")
        self.assertEqual(chunks[0].publication_date, "2024-03-15")
        self.assertEqual(chunks[0].industry, "Manufacturing")
        self.assertIn("Sentiment:", chunks[0].text)

    def test_process_inline_news(self):
        result = process_news_article(
            company="Acme Corp",
            sector="Manufacturing",
            raw_ref="inline_news",
            processed_file="test.json",
            text="Export volumes rose while imports declined amid trade policy changes.",
            url="",
        )
        self.assertGreater(len(result.chunks), 0)
        self.assertEqual(result.chunks[0]["publisher"], "social")
        self.assertEqual(result.chunks[0]["industry"], "Manufacturing")
        self.assertIn("topic", result.chunks[0])
        self.assertIn("sentiment", result.chunks[0])
        self.assertIn("publication_date", result.chunks[0])


if __name__ == "__main__":
    unittest.main()
