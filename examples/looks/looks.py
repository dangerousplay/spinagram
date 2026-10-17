"""One diagram, four looks: `spinagram serve examples/looks/` and compare. Only the stylesheet changes."""
from _platform import platform

diagrams = [
    platform("LOOK01", "Midnight", "midnight.css"),
    platform("LOOK02", "Blueprint", "blueprint.css"),
    platform("LOOK03", "Pastel", "pastel.css"),
    platform("LOOK04", "Editorial", "editorial.css"),
]
