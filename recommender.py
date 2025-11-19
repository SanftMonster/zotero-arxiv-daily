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
    use_prestige: bool = True
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
    
    # Calculate final scores with prestige boost
    logger.info("Calculating prestige scores for papers...")
    for idx, (rel_score, paper) in enumerate(tqdm(zip(relevance_scores, candidate), total=len(candidate), desc="Scoring papers")):
        # Store relevance score
        paper.relevance_score = rel_score.item()
        
        if use_prestige:
            # Get prestige scores (0-100)
            institution_score = paper.institution_prestige_score
            author_score = paper.author_prestige_score
            
            # Store prestige scores
            paper.institution_score = institution_score
            paper.author_score = author_score
            
            # Calculate boost factors (0.5 ~ 1.5)
            # score=50 (average) -> boost=1.0
            # score=100 (excellent) -> boost=1.5
            # score=0 (poor) -> boost=0.5
            institution_boost = 0.5 + (institution_score / 100.0)
            author_boost = 0.5 + (author_score / 100.0)
            
            # Apply multiplicative boost
            final_score = paper.relevance_score * institution_boost * author_boost
            
            logger.debug(
                f"{paper.arxiv_id}: relevance={paper.relevance_score:.2f}, "
                f"inst={institution_score:.1f} (boost={institution_boost:.2f}), "
                f"author={author_score:.1f} (boost={author_boost:.2f}), "
                f"final={final_score:.2f}"
            )
        else:
            # No prestige boost
            final_score = paper.relevance_score
            paper.institution_score = 50.0
            paper.author_score = 50.0
        
        paper.score = final_score
    
    # Sort by final score
    candidate = sorted(candidate, key=lambda x: x.score, reverse=True)
    
    logger.info(f"Reranking complete. Top score: {candidate[0].score:.2f}, Bottom score: {candidate[-1].score:.2f}")
    
    return candidate