"""
Author Scorer Module
Evaluates author prestige using Semantic Scholar API.
Metrics include h-index, citation count, and paper count.
"""

import requests
from requests.adapters import HTTPAdapter, Retry
from typing import Optional, List, Dict
import time
from loguru import logger
import json
from pathlib import Path


class AuthorScorer:
    def __init__(
        self,
        cache_file: str = "author_cache.json",
        default_score: float = 50.0,
        prestigious_threshold: float = 80.0
    ):
        """
        Initialize the author scorer.
        
        Args:
            cache_file: Path to cache file for storing author scores
            default_score: Default score for unknown authors (0-100)
            prestigious_threshold: Threshold for considering an author prestigious
        """
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self.default_score = default_score
        self.prestigious_threshold = prestigious_threshold
        self.cache_file = cache_file
        self.cache: Dict[str, Dict] = {}
        
        # Setup session with retry strategy
        self.session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        
        # Load cache
        self.load_cache()
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms between requests
    
    def load_cache(self):
        """Load cached author data."""
        cache_path = Path(self.cache_file)
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                logger.info(f"Loaded {len(self.cache)} cached author scores")
            except Exception as e:
                logger.warning(f"Failed to load author cache: {e}")
    
    def save_cache(self):
        """Save author cache to file."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved author cache with {len(self.cache)} entries")
        except Exception as e:
            logger.warning(f"Failed to save author cache: {e}")
    
    def rate_limit(self):
        """Enforce rate limiting."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()
    
    def search_author(self, author_name: str) -> Optional[str]:
        """
        Search for an author and return their Semantic Scholar ID.
        
        Args:
            author_name: Author's name
            
        Returns:
            Author ID or None if not found
        """
        try:
            self.rate_limit()
            url = f"{self.base_url}/author/search"
            params = {
                'query': author_name,
                'limit': 1,
                'fields': 'authorId,name,hIndex,citationCount,paperCount'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data') and len(data['data']) > 0:
                    return data['data'][0]
            elif response.status_code == 429:
                logger.warning("Rate limited by Semantic Scholar API")
                time.sleep(5)
                return None
            else:
                logger.debug(f"Author search failed for '{author_name}': {response.status_code}")
                return None
        except Exception as e:
            logger.debug(f"Error searching for author '{author_name}': {e}")
            return None
    
    def calculate_score(self, author_data: Dict) -> float:
        """
        Calculate author score based on metrics.
        
        Scoring formula:
        - h-index: 0-100 scale (h=50+ gets 100 points)
        - Citation count: logarithmic scale
        - Paper count: logarithmic scale
        
        Final score = 0.5 * h_score + 0.3 * citation_score + 0.2 * paper_score
        
        Args:
            author_data: Author data from Semantic Scholar
            
        Returns:
            Score between 0-100
        """
        try:
            h_index = author_data.get('hIndex', 0)
            citation_count = author_data.get('citationCount', 0)
            paper_count = author_data.get('paperCount', 0)
            
            # H-index score (0-100)
            # h=0 -> 0, h=10 -> 20, h=25 -> 50, h=50+ -> 100
            h_score = min((h_index / 50.0) * 100, 100)
            
            # Citation score (logarithmic, 0-100)
            # 0 citations -> 0, 100 -> 40, 1000 -> 60, 10000 -> 80, 100000+ -> 100
            import math
            if citation_count > 0:
                citation_score = min((math.log10(citation_count) / 5.0) * 100, 100)
            else:
                citation_score = 0
            
            # Paper count score (logarithmic, 0-100)
            # 0 papers -> 0, 10 -> 40, 50 -> 68, 100 -> 80, 1000+ -> 100
            if paper_count > 0:
                paper_score = min((math.log10(paper_count) / 3.0) * 100, 100)
            else:
                paper_score = 0
            
            # Weighted combination
            final_score = (
                0.5 * h_score +
                0.3 * citation_score +
                0.2 * paper_score
            )
            
            logger.debug(
                f"Author score calculation: h={h_index} ({h_score:.1f}), "
                f"cites={citation_count} ({citation_score:.1f}), "
                f"papers={paper_count} ({paper_score:.1f}) -> {final_score:.1f}"
            )
            
            return final_score
            
        except Exception as e:
            logger.debug(f"Error calculating author score: {e}")
            return self.default_score
    
    def get_score(self, author_name: str) -> float:
        """
        Get the prestige score for an author.
        
        Args:
            author_name: Author's name
            
        Returns:
            Score between 0-100
        """
        if not author_name:
            return self.default_score
        
        # Check cache first
        if author_name in self.cache:
            cached_data = self.cache[author_name]
            # Check if cache is stale (older than 30 days)
            cache_time = cached_data.get('cached_at', 0)
            if time.time() - cache_time < 30 * 24 * 3600:
                return cached_data.get('score', self.default_score)
        
        # Search for author
        author_data = self.search_author(author_name)
        
        if author_data:
            score = self.calculate_score(author_data)
            
            # Cache the result
            self.cache[author_name] = {
                'score': score,
                'data': author_data,
                'cached_at': time.time()
            }
            
            return score
        else:
            # Unknown author - use default and cache it
            self.cache[author_name] = {
                'score': self.default_score,
                'data': None,
                'cached_at': time.time()
            }
            return self.default_score
    
    def get_max_score(self, authors: List[str]) -> float:
        """
        Get the maximum score among a list of authors.
        Typically focuses on first and last authors (most important in academic papers).
        
        Args:
            authors: List of author names
            
        Returns:
            Maximum score
        """
        if not authors:
            return self.default_score
        
        # For performance, only check first author, last author, and middle one if many authors
        if len(authors) <= 3:
            authors_to_check = authors
        else:
            # Check first, last, and one middle author
            authors_to_check = [authors[0], authors[-1]]
        
        scores = []
        for author in authors_to_check:
            score = self.get_score(author)
            scores.append(score)
        
        return max(scores) if scores else self.default_score
    
    def is_prestigious(self, author_name: str) -> bool:
        """
        Check if an author is considered highly prestigious.
        
        Args:
            author_name: Author's name
            
        Returns:
            True if score >= prestigious_threshold
        """
        return self.get_score(author_name) >= self.prestigious_threshold
    
    def get_prestigious_authors(self, authors: List[str]) -> List[str]:
        """
        Filter out prestigious authors from a list.
        
        Args:
            authors: List of author names
            
        Returns:
            List of prestigious authors
        """
        prestigious = []
        for author in authors:
            if self.is_prestigious(author):
                prestigious.append(author)
        return prestigious


# Global instance
_global_scorer = None


def get_author_scorer() -> AuthorScorer:
    """Get the global author scorer instance."""
    global _global_scorer
    if _global_scorer is None:
        _global_scorer = AuthorScorer()
    return _global_scorer


