#!/usr/bin/env python3
"""
RAG Retrieval Test Suite for eMMC 5.1 Specification
Tests the quality of retrieval after TOC-based chunking improvements.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.qdrant_client import QdrantVectorStore
from typing import List, Dict, Tuple


class RAGTester:
    def __init__(self):
        self.vector_store = QdrantVectorStore()
        self.test_results = []

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search and return results with metadata."""
        # QdrantVectorStore.search() already returns formatted dictionaries
        results = self.vector_store.search(query, top_k=top_k)
        return results

    def evaluate_question(
        self,
        question: str,
        expected_section: str = None,
        expected_page: int = None,
        expected_subtitle: str = None,
        check_no_malformed: bool = True,
        check_no_inferred: bool = True,
    ) -> Tuple[int, str]:
        """
        Evaluate a single test question.
        Returns (score, report)
        """
        print(f"\n{'='*80}")
        print(f"Question: {question}")
        print(f"{'='*80}")

        results = self.search(question, top_k=5)

        if not results:
            print("❌ No results returned!")
            return 0, "No results returned"

        # Scoring
        scores = {
            'retrieval_accuracy': 0,
            'section_path_quality': 0,
            'subtitle_accuracy': 0,
            'citation_accuracy': 0,
            'content_completeness': 0,
        }

        report_lines = []

        # Check top result
        top_result = results[0]
        print(f"\n🥇 Top Result:")
        print(f"  Section: {top_result['section_path']}")
        print(f"  Title: {top_result['section_title']}")
        print(f"  Pages: {top_result['page_numbers']}")
        print(f"  Score: {top_result['score']:.4f}")
        print(f"  Preview: {top_result['text'][:200]}...")

        # Criteria 1: Retrieval Accuracy
        if expected_section:
            if expected_section.lower() in top_result['section_path'].lower():
                scores['retrieval_accuracy'] = 5
                print(f"  ✅ Expected section found: {expected_section}")
            else:
                scores['retrieval_accuracy'] = 2
                print(f"  ⚠️  Expected section not in top result: {expected_section}")
                print(f"     Got: {top_result['section_path']}")
        else:
            # Manual judgment needed
            scores['retrieval_accuracy'] = 4
            print(f"  ℹ️  Manual review needed for relevance")

        # Criteria 2: Section Path Quality
        path_issues = []
        if '[Inferred]' in top_result['section_path']:
            path_issues.append("Contains [Inferred]")
        if '.part' in top_result['section_path'].lower():
            path_issues.append("Contains .partX suffix")
        if 'Page ' in top_result['section_path'] and 'Page ' not in top_result['section_title']:
            path_issues.append("Contains 'Page XXX' in path")

        if not path_issues:
            scores['section_path_quality'] = 5
            print(f"  ✅ Section path quality: Excellent")
        else:
            scores['section_path_quality'] = 2
            print(f"  ⚠️  Section path issues: {', '.join(path_issues)}")

        # Criteria 3: Subtitle Accuracy
        subtitle_in_path = ' - ' in top_result['section_path']
        if subtitle_in_path:
            subtitle = top_result['section_path'].split(' - ')[-1]
            # Check if subtitle is meaningful
            if 'Table ' in subtitle or 'Figure ' in subtitle:
                scores['subtitle_accuracy'] = 2
                print(f"  ⚠️  Subtitle is table/figure caption: {subtitle}")
            elif expected_subtitle and expected_subtitle.lower() in subtitle.lower():
                scores['subtitle_accuracy'] = 5
                print(f"  ✅ Expected subtitle found: {subtitle}")
            else:
                # Check if subtitle appears in content
                if subtitle in top_result['text'][:500]:
                    scores['subtitle_accuracy'] = 4
                    print(f"  ✅ Subtitle appears in content: {subtitle}")
                else:
                    scores['subtitle_accuracy'] = 2
                    print(f"  ⚠️  Subtitle not in first 500 chars: {subtitle}")
        else:
            scores['subtitle_accuracy'] = 3
            print(f"  ℹ️  No subtitle detected")

        # Criteria 4: Citation Accuracy
        if expected_page:
            if expected_page in top_result['page_numbers']:
                scores['citation_accuracy'] = 5
                print(f"  ✅ Expected page found: {expected_page}")
            elif any(abs(p - expected_page) <= 2 for p in top_result['page_numbers']):
                scores['citation_accuracy'] = 4
                print(f"  ✅ Close to expected page: {expected_page} (got {top_result['page_numbers']})")
            else:
                scores['citation_accuracy'] = 2
                print(f"  ⚠️  Page mismatch: expected {expected_page}, got {top_result['page_numbers']}")
        else:
            scores['citation_accuracy'] = 4
            print(f"  ℹ️  Page numbers: {top_result['page_numbers']}")

        # Criteria 5: Content Completeness (check if answer keywords are in content)
        content_lower = top_result['text'].lower()
        keyword_count = sum(1 for word in question.lower().split() if len(word) > 3 and word in content_lower)
        if keyword_count >= 3:
            scores['content_completeness'] = 5
            print(f"  ✅ Content contains {keyword_count} query keywords")
        elif keyword_count >= 2:
            scores['content_completeness'] = 4
            print(f"  ✅ Content contains {keyword_count} query keywords")
        else:
            scores['content_completeness'] = 3
            print(f"  ⚠️  Content contains only {keyword_count} query keywords")

        # Show other top results briefly
        print(f"\n  Other Top Results:")
        for i, result in enumerate(results[1:4], 2):
            print(f"  {i}. {result['section_path'][:80]}...")

        total_score = sum(scores.values())
        print(f"\n  📊 Scores:")
        for criterion, score in scores.items():
            print(f"     {criterion}: {score}/5")
        print(f"  Total: {total_score}/25")

        return total_score, "\n".join(report_lines)

    def run_all_tests(self):
        """Run all test questions."""
        print("\n" + "="*80)
        print("RAG RETRIEVAL TEST SUITE - eMMC 5.1 Specification")
        print("="*80)

        test_cases = [
            # Category 1: Specific Technical Details
            {
                'category': 'Specific Technical Details',
                'question': 'What is HS400 timing mode and how do you select it?',
                'expected_section': '6.6.2.3',
                'expected_page': 46,
                'expected_subtitle': 'HS400',
            },
            {
                'category': 'Specific Technical Details',
                'question': 'What is the TAAC field in the CSD register?',
                'expected_section': '7.3.3',
                'expected_page': 165,
                'expected_subtitle': 'TAAC',
            },
            {
                'category': 'Specific Technical Details',
                'question': 'How does HS200 mode work in eMMC?',
                'expected_section': '6.6.2',
                'expected_page': None,
                'expected_subtitle': 'HS200',
            },

            # Category 2: Feature Descriptions
            {
                'category': 'Feature Descriptions',
                'question': 'What is Command Queuing and how does it work?',
                'expected_section': '6.6.39',
                'expected_page': 115,
                'expected_subtitle': None,
            },
            {
                'category': 'Feature Descriptions',
                'question': 'What is Production State Awareness in eMMC?',
                'expected_section': '6.6.17',
                'expected_page': 69,
                'expected_subtitle': None,
            },
            {
                'category': 'Feature Descriptions',
                'question': 'How does Replay Protected Memory Block work?',
                'expected_section': '6.6.22',
                'expected_page': 78,
                'expected_subtitle': None,
            },

            # Category 3: Register Specifications
            {
                'category': 'Register Specifications',
                'question': 'What is the OCR register and what information does it contain?',
                'expected_section': '7.1',
                'expected_page': 161,
                'expected_subtitle': None,
            },
            {
                'category': 'Register Specifications',
                'question': 'What fields are in the EXT_CSD register?',
                'expected_section': '7.4',
                'expected_page': None,
                'expected_subtitle': None,
            },

            # Category 4: General Concepts
            {
                'category': 'General Concepts',
                'question': 'What boot modes does eMMC support?',
                'expected_section': '6.3',
                'expected_page': None,
                'expected_subtitle': None,
            },
            {
                'category': 'General Concepts',
                'question': 'How does eMMC handle power management and sleep modes?',
                'expected_section': '6.6.21',
                'expected_page': None,
                'expected_subtitle': None,
            },

            # Category 5: Edge Cases
            {
                'category': 'Edge Cases',
                'question': 'What are all the different speed modes supported by eMMC?',
                'expected_section': None,  # Multiple sections
                'expected_page': None,
                'expected_subtitle': None,
            },
            {
                'category': 'Edge Cases',
                'question': 'What are the CSD register field definitions?',
                'expected_section': '7.3',
                'expected_page': None,
                'expected_subtitle': None,
            },
        ]

        total_score = 0
        max_score = len(test_cases) * 25
        category_scores = {}

        for i, test_case in enumerate(test_cases, 1):
            category = test_case['category']
            print(f"\n{'='*80}")
            print(f"TEST {i}/{len(test_cases)} - Category: {category}")

            score, report = self.evaluate_question(
                question=test_case['question'],
                expected_section=test_case.get('expected_section'),
                expected_page=test_case.get('expected_page'),
                expected_subtitle=test_case.get('expected_subtitle'),
            )

            total_score += score

            if category not in category_scores:
                category_scores[category] = {'score': 0, 'count': 0}
            category_scores[category]['score'] += score
            category_scores[category]['count'] += 1

            self.test_results.append({
                'question': test_case['question'],
                'category': category,
                'score': score,
                'max_score': 25,
            })

        # Final Report
        print("\n" + "="*80)
        print("FINAL TEST REPORT")
        print("="*80)

        percentage = (total_score / max_score) * 100

        print(f"\nOverall Score: {total_score}/{max_score} ({percentage:.1f}%)")

        if percentage >= 90:
            grade = "EXCELLENT ⭐⭐⭐ - Production Ready"
        elif percentage >= 75:
            grade = "GOOD ⭐⭐ - Minor improvements needed"
        elif percentage >= 60:
            grade = "ACCEPTABLE ⭐ - Some refinement required"
        else:
            grade = "NEEDS WORK ⚠️ - Significant issues remain"

        print(f"Grade: {grade}")

        print(f"\nCategory Breakdown:")
        for category, data in category_scores.items():
            cat_percentage = (data['score'] / (data['count'] * 25)) * 100
            print(f"  {category}: {data['score']}/{data['count']*25} ({cat_percentage:.1f}%)")

        print(f"\nDetailed Results:")
        for i, result in enumerate(self.test_results, 1):
            status = "✅" if result['score'] >= 20 else "⚠️" if result['score'] >= 15 else "❌"
            print(f"  {status} Q{i}: {result['score']}/25 - {result['question'][:60]}...")

        return total_score, max_score


def main():
    tester = RAGTester()
    total_score, max_score = tester.run_all_tests()

    print("\n" + "="*80)
    print("Test Complete!")
    print("="*80)


if __name__ == '__main__':
    main()
