"""
Visual screenshot parser and odds widget detection.
"""
from typing import Dict, List, Any, Optional
from PIL import Image


class ScreenshotAnalyzer:
    """
    Parses UI cards, price badges, and odds boxes from rendered screenshots.
    """

    def __init__(self):
        pass

    def extract_odds_from_text_detections(self, detected_text: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Scans OCR text bounding boxes to find pattern-matching odds numbers (e.g., 1.85, 2.40, +150, -110, 65%).
        """
        extracted_odds = []
        for item in detected_text:
            txt = str(item.get("text", "")).strip()
            # Try decimal odds detection (e.g., 1.50 - 99.0)
            try:
                if "." in txt:
                    val = float(txt.replace("$", "").replace("x", ""))
                    if 1.01 <= val <= 100.0:
                        extracted_odds.append({
                            "type": "decimal_odds",
                            "value": val,
                            "raw_text": txt,
                            "position": item.get("position"),
                            "confidence": item.get("confidence", 1.0),
                        })
                elif txt.endswith("%"):
                    pct = float(txt.replace("%", ""))
                    if 1.0 <= pct <= 99.0:
                        extracted_odds.append({
                            "type": "percentage_probability",
                            "value": pct / 100.0,
                            "raw_text": txt,
                            "position": item.get("position"),
                            "confidence": item.get("confidence", 1.0),
                        })
            except ValueError:
                continue

        return extracted_odds
