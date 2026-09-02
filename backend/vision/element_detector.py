"""
Element detector for betting UI components.
"""
from typing import Any, Dict, List


class ElementDetector:
    """
    Classifies UI elements on prediction market web interfaces:
    - Yes/No buttons
    - Stake input fields
    - Submit/Confirm order buttons
    - Slider controls
    """

    @staticmethod
    def classify_elements(elements: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        classified = {
            "buy_yes_buttons": [],
            "buy_no_buttons": [],
            "stake_inputs": [],
            "submit_buttons": [],
            "other": [],
        }

        for el in elements:
            txt = str(el.get("text", "")).lower()
            sel = str(el.get("selector", "")).lower()

            if "yes" in txt or "buy yes" in txt:
                classified["buy_yes_buttons"].append(el)
            elif "no" in txt or "buy no" in txt:
                classified["buy_no_buttons"].append(el)
            elif "input" in sel or "amount" in txt or "stake" in txt:
                classified["stake_inputs"].append(el)
            elif any(k in txt for k in ["place bet", "buy", "submit", "confirm", "trade"]):
                classified["submit_buttons"].append(el)
            else:
                classified["other"].append(el)

        return classified
