"""Semantic citation verification: claim extraction and verification logic."""

from lectern.entailment import NLIChecker, extract_claims, verify_citations


def test_extract_claims_simple() -> None:
    answer = "Revenue grew 14%. [slide:1:notes] Costs dropped. [slide:3:notes]"
    claims = extract_claims(answer)
    assert len(claims) == 2
    assert claims[0] == ("Revenue grew 14%", "slide:1:notes")
    assert claims[1] == ("Costs dropped", "slide:3:notes")


def test_extract_claims_no_markers() -> None:
    assert extract_claims("Just plain text, no citations.") == []


def test_extract_claims_trailing_marker() -> None:
    claims = extract_claims("The cafe grew. [slide:2:body]")
    assert len(claims) == 1
    assert claims[0][1] == "slide:2:body"


class FakeNLI:
    """Deterministic NLI for tests: entails if claim words appear in evidence."""

    def check(self, claim: str, evidence: str) -> str:
        words = set(claim.lower().split())
        ev_words = set(evidence.lower().split())
        return "entailment" if len(words & ev_words) >= len(words) / 2 else "neutral"

    def check_batch(self, pairs: list[tuple[str, str]]) -> list[str]:
        return [self.check(c, e) for c, e in pairs]


def test_verify_keeps_entailed_citations() -> None:
    answer = "Revenue grew. [slide:1:notes] Weather nice. [slide:2:body]"
    blocks = {"slide:1:notes": "Revenue grew 14% in Q3", "slide:2:body": "Sales by region"}
    cleaned, kept = verify_citations(FakeNLI(), answer, blocks)  # type: ignore[arg-type]
    assert "slide:1:notes" in kept
    assert "slide:2:body" not in kept  # "Weather nice" not in "Sales by region"


def test_verify_no_blocks_passthrough() -> None:
    answer = "Just text [slide:1:notes]"
    cleaned, kept = verify_citations(FakeNLI(), answer, {})  # type: ignore[arg-type]
    assert cleaned == answer  # no matching blocks, passthrough


def test_nli_checker_available_reflects_import() -> None:
    result = NLIChecker.available()
    assert isinstance(result, bool)
