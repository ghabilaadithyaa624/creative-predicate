"""
Knowledge graph representing market entities, correlations, and relationships.
"""
from typing import Dict, List, Set, Any


class MarketKnowledgeGraph:
    """
    Lightweight knowledge graph tracking entity relationships:
    - Teams -> League
    - Assets -> Macro Factors (e.g. BTC -> Interest Rates, Halving)
    - Correlated Markets
    """

    def __init__(self):
        self.entities: Dict[str, Dict[str, Any]] = {}
        self.relationships: List[Dict[str, Any]] = []

    def add_entity(self, entity_id: str, entity_type: str, properties: Dict[str, Any] = None):
        self.entities[entity_id] = {
            "type": entity_type,
            "properties": properties or {},
        }

    def add_relation(self, source: str, relation: str, target: str, weight: float = 1.0):
        self.relationships.append({
            "source": source,
            "relation": relation,
            "target": target,
            "weight": weight,
        })

    def get_related_entities(self, entity_id: str, relation_type: str = None) -> List[str]:
        results = []
        for rel in self.relationships:
            if rel["source"] == entity_id:
                if relation_type is None or rel["relation"] == relation_type:
                    results.append(rel["target"])
            elif rel["target"] == entity_id:
                if relation_type is None or rel["relation"] == relation_type:
                    results.append(rel["source"])
        return list(set(results))
