"""Recipe persistence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Recipe:
    """Current espresso recipe."""

    input_dose_g: float = 18.0
    target_yield_g: float = 36.0


class RecipeStore:
    """Store the active recipe in a small JSON file."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def load(self) -> Recipe:
        """Load the current recipe."""
        if not self.path.exists():
            return Recipe()
        data = json.loads(self.path.read_text())
        return Recipe(
            input_dose_g=float(data.get("input_dose_g", 18.0)),
            target_yield_g=float(data.get("target_yield_g", 36.0)),
        )

    def save(self, recipe: Recipe) -> Recipe:
        """Save the current recipe."""
        self.path.write_text(json.dumps(asdict(recipe), indent=2) + "\n")
        return recipe
