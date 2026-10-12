"""CachedSearch: official W3C APG patterns from the local cache (knowledge/aria_patterns/).
The Tavily adapter (DR-6) replaces this at runtime for the prize lane; same port."""

from pathlib import Path

from blindrun.ports import Pattern

_CACHE = Path(__file__).resolve().parents[3] / "knowledge" / "aria_patterns"

_KNOWN = {
    "radio": Pattern(
        widget="radio",
        url="https://www.w3.org/WAI/ARIA/apg/patterns/radio/",
        summary="Radio group: native radio buttons inside a fieldset with a legend; "
        "arrow keys move within the group; Space selects.",
        keyboard=["ArrowDown/ArrowUp: next/previous radio", "Space: select", "Tab: leave the group"],
        source="cache",
    ),
    "listbox": Pattern(
        widget="listbox",
        url="https://www.w3.org/WAI/ARIA/apg/patterns/listbox/",
        summary="Listbox: role=listbox with role=option children; arrow keys move focus; "
        "selection follows focus or is toggled with Space (declare which).",
        keyboard=["ArrowDown/ArrowUp: move focus", "Home/End: first/last option", "Space: toggle"],
        source="cache",
    ),
    "combobox": Pattern(
        widget="combobox",
        url="https://www.w3.org/WAI/ARIA/apg/patterns/combobox/",
        summary="Combobox: role=combobox with aria-expanded; typing filters; "
        "aria-activedescendant tracks the highlighted option.",
        keyboard=["ArrowDown: open / next option", "Enter: accept", "Escape: dismiss"],
        source="cache",
    ),
    "dialog": Pattern(
        widget="dialog",
        url="https://www.w3.org/WAI/ARIA/apg/patterns/dialog/",
        summary="Dialog: focus moves into the dialog on open, is trapped inside, "
        "and returns to the invoking element on close.",
        keyboard=["Tab: cycle inside", "Escape: close", "focus returns to opener"],
        source="cache",
    ),
}


class CachedSearch:
    async def pattern(self, widget: str) -> Pattern:
        return _KNOWN.get(widget.lower().strip()) or Pattern(
            widget=widget,
            url="https://www.w3.org/WAI/ARIA/apg/patterns/",
            summary="APG patterns index (widget not in local cache yet).",
            keyboard=[],
            source="cache",
        )

    async def docs(self, wcag_sc: str) -> str:
        """Offline floor for the WCAG Understanding doc (TavilySearch confirms live)."""
        return f"https://www.w3.org/WAI/WCAG22/Understanding/{wcag_sc.replace('.', '-')}.html"
