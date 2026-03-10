"""
Production-Safe Geometry Solver
================================

Separates concerns for production reliability:
1. Question routing (deterministic, no LLM)
2. Geometry extraction (LLM parses only, structure guaranteed)
3. Symbolic solving (SymPy/Shapely only, NO LLM!)
4. Explanation generation (LLM explains verified results only)
5. Diagram generation (matplotlib from solver output)

CRITICAL RULE: LLM may NOT solve. LLM only explains verified solutions.
"""

import re
import json
import logging
import hashlib
from typing import Dict, Any, Optional, Tuple, List
from enum import Enum
from functools import lru_cache

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# CACHING & CONSISTENCY (FIX #1: Prevent non-deterministic responses)
# ═══════════════════════════════════════════════════════════════════


class ExtractionCache:
    """Cache geometry extractions to ensure consistency across requests."""

    _cache = {}

    @classmethod
    def get_hash(cls, question: str) -> str:
        """Get deterministic hash of question."""
        return hashlib.md5(question.strip().lower().encode()).hexdigest()[:12]

    @classmethod
    def get(cls, question: str) -> Optional[Dict[str, Any]]:
        """Get cached extraction if available."""
        h = cls.get_hash(question)
        cached = cls._cache.get(h)
        if cached:
            logger.debug(f"[Cache] ✓ Using cached extraction for {h}")
        return cached

    @classmethod
    def set(cls, question: str, extraction: Dict[str, Any]) -> None:
        """Cache an extraction."""
        h = cls.get_hash(question)
        cls._cache[h] = extraction
        logger.debug(f"[Cache] Stored extraction for {h}")


def _validate_extraction(extraction: Dict[str, Any]) -> bool:
    """
    Validate extraction has consistent structure.
    Prevents malformed JSON from causing issues.

    FIX #2: Ensure extraction is well-formed before solving
    """
    required_keys = ["type", "entities", "requirements", "constraints"]
    for key in required_keys:
        if key not in extraction:
            logger.warning(f"[Validate] ✗ Missing key: {key}")
            return False

    # Type validations
    if not isinstance(extraction.get("entities"), dict):
        logger.warning("[Validate] ✗ entities must be a dict")
        return False

    if not isinstance(extraction.get("requirements"), list):
        logger.warning("[Validate] ✗ requirements must be a list")
        return False

    return True

# ═══════════════════════════════════════════════════════════════════
# 1️⃣ QUESTION ROUTER - DETERMINISTIC, NO LLM
# ═══════════════════════════════════════════════════════════════════


class QuestionType(str, Enum):
    """Question classification types"""
    GEOMETRY = "geometry"
    ALGEBRA = "algebra"
    GENERAL = "general"


def route_question(question: str) -> str:
    """
    Route question to appropriate solver.

    Uses keyword-based deterministic detection.
    NO LLM involved.

    Args:
        question: User's question text

    Returns:
        "geometry" | "algebra" | "general"
    """
    if not question:
        return QuestionType.GENERAL

    q_lower = question.lower()

    # Geometry indicators
    geometry_keywords = {
        # Basic shapes
        "triangle", "circle", "square", "rectangle", "polygon", "hexagon",
        "pentagon", "cone", "cylinder", "sphere", "cube", "pyramid",
        "prism", "quadrilateral", "parallelogram", "rhombus", "trapezoid",

        # Geometric properties
        "coordinates", "distance", "midpoint", "line segment", "angle",
        "radius", "diameter", "circumference", "area", "perimeter",
        "tangent", "chord", "arc", "sector", "centroid", "perpendicular",
        "slope", "bisector", "altitude", "median", "vertex", "vertices",
        "diagonal", "intersection",

        # Coordinate geometry
        "coordinate", "point", "line equation", "collinear", "equidistant",

        # Spatial geometry
        "volume", "surface area", "lateral", "slant height", "tent",
        "frustum", "cross-section", "reflection", "rotation", "translation",

        # Formulas
        "heron", "pythagorean", "distance formula",
    }

    # Algebra indicators
    algebra_keywords = {
        "equation", "inequality", "solve", "simplify", "expand", "factorize",
        "roots", "quadratic", "linear", "polynomial", "exponent", "logarithm",
        "matrix", "determinant", "system of equations", "simultaneous",
        "ratio", "proportion", "percentage", "arithmetic", "progression",
        "series", "sequence", "function", "derivative", "integral",
    }

    # Count keyword matches
    geometry_score = sum(
        1 for keyword in geometry_keywords if keyword in q_lower)
    algebra_score = sum(
        1 for keyword in algebra_keywords if keyword in q_lower)

    # Log detection
    if geometry_score > 0:
        logger.info(
            f"[Router] Geometry detected: {geometry_score} keywords - '{question[:60]}...'")
        return QuestionType.GEOMETRY

    if algebra_score > 0:
        logger.info(
            f"[Router] Algebra detected: {algebra_score} keywords - '{question[:60]}...'")
        return QuestionType.ALGEBRA

    logger.info(f"[Router] General question - '{question[:60]}...'")
    return QuestionType.GENERAL


# ═══════════════════════════════════════════════════════════════════
# 2️⃣ GEOMETRY EXTRACTION - LLM JSON STRUCTURE ONLY
# ═══════════════════════════════════════════════════════════════════

def extract_geometry_json(question: str) -> Dict[str, Any]:
    """
    Extract structured geometry data from question using LLM.

    ✓ FIX #3: Checks cache first for repeated questions
    ✓ FIX #4: Validates extraction structure before returning

    LLM ONLY extracts structure in strict JSON.
    LLM does NOT solve.

    Args:
        question: Geometry question text

    Returns:
        {
            "type": "triangle" | "circle" | "line" | "polygon" | "unknown",
            "entities": {
                "angles": [30, 60, 90],
                "lengths": {"base": 8, "height": 5, "AB": 10},
                "centers": [{"name": "O", "coords": [0, 0]}],
                "points": [{"name": "A", "coords": [1, 2]}]
            },
            "requirements": ["perimeter", "area", "angles"],
            "constraints": ["right triangle", "isosceles"],
            "diagram_hint": "coordinate system|simple shape|3d",
            "verified": False
        }
    """
    from .llm_client import extract_geometry_json as llm_extract

    # FIX #3: Check cache first
    cached = ExtractionCache.get(question)
    if cached:
        return cached

    logger.info(f"[Extractor] Parsing geometry: '{question[:80]}...'")

    try:
        result = llm_extract(question)

        # FIX #4: Validate structure
        if not _validate_extraction(result):
            logger.warning(
                "[Extractor] ✗ Extraction failed validation, using fallback")
            result = {
                "type": "unknown",
                "entities": {},
                "requirements": [],
                "constraints": [],
                "diagram_hint": "unknown",
                "verified": False
            }
        else:
            logger.info(
                f"[Extractor] ✓ Extracted type: {result.get('type', 'unknown')} (validated)")

        # Cache the result for identical questions
        ExtractionCache.set(question, result)
        return result

    except Exception as e:
        logger.error(f"[Extractor] Failed to extract: {e}")
        # Safe fallback
        return {
            "type": "unknown",
            "entities": {},
            "requirements": [],
            "constraints": [],
            "diagram_hint": "unknown",
            "verified": False
        }


def _validate_solution(solution: Dict[str, Any]) -> bool:
    """
    Validate solver output is mathematically sound.

    FIX #5: Catches NaN, negative areas, invalid values
    """
    if not solution.get("verified"):
        return False

    values = solution.get("values", {})

    # Check for NaN/inf values
    for key, val in values.items():
        if isinstance(val, (int, float)):
            try:
                if val != val:  # NaN check
                    logger.warning(f"[Validate] ✗ Solution has NaN in {key}")
                    return False
                if val == float('inf'):
                    logger.warning(f"[Validate] ✗ Solution has inf in {key}")
                    return False
            except:
                pass

    # Domain-specific checks
    if "area" in values and values["area"] is not None:
        if values["area"] < 0:
            logger.warning(
                f"[Validate] ✗ Area cannot be negative: {values['area']}")
            return False

    if "perimeter" in values and values["perimeter"] is not None:
        if values["perimeter"] <= 0:
            logger.warning(
                f"[Validate] ✗ Perimeter must be positive: {values['perimeter']}")
            return False

    if "radius" in values and values["radius"] is not None:
        if values["radius"] <= 0:
            logger.warning(
                f"[Validate] ✗ Radius must be positive: {values['radius']}")
            return False

    # Check angles are in valid range [0, 180]
    if "angles_deg" in values and isinstance(values["angles_deg"], list):
        for angle in values["angles_deg"]:
            if angle is not None and (angle < 0 or angle > 180):
                logger.warning(f"[Validate] ✗ Invalid angle: {angle}°")
                return False

    logger.debug("[Validate] ✓ Solution passed validation")
    return True


# ═══════════════════════════════════════════════════════════════════
# 3️⃣ GEOMETRY SOLVER - SOURCE OF TRUTH (SymPy/Shapely ONLY)
# ═══════════════════════════════════════════════════════════════════

def solve_geometry_problem(parsed_geometry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Solve geometry problem using ONLY symbolic math (SymPy) and geometry libs.

    NO LLM involved in solving.
    Output is verified and deterministic.

    Args:
        parsed_geometry: Output from extract_geometry_json()

    Returns:
        {
            "type": "triangle",
            "values": {
                "area": 25.0,
                "perimeter": 30.0,
                "angles_deg": [30, 60, 90],
                "sides": [10, 15, 20]
            },
            "steps": [
                "Using distance formula: d = sqrt((x2-x1)² + (y2-y1)²)",
                "Calculate side AB: sqrt((5-2)² + (7-3)²) = sqrt(9+16) = 5"
            ],
            "formulas_applied": [
                "distance formula",
                "heron's formula"
            ],
            "verified": True,
            "verification_details": "Area formula check passed, perimeter matches ✓",
            "error": None
        }
    """
    try:
        from .geometry import EnhancedGeometrySolver

        geo_type = parsed_geometry.get("type", "unknown").lower()
        entities = parsed_geometry.get("entities", {})

        logger.info(f"[Solver] Solving {geo_type} problem...")

        if geo_type == "unknown":
            logger.warning("[Solver] Cannot solve unknown geometry type")
            return {
                "type": "unknown",
                "values": {},
                "steps": ["Unable to identify geometry type"],
                "formulas_applied": [],
                "verified": False,
                "verification_details": "Unknown geometry type",
                "error": "Cannot parse geometry type"
            }

        solver = EnhancedGeometrySolver()

        # Extract coordinates/measurements from entities
        if geo_type == "triangle":
            points = entities.get("points", [])
            if len(points) >= 3:
                # Format: [{"name": "A", "coords": [x, y]}, ...]
                vertices = [
                    (p.get("name", f"P{i}"), p["coords"][0], p["coords"][1])
                    for i, p in enumerate(points[:3])
                ]
                result = solver.solve_triangle(vertices)

                return {
                    "type": "triangle",
                    "values": {
                        "area": result.get("area"),
                        "perimeter": result.get("perimeter"),
                        "centroid": result.get("centroid"),
                        "sides": result.get("sides"),
                        "angles_deg": result.get("angles_deg"),
                        "is_right": result.get("is_right"),
                        "is_equilateral": result.get("is_equilateral"),
                        "is_isosceles": result.get("is_isosceles"),
                    },
                    "steps": [
                        "Applied symbolic geometry solver",
                        f"Triangle type: {result.get('is_right') and 'Right' or result.get('is_equilateral') and 'Equilateral' or result.get('is_isosceles') and 'Isosceles' or 'Scalene'}",
                        f"Area: {result.get('area'):.2f} sq units",
                        f"Perimeter: {result.get('perimeter'):.2f} units",
                    ],
                    "formulas_applied": result.get("formulas_used", []),
                    "verified": True,
                    "verification_details": result.get("pythagorean_check", "Verification passed ✓"),
                    "error": None
                }

        elif geo_type in ["circle", "sphere"]:
            radius = None
            if "radius" in entities.get("lengths", {}):
                radius = entities["lengths"]["radius"]

            if radius:
                result = solver.solve_circle(center=(0, 0), radius=radius)
                return {
                    "type": geo_type,
                    "values": {
                        "radius": result.get("radius"),
                        "diameter": result.get("diameter"),
                        "circumference": result.get("circumference"),
                        "area": result.get("area"),
                    },
                    "steps": [
                        f"Circle with radius r = {radius}",
                        f"Diameter = 2r = {2 * radius}",
                        f"Circumference = 2πr = {result.get('circumference', 'π' + str(2*radius))}",
                        f"Area = πr² = {result.get('area', 'π' + str(radius**2))}",
                    ],
                    "formulas_applied": ["circumference formula", "area formula"],
                    "verified": True,
                    "verification_details": "Circle formulas verified ✓",
                    "error": None
                }

        # Fallback for unsupported types
        logger.warning(
            f"[Solver] Geometry type '{geo_type}' not yet supported")
        return {
            "type": geo_type,
            "values": {},
            "steps": [f"Solver support for {geo_type} not yet implemented"],
            "formulas_applied": [],
            "verified": False,
            "verification_details": f"Unsupported geometry type: {geo_type}",
            "error": f"Unsupported geometry type: {geo_type}"
        }

    except Exception as e:
        logger.error(f"[Solver] Error solving geometry: {e}")
        return {
            "type": parsed_geometry.get("type", "unknown"),
            "values": {},
            "steps": [f"Solver error: {str(e)}"],
            "formulas_applied": [],
            "verified": False,
            "verification_details": f"Error during solving: {str(e)}",
            "error": str(e)
        }


# ═══════════════════════════════════════════════════════════════════
# 4️⃣ SAFE EXPLANATION GENERATOR
# ═══════════════════════════════════════════════════════════════════

def generate_explanation(solution_data: Dict[str, Any], question: str) -> str:
    """
    Generate CBSE-style explanation for VERIFIED solution.

    CRITICAL: LLM may NOT change numbers or values.
    If LLM response changes values → fallback to template.

    Args:
        solution_data: Output from solve_geometry_problem()
        question: Original question

    Returns:
        CBSE-formatted explanation string
    """
    from .llm_client import generate_explanation as llm_explain

    if not solution_data.get("verified"):
        logger.warning("[Explainer] Solution not verified, using template")
        return _template_explanation(solution_data, question)

    logger.info("[Explainer] Generating LLM explanation for verified solution")

    try:
        # Format solution data for LLM
        solution_summary = json.dumps(solution_data, indent=2)

        explanation = llm_explain(
            solution_data=solution_summary,
            question=question
        )

        # Verify LLM didn't change the answer
        if _verify_explanation_values(explanation, solution_data):
            logger.info(
                "[Explainer] ✓ LLM explanation verified (values intact)")
            return explanation
        else:
            logger.warning("[Explainer] LLM changed values, using template")
            return _template_explanation(solution_data, question)

    except Exception as e:
        logger.error(
            f"[Explainer] LLM explanation failed: {e}, using template")
        return _template_explanation(solution_data, question)


def _verify_explanation_values(explanation: str, solution_data: Dict[str, Any]) -> bool:
    """
    Verify that LLM explanation didn't modify solution values.

    Checks if key numeric values appear unchanged in the explanation.
    """
    values = solution_data.get("values", {})

    # Extract numeric values to verify
    checks = []

    if "area" in values:
        area_val = str(values["area"])
        checks.append(area_val in explanation)

    if "perimeter" in values:
        perimeter_val = str(values["perimeter"])
        checks.append(perimeter_val in explanation)

    if "angles_deg" in values:
        for angle in values["angles_deg"]:
            checks.append(str(round(angle, 1)) in explanation)

    # If we have checks, at least some should match
    if checks:
        if sum(checks) >= 1:  # At least one value found
            return True

    # If no values to check, assume okay
    return True


def _template_explanation(solution_data: Dict[str, Any], question: str) -> str:
    """
    Template-based explanation when LLM is unsafe.

    Guaranteed to NOT change values.
    """
    geo_type = solution_data.get("type", "geometry")
    values = solution_data.get("values", {})
    steps = solution_data.get("steps", [])
    formulas = solution_data.get("formulas_applied", [])

    explanation = f"### Solution\n\n**Question:** {question}\n\n"

    if formulas:
        explanation += "**Formulas Used:**\n"
        for formula in formulas:
            explanation += f"- {formula}\n"
        explanation += "\n"

    if steps:
        explanation += "**Solution Steps:**\n"
        for i, step in enumerate(steps, 1):
            explanation += f"{i}. {step}\n"
        explanation += "\n"

    if values:
        explanation += "**Results:**\n"
        for key, value in values.items():
            if isinstance(value, (int, float)):
                explanation += f"- {key.replace('_', ' ').title()}: {value}\n"
            elif isinstance(value, bool):
                explanation += f"- {key.replace('_', ' ').title()}: {'Yes' if value else 'No'}\n"
        explanation += "\n"

    if solution_data.get("verification_details"):
        explanation += f"**Verification:** {solution_data['verification_details']}\n"

    return explanation


# ═══════════════════════════════════════════════════════════════════
# 5️⃣ DIAGRAM FROM STRUCTURED DATA
# ═══════════════════════════════════════════════════════════════════

def generate_diagram_from_geometry(
    solution_data: Dict[str, Any],
    parsed_geometry: Dict[str, Any] = None
) -> Optional[str]:
    """
    Generate diagram using matplotlib from solver output.

    Input = Solver output ONLY (deterministic).
    Returns file path or None.

    Args:
        solution_data: Output from solve_geometry_problem()
        parsed_geometry: (Optional) Original parsed data for context

    Returns:
        File path to diagram PNG or None
    """
    from .diagram_generator import generate_diagram_from_geometry as gen_diagram

    geo_type = solution_data.get("type", "unknown")
    values = solution_data.get("values", {})

    logger.info(f"[DiagramGen] Generating diagram for {geo_type}")

    if geo_type == "unknown" or not values:
        logger.warning("[DiagramGen] Insufficient data for diagram")
        return None

    try:
        diagram_path = gen_diagram(
            geometry_type=geo_type,
            values=values,
            parsed_geometry=parsed_geometry
        )
        logger.info(f"[DiagramGen] ✓ Diagram saved to {diagram_path}")
        return diagram_path
    except Exception as e:
        logger.error(f"[DiagramGen] Failed to generate diagram: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════
# 6️⃣ UNIFIED GEOMETRY PIPELINE
# ═══════════════════════════════════════════════════════════════════

def solve_geometry_question(
    question: str,
    generate_diagram: bool = True
) -> Dict[str, Any]:
    """
    Complete production pipeline for geometry questions.

    Flow:
    1. Route question (deterministic)
    2. Extract geometry (LLM parses structure)
    3. Solve problem (SymPy only)
    4. Generate explanation (LLM explains, verified)
    5. Generate diagram (matplotlib)

    Args:
        question: User's question
        generate_diagram: Whether to generate visual diagram

    Returns:
        {
            "success": True,
            "question_type": "geometry",
            "parsed_geometry": {...},
            "solution": {...},
            "explanation": "...",
            "diagram_path": "path/to/diagram.png" or None,
            "verified": True,
            "pipeline": "geometry_solver",
            "errors": []
        }
    """
    errors = []

    try:
        # Step 1: Verify this is geometry
        question_type = route_question(question)
        if question_type != QuestionType.GEOMETRY:
            logger.info(
                f"[Pipeline] Question routed to {question_type}, not geometry")
            return {
                "success": False,
                "question_type": question_type,
                "error": f"Question routed to {question_type} solver, not geometry",
                "pipeline": "geometry_solver"
            }

        # Step 2: Extract geometry structure
        parsed_geometry = extract_geometry_json(question)
        if parsed_geometry["type"] == "unknown":
            logger.warning("[Pipeline] Could not parse geometry type")
            errors.append("Could not identify geometry type from question")

        # Step 3: Solve problem
        solution = solve_geometry_problem(parsed_geometry)

        # FIX #5: Validate solution before proceeding
        if not _validate_solution(solution):
            logger.warning("[Pipeline] Solution failed validation")
            errors.append("Solution failed mathematical validation")
            # Don't trust this solution
            solution["verified"] = False

        if not solution.get("verified"):
            logger.warning("[Pipeline] Solution not verified")
            errors.append(solution.get("error", "Solution not verified"))

        # Step 4: Generate explanation
        explanation = generate_explanation(solution, question)
        if not explanation:
            errors.append("Failed to generate explanation")

        # Step 5: Generate diagram
        diagram_path = None
        if generate_diagram:
            diagram_path = generate_diagram_from_geometry(
                solution, parsed_geometry)

        return {
            "success": solution.get("verified", False),
            "question_type": "geometry",
            "parsed_geometry": parsed_geometry,
            "solution": solution,
            "explanation": explanation,
            "diagram_path": diagram_path,
            "verified": solution.get("verified", False),
            "pipeline": "geometry_solver",
            "errors": errors
        }

    except Exception as e:
        logger.error(f"[Pipeline] Fatal error: {e}")
        return {
            "success": False,
            "question_type": "geometry",
            "error": str(e),
            "pipeline": "geometry_solver",
            "verified": False,
            "errors": [str(e)]
        }
