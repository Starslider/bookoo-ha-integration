"""Shot analysis heuristics."""

from __future__ import annotations


def analyze_shot(shot: dict, samples: list[dict]) -> dict:
    """Return metrics and practical adjustment suggestions."""
    suggestions: list[str] = []
    duration = shot.get("duration_s") or 0
    final_weight = shot.get("final_weight_g")
    avg_flow = shot.get("avg_flow_g_s")
    max_pressure = shot.get("max_pressure_bar")
    input_dose = shot.get("input_dose_g")
    target_yield = shot.get("target_yield_g")
    brew_ratio = final_weight / input_dose if final_weight is not None and input_dose else None
    yield_error = final_weight - target_yield if final_weight is not None and target_yield is not None else None

    if duration < 20:
        suggestions.append("Shot ran short. Grind finer or increase dose if the taste is thin or sour.")
    elif duration > 35:
        suggestions.append("Shot ran long. Grind coarser or reduce dose if the taste is bitter or drying.")

    if avg_flow is not None:
        if avg_flow > 2.5:
            suggestions.append("Average flow is high. Grind finer or improve puck prep to slow extraction.")
        elif avg_flow < 1.0:
            suggestions.append("Average flow is low. Grind coarser or check for puck choking.")

    if max_pressure is not None:
        if max_pressure > 10:
            suggestions.append("Peak pressure is high. Grind slightly coarser or reduce puck resistance.")
        elif max_pressure < 6:
            suggestions.append("Peak pressure is low. Grind finer, increase dose, or check pump/pressure setup.")

    if final_weight is not None and final_weight < 25:
        suggestions.append("Yield is low. Stop later or use a lower dose if the cup is overly intense.")

    if yield_error is not None:
        if yield_error < -2:
            suggestions.append("Yield landed below target. Let the shot run longer or reduce the target if taste is balanced.")
        elif yield_error > 2:
            suggestions.append("Yield exceeded target. Stop earlier or use a larger cup yield intentionally if taste needs more extraction.")

    if brew_ratio is not None:
        if brew_ratio < 1.7:
            suggestions.append("Brew ratio is short. Consider a higher yield for more extraction if the shot tastes sharp.")
        elif brew_ratio > 2.5:
            suggestions.append("Brew ratio is long. Consider a lower yield if the shot tastes hollow or thin.")

    pressure_values = [sample["pressure_bar"] for sample in samples if sample["pressure_bar"] is not None]
    pressure_range = max(pressure_values) - min(pressure_values) if pressure_values else None
    if pressure_range is not None and pressure_range > 4 and duration > 10:
        suggestions.append("Pressure varied a lot. Improve distribution/tamping consistency and watch for channeling.")

    if not suggestions:
        suggestions.append("Shot metrics look broadly reasonable. Adjust based on taste: finer for sour/thin, coarser for bitter/drying.")

    return {
        "metrics": {
            "duration_s": duration,
            "final_weight_g": final_weight,
            "avg_flow_g_s": avg_flow,
            "max_pressure_bar": max_pressure,
            "pressure_range_bar": pressure_range,
            "input_dose_g": input_dose,
            "target_yield_g": target_yield,
            "brew_ratio": brew_ratio,
            "yield_error_g": yield_error,
        },
        "suggestions": suggestions,
    }
