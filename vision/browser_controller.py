"""
Playwright-based browser automation controller with vision and OCR support.
"""
import io
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple, Any
from loguru import logger
from PIL import Image

try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    Page = Any
    Browser = Any
    BrowserContext = Any

try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False


@dataclass
class ElementInfo:
    selector: str
    text: str
    bounding_box: Dict[str, float]
    confidence: float
    element_type: str


class VisionBrowser:
    """
    Browser controller with screenshot analysis, visual element detection, and OCR.
    """

    def __init__(
        self,
        headless: bool = True,
        viewport: Tuple[int, int] = (1920, 1080),
        ocr_languages: Optional[List[str]] = None,
    ):
        self.headless = headless
        self.viewport = viewport
        self.ocr_languages = ocr_languages or ["en"]
        self.ocr_reader = None

        if HAS_EASYOCR:
            try:
                self.ocr_reader = easyocr.Reader(self.ocr_languages, gpu=False)
            except Exception as e:
                logger.debug(f"Could not load EasyOCR: {e}")

        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def start(self):
        """Initializes the browser context."""
        if not HAS_PLAYWRIGHT:
            logger.warning("Playwright is not installed in the current environment. Operating in mock vision mode.")
            return

        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
            self.context = await self.browser.new_context(
                viewport={"width": self.viewport[0], "height": self.viewport[1]},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            self.page = await self.context.new_page()
            logger.info("Vision browser started successfully.")
        except Exception as e:
            logger.warning(f"Failed to launch Chromium browser: {e}. Falling back to simulation.")

    async def stop(self):
        """Closes all browser sessions."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Vision browser stopped.")

    async def navigate(self, url: str, wait_for: Optional[str] = None):
        if not self.page:
            logger.debug(f"[MockVision] Navigating to {url}")
            return

        await self.page.goto(url, wait_until="networkidle")
        if wait_for:
            await self.page.wait_for_selector(wait_for, timeout=10000)
        logger.info(f"Navigated to {url}")

    async def screenshot(self, full_page: bool = False, selector: Optional[str] = None) -> Image.Image:
        """Captures page screenshot."""
        if not self.page:
            # Generate blank placeholder image if browser isn't active
            return Image.new("RGB", self.viewport, color=(30, 30, 40))

        if selector:
            element = await self.page.query_selector(selector)
            if element:
                screenshot_bytes = await element.screenshot()
            else:
                screenshot_bytes = await self.page.screenshot(full_page=full_page)
        else:
            screenshot_bytes = await self.page.screenshot(full_page=full_page)

        return Image.open(io.BytesIO(screenshot_bytes))

    async def analyze_screen(self) -> Dict[str, Any]:
        """Runs screenshot capture + OCR + DOM extraction."""
        img = await self.screenshot()
        detected_text = []

        if self.ocr_reader:
            try:
                img_bytes = io.BytesIO()
                img.save(img_bytes, format="PNG")
                ocr_results = self.ocr_reader.readtext(img_bytes.getvalue())
                for bbox, text, conf in ocr_results:
                    detected_text.append({
                        "text": text,
                        "confidence": float(conf),
                        "position": {
                            "x": bbox[0][0],
                            "y": bbox[0][1],
                            "width": bbox[2][0] - bbox[0][0],
                            "height": bbox[2][1] - bbox[0][1],
                        }
                    })
            except Exception as e:
                logger.debug(f"OCR execution warning: {e}")

        elements = await self._get_interactive_elements()
        url = self.page.url if self.page else "https://simulated.market"
        title = (await self.page.title()) if self.page else "Simulated Prediction Market"

        return {
            "screenshot": img,
            "detected_text": detected_text,
            "elements": elements,
            "url": url,
            "title": title,
        }

    async def _get_interactive_elements(self) -> List[ElementInfo]:
        if not self.page:
            return []

        elements = []
        selectors = ["button", "a", "input", "[role='button']", "[class*='btn']"]
        for sel in selectors:
            try:
                nodes = await self.page.query_selector_all(sel)
                for i, node in enumerate(nodes[:20]):
                    try:
                        box = await node.bounding_box()
                        txt = await node.inner_text()
                        vis = await node.is_visible()
                        if vis and box:
                            elements.append(ElementInfo(
                                selector=f"{sel}:nth-of-type({i+1})",
                                text=txt[:80] if txt else "",
                                bounding_box=box,
                                confidence=1.0,
                                element_type=sel,
                            ))
                    except Exception:
                        continue
            except Exception:
                continue

        return elements
