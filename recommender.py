import numpy as np
from sentence_transformers import SentenceTransformer
from paper import ArxivPaper
from datetime import datetime
from loguru import logger
from tqdm import tqdm

def rerank_paper(
    candidate: list[ArxivPaper],
    corpus: list[dict],
    model: str = 'avsolatorio/GIST-small-Embedding-v0',
    use_prestige: bool = True,
    max_paper_num: int = 100,
    prestige_weight: float = 1.0,
) -> list[ArxivPaper]:
    """
    Rerank papers based on relevance and prestige (institutions and authors).
    
    Scoring formula:
    - relevance_score: Weighted similarity with Zotero corpus (0-10 scale)
    - institution_boost: 0.5 ~ 1.5 based on institution prestige (0-100)
    - author_boost: 0.5 ~ 1.5 based on author prestige (0-100)
    - final_score = relevance_score × institution_boost × author_boost
    
    Args:
        candidate: List of candidate papers
        corpus: Zotero corpus
        model: Sentence transformer model name
        use_prestige: Whether to use institution and author prestige
        max_paper_num: Maximum number of papers to return, used for optimization
        
    Returns:
        Sorted list of papers
    """
    encoder = SentenceTransformer(model)
    
    # Sort corpus by date, from newest to oldest
    corpus = sorted(corpus, key=lambda x: datetime.strptime(x['data']['dateAdded'], '%Y-%m-%dT%H:%M:%SZ'), reverse=True)
    time_decay_weight = 1 / (1 + np.log10(np.arange(len(corpus)) + 1))
    time_decay_weight = time_decay_weight / time_decay_weight.sum()
    
    # Encode features
    corpus_feature = encoder.encode([paper['data']['abstractNote'] for paper in corpus])
    candidate_feature = encoder.encode([paper.summary for paper in candidate])
    
    # Calculate similarity
    sim = encoder.similarity(candidate_feature, corpus_feature)  # [n_candidate, n_corpus]
    relevance_scores = (sim * time_decay_weight).sum(axis=1) * 10  # [n_candidate]
    
    # Store relevance score for all papers
    for idx, paper in enumerate(candidate):
        paper.relevance_score = relevance_scores[idx].item()
    
    # Calculate final scores with prestige boost
    if use_prestige:
        prestige_weight = max(0.0, min(1.0, prestige_weight))
        # Optimization: Only calculate prestige for top candidates
        # Sort by relevance first
        candidate.sort(key=lambda x: x.relevance_score, reverse=True)
        
        # Determine how many papers to process for prestige
        # We process at least max_paper_num * 3 papers to ensure we don't miss high-prestige papers
        process_limit = min(len(candidate), max(max_paper_num * 3, 50))
        top_candidates = candidate[:process_limit]
        rest_candidates = candidate[process_limit:]
        
        logger.info(f"Calculating prestige scores for top {len(top_candidates)} papers (Optimization)...")
        for paper in tqdm(top_candidates, desc="Scoring papers"):
            # Get prestige scores (0-100)
            institution_score = paper.institution_prestige_score
            author_score = paper.author_prestige_score
            
            # Store prestige scores
            paper.institution_score = institution_score
            paper.author_score = author_score
            
            # Calculate boost factors (0.5 ~ 1.5)
            institution_boost = 0.5 + (institution_score / 100.0)
            author_boost = 0.5 + (author_score / 100.0)
            
            combined_boost = institution_boost * author_boost
            weighted_boost = 1 + prestige_weight * (combined_boost - 1)
            # Apply weighted boost to keep relevance dominant when prestige_weight < 1
            final_score = paper.relevance_score * max(weighted_boost, 0.0)
            paper.score = final_score
            
            logger.debug(
                f"{paper.arxiv_id}: relevance={paper.relevance_score:.2f}, "
                f"inst={institution_score:.1f} (boost={institution_boost:.2f}), "
                f"author={author_score:.1f} (boost={author_boost:.2f}), "
                f"final={final_score:.2f}"
            )
            
        # For the rest of the papers, assign default scores
        for paper in rest_candidates:
            paper.institution_score = 50.0
            paper.author_score = 50.0
            paper.score = paper.relevance_score  # No boost
            
    else:
        # No prestige boost
        for paper in candidate:
            final_score = paper.relevance_score
            paper.institution_score = 50.0
            paper.author_score = 50.0
            paper.score = final_score
    
    # Sort by final score
    candidate = sorted(candidate, key=lambda x: x.score, reverse=True)
    
    logger.info(f"Reranking complete. Top score: {candidate[0].score:.2f}, Bottom score: {candidate[-1].score:.2f}")
    
    return candidate