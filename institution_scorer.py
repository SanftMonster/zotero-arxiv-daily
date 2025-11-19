"""
Institution Scorer Module
Evaluates institution prestige using a hybrid approach:
- Static dictionary for known institutions
- Cache for previously evaluated institutions
- Default score for unknown institutions
"""

import json
from typing import Optional, List
from pathlib import Path
from loguru import logger
import re


class InstitutionScorer:
    def __init__(self, scores_file: str = "institution_scores.json", default_score: float = 50.0):
        """
        Initialize the institution scorer.
        
        Args:
            scores_file: Path to JSON file containing institution scores
            default_score: Default score for unknown institutions (0-100)
        """
        self.default_score = default_score
        self.static_scores = {}
        self.cache = {}
        self.prestigious_threshold = 90  # Institutions above this are considered highly prestigious
        
        # Load static scores
        scores_path = Path(scores_file)
        if scores_path.exists():
            with open(scores_path, 'r', encoding='utf-8') as f:
                self.static_scores = json.load(f)
            logger.info(f"Loaded {len(self.static_scores)} institution scores from {scores_file}")
        else:
            logger.warning(f"Institution scores file not found: {scores_file}. Using default scores only.")
    
    def normalize_institution_name(self, name: str) -> str:
        """
        Normalize institution name for better matching.
        
        Examples:
            "Stanford Univ." -> "Stanford University"
            "MIT CSAIL" -> "MIT"
        """
        if not name:
            return ""
        
        # Convert to title case and strip
        name = name.strip()
        
        # Common abbreviations
        replacements = {
            r'\bUniv\b\.?': 'University',
            r'\bColl\b\.?': 'College',
            r'\bInst\b\.?': 'Institute',
            r'\bTech\b\.?': 'Technology',
            r'\bDept\b\.?': 'Department',
        }
        
        for pattern, replacement in replacements.items():
            name = re.sub(pattern, replacement, name, flags=re.IGNORECASE)
        
        # Remove department information (keep only top-level institution)
        # e.g., "Department of CS, MIT" -> "MIT"
        if ',' in name:
            parts = [p.strip() for p in name.split(',')]
            # Usually the institution is the last part
            name = parts[-1]
        
        return name.strip()
    
    def fuzzy_match(self, query: str) -> Optional[tuple[str, float]]:
        """
        Try to find a fuzzy match in static scores.
        
        Returns:
            Tuple of (matched_institution, score) or None
        """
        query_lower = query.lower()
        
        # Exact match (case insensitive)
        for inst, score in self.static_scores.items():
            if inst.lower() == query_lower:
                return (inst, score)
        
        # Partial match (query contains institution name or vice versa)
        for inst, score in self.static_scores.items():
            inst_lower = inst.lower()
            if inst_lower in query_lower or query_lower in inst_lower:
                # Prefer longer matches (more specific)
                if len(inst_lower) > 3:  # Avoid matching very short names
                    return (inst, score)
        
        return None
    
    def get_score(self, institution: str) -> float:
        """
        Get the prestige score for an institution.
        
        Args:
            institution: Institution name
            
        Returns:
            Score between 0-100
        """
        if not institution:
            return self.default_score
        
        # Normalize the name
        normalized = self.normalize_institution_name(institution)
        
        # Check cache first
        if normalized in self.cache:
            return self.cache[normalized]
        
        # Check static scores (exact match)
        if normalized in self.static_scores:
            score = self.static_scores[normalized]
            self.cache[normalized] = score
            return score
        
        # Try fuzzy matching
        fuzzy_result = self.fuzzy_match(normalized)
        if fuzzy_result:
            matched_inst, score = fuzzy_result
            logger.debug(f"Fuzzy matched '{institution}' to '{matched_inst}' with score {score}")
            self.cache[normalized] = score
            return score
        
        # Unknown institution - use default
        logger.debug(f"Unknown institution: '{institution}', using default score {self.default_score}")
        self.cache[normalized] = self.default_score
        return self.default_score
    
    def get_max_score(self, institutions: List[str]) -> float:
        """
        Get the maximum score among a list of institutions.
        
        Args:
            institutions: List of institution names
            
        Returns:
            Maximum score
        """
        if not institutions:
            return self.default_score
        
        scores = [self.get_score(inst) for inst in institutions]
        return max(scores)
    
    def is_prestigious(self, institution: str) -> bool:
        """
        Check if an institution is considered highly prestigious.
        
        Args:
            institution: Institution name
            
        Returns:
            True if score >= prestigious_threshold
        """
        return self.get_score(institution) >= self.prestigious_threshold
    
    def get_prestigious_institutions(self, institutions: List[str]) -> List[str]:
        """
        Filter out prestigious institutions from a list.
        
        Args:
            institutions: List of institution names
            
        Returns:
            List of prestigious institutions
        """
        return [inst for inst in institutions if self.is_prestigious(inst)]
    
    def save_cache(self, cache_file: str = "institution_cache.json"):
        """Save the cache to a file for future use."""
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved institution cache to {cache_file}")
    
    def load_cache(self, cache_file: str = "institution_cache.json"):
        """Load cache from a file."""
        cache_path = Path(cache_file)
        if cache_path.exists():
            with open(cache_path, 'r', encoding='utf-8') as f:
                self.cache = json.load(f)
            logger.info(f"Loaded {len(self.cache)} cached institution scores")


# Global instance
_global_scorer = None


def get_institution_scorer() -> InstitutionScorer:
    """Get the global institution scorer instance."""
    global _global_scorer
    if _global_scorer is None:
        _global_scorer = InstitutionScorer()
        # Try to load cache
        try:
            _global_scorer.load_cache()
        except:
            pass
    return _global_scorer


