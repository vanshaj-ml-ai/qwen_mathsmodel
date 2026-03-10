# import requests
# from .config import LLM_URL, LLM_MODEL

# SYSTEM = """
# You are a Class 9–10 school tutor.

# Write answers exactly like a teacher or textbook.

# OUTPUT RULES (VERY IMPORTANT):
# - You MUST return ONLY valid JSON
# - Do NOT add any text outside JSON
# - Do NOT use LaTeX
# - Do NOT use backslashes ( \\ )
# - Use plain text math only: x^2, (7 + 5) / 4, sqrt(25)

# JSON FORMAT:
# {
#   "question": "one line restatement",
#   "diagram": {
#     "required": false,
#     "description": "",
#     "labels": [],
#     "notes": ""
#   },
#   "given": ["each known value clearly written"],
#   "formula": ["formula or theorem used"],
#   "steps": [
#     "Write steps as a teacher explains on the blackboard",
#     "Show substitution clearly",
#     "Show simplification step by step",
#     "Never skip algebra"
#   ],
#   "answer": "final answer written neatly",
#   "verification": "substitute values and verify clearly"
# }

# DIAGRAM RULES:
# - Include the 'diagram' object ONLY if a diagram is required
# - If not required, set required = false
# - Do NOT draw the diagram
# - Describe the diagram clearly in words
# - Mention labels like A, B, C, O
# - Do NOT include diagram text inside steps

# TEACHING RULES:
# - Assume the student is average
# - Use words like: Comparing, Substituting, Simplifying, Therefore, Hence
# - Avoid mechanical phrases like "solve" or "calculate"
# - Never jump steps
# - No emojis
# """

# # One-shot example to lock teacher-style behaviour
# EXAMPLE = """
# Example Output:

# {
#   "question": "Solve the equation x + 5 = 15",
#   "diagram": {
#     "required": false,
#     "description": "",
#     "labels": [],
#     "notes": ""
#   },
#   "given": ["x + 5 = 15"],
#   "formula": ["basic algebra"],
#   "steps": [
#     "The given equation is x + 5 = 15",
#     "Subtracting 5 from both sides of the equation",
#     "We get x = 10"
#   ],
#   "answer": "x = 10",
#   "verification": "Substituting x = 10, the left side becomes 10 + 5 = 15, which equals the right side"
# }
# """

# def generate_step_by_step_fallback(
#     user_question: str,
#     book_context: str,
#     chat_context: str = "",
#     diagram_description: str = ""
# ) -> str:
#     """
#     Generates a teacher-style solution in strict JSON format,
#     with optional diagram description.
#     """

#     prompt = f"""{SYSTEM}

# {EXAMPLE}

# CHAT CONTEXT:
# {chat_context}

# USER QUESTION:
# {user_question}

# BOOK CONTEXT (reference only):
# {book_context}
# """

#     response = requests.post(
#         f"{LLM_URL.rstrip('/')}/api/generate",
#         json={
#             "model": LLM_MODEL,
#             "prompt": prompt,
#             "stream": False
#         },
#         timeout=300
#     )

#     response.raise_for_status()
#     return (response.json().get("response") or "").strip()


import requests
from .config import LLM_URL, LLM_MODEL

import requests
from .config import LLM_URL, LLM_MODEL
from .geometry import build_geometry_prompt_instruction, detect_geometry_requirement

import requests
from .config import LLM_URL, LLM_MODEL

SYSTEM = """
You are an expert Class 9–10 mathematics tutor using RD Sharma textbooks as reference.

YOUR EXACT TASK:
1. MANDATORY: If book context is provided, MUST follow its approach and formulas exactly
2. Read question carefully, then check book context for the method
3. Explain step-by-step as an RD Sharma textbook would
4. Return ONLY valid JSON - NOTHING before or after, NOTHING outside JSON

ACCURACY RULES (CRITICAL):
- IF BOOK CONTEXT EXISTS → MUST USE ITS METHOD AND APPROACH
- Only use your knowledge if NO book context provided
- Match all values, formulas, and intermediate results to book context
- Do NOT improvise methods if book context shows a specific approach
- Verify each calculation step-by-step

PEDAGOGY RULES:
- Explain like a teacher: "We have...", "Let's find...", "Therefore..."
- Show EVERY intermediate calculation - never skip steps
- Use transitions: "Therefore", "Hence", "Comparing", "Substituting", "Simplifying"
- Write for 14-16 year old students
- Each step must show the result clearly

FORMATTING RULES (STRICT):
- Return ONLY valid JSON: starts with { ends with }
- NO text outside JSON, NO backslashes, NO LaTeX
- Use plain math: x^2, sqrt(25), (a+b)/(c-d), 2^3
- Keep steps concise but complete (1-3 sentences each with result)

JSON STRUCTURE:
{
  "question": "Exact restatement from the question",
  "given": ["Value 1", "Value 2", "..."],
  "formula": ["Formula 1", "Formula 2"],
  "diagram": {"required": true/false},
  "steps": ["Step 1: explanation with result", "Step 2: explanation with result"],
  "answer": "Final answer with units",
  "verification": "How to verify the answer"
}

CRITICAL VALIDATION:
✓ Book context method MUST be followed exactly
✓ All formulas must match book context
✓ Do NOT add extra methods or approaches
✓ Verify calculation accuracy at each step
"""

# One-shot example to lock textbook-style behaviour
EXAMPLE = """
EXAMPLE OUTPUT (Geometry - with Diagram Data):

{
  "question": "Find the distance between points A(2, 3) and B(5, 7)",
  "given": [
    "Point A has coordinates (2, 3)",
    "Point B has coordinates (5, 7)"
  ],
  "formula": [
    "Distance formula: d = sqrt((x2-x1)^2 + (y2-y1)^2)"
  ],
  "diagram": {
    "required": true,
    "description": "A coordinate system showing two points A(2, 3) and B(5, 7) with a line connecting them forming a right triangle.",
    "type": "distance",
    "data": {
      "p1": ["A", 2, 3],
      "p2": ["B", 5, 7]
    },
    "labels": [
      "Point A at (2, 3)",
      "Point B at (5, 7)",
      "Horizontal distance: 3 units",
      "Vertical distance: 4 units"
    ]
  },
  "steps": [
    "Step 1: We need to find the distance between A(2, 3) and B(5, 7). We use the distance formula: d = sqrt((x2-x1)^2 + (y2-y1)^2).",
    "Step 2: Substituting the coordinates into the formula: d = sqrt((5-2)^2 + (7-3)^2).",
    "Step 3: Simplifying inside the brackets: d = sqrt(3^2 + 4^2).",
    "Step 4: Calculating the squares: d = sqrt(9 + 16) = sqrt(25).",
    "Step 5: Taking the square root: d = 5 units."
  ],
  "answer": "The distance between points A(2, 3) and B(5, 7) is 5 units",
  "verification": "Using the Pythagorean theorem on the right triangle formed: horizontal distance = 3, vertical distance = 4, so hypotenuse = sqrt(3^2 + 4^2) = 5 ✓"
}

EXAMPLE OUTPUT (3D Geometry - Tent with Cylinder + Cone):

{
  "question": "A tent is in the shape of a cylinder surmounted by a conical top. If the height and diameter of the cylindrical part are 2.1 m and 4 m respectively, and the slant height of the top is 2.8 m, find the area of the canvas used for making the tent. Also, find the cost of the canvas of the tent at the rate of Rs. 500 per m2.",
  "given": [
    "Height of cylindrical part: 2.1 m",
    "Diameter of cylindrical part: 4 m, so radius = 2 m",
    "Slant height of conical part: 2.8 m"
  ],
  "formula": [
    "Lateral surface area of cylinder: A_cyl = 2πrh",
    "Lateral surface area of cone: A_cone = πrl",
    "Total canvas area: A_total = A_cyl + A_cone"
  ],
  "diagram": {
    "required": true,
    "description": "A 3D tent showing a cylinder (radius 2 m, height 2.1 m) with a cone on top (slant height 2.8 m). The cone is positioned on top of the cylinder forming a tent shape.",
    "type": "tent",
    "data": {
      "cylinder_radius": 2,
      "cylinder_height": 2.1,
      "cone_slant_height": 2.8
    },
    "labels": [
      "Height of cylinder: h = 2.1 m",
      "Radius: r = 2 m",
      "Slant height of cone: l = 2.8 m",
      "Cylindrical part (blue): covers the sides of cylinder",
      "Conical part (red): covers the slanted surface of cone"
    ]
  },
  "steps": [
    "Step 1: The canvas area consists of the lateral surface of the cylinder and the lateral surface of the cone (not the base).",
    "Step 2: Calculate the lateral surface area of the cylinder using A_cyl = 2πrh. Substituting r = 2 and h = 2.1: A_cyl = 2 × π × 2 × 2.1 = 2 × 3.14 × 2 × 2.1 = 26.38 m².",
    "Step 3: Calculate the lateral surface area of the cone using A_cone = πrl. Substituting r = 2 and l = 2.8: A_cone = π × 2 × 2.8 = 3.14 × 2 × 2.8 = 17.58 m².",
    "Step 4: The total canvas area is the sum: Total = 26.38 + 17.58 = 43.96 m².",
    "Step 5: The cost is calculated as: Cost = Area × Rate = 43.96 × 500 = Rs. 21,980"
  ],
  "answer": "The area of the canvas used is 43.96 m², and the cost is Rs. 21,980",
  "verification": "We can verify by checking each formula: Cylinder lateral area = 2πrh = 2 × 3.14 × 2 × 2.1 = 26.38, Cone lateral area = πrl = 3.14 × 2 × 2.8 = 17.58, Total = 43.96 m². Cost = 43.96 × 500 = 21,980 ✓"
}

EXAMPLE OUTPUT (Non-Geometry):

{
  "question": "Solve for x: 2x + 5 = 15",
  "given": [
    "Equation: 2x + 5 = 15"
  ],
  "formula": [
    "Algebraic principle: Isolate variable by inverse operations"
  ],
  "diagram": {
    "required": false,
    "description": "",
    "type": "",
    "data": {},
    "labels": []
  },
  "steps": [
    "Step 1: We have the equation 2x + 5 = 15. To find x, we need to isolate it on one side.",
    "Step 2: First, subtract 5 from both sides of the equation. This gives us 2x = 10.",
    "Step 3: Now divide both sides by 2 to isolate x. This gives us x = 5."
  ],
  "answer": "x = 5",
  "verification": "Substitute x = 5: 2(5) + 5 = 10 + 5 = 15 ✓"
}
"""


def generate_step_by_step_fallback(
    user_question: str,
    book_context: str,
    chat_context: str = "",
    diagram_description: str = ""
) -> str:
    """
    Generates a detailed, teacher-style solution in strict JSON format.
    PRIORITIZES book context - uses RD Sharma approach if available.
    """
    import json
    import logging

    logger = logging.getLogger(__name__)

    # Add geometry-specific instructions if needed
    geometry_instruction = build_geometry_prompt_instruction(user_question)

    # Build context presentation
    context_section = ""
    if book_context and book_context.strip():
        context_section = f"""MANDATORY BOOK CONTEXT (FROM RD SHARMA - YOU MUST USE THIS):
{book_context}

⚠️ CRITICAL: You MUST follow the exact method, formulas, and approach shown in the RD Sharma context above.
Do NOT use any other method or approach than what is shown in the context.
Your answer MUST follow the RD Sharma approach exactly."""
    else:
        context_section = "NOTE: No RD Sharma context available. Use your knowledge to solve accurately."

    prompt = f"""{SYSTEM}

{EXAMPLE}

{geometry_instruction}

═══════════════════════════════════════════════════
USER QUESTION TO SOLVE:
{user_question}
═══════════════════════════════════════════════════

{context_section}

{f'''
RECENT CHAT CONTEXT (for reference):
{chat_context}
''' if chat_context else ""}

{f'''
DIAGRAM HINT:
{diagram_description}
''' if diagram_description else ""}

═══════════════════════════════════════════════════
RESPOND NOW:
- Return ONLY JSON starting with {{ and ending with }}
- NO text or explanations outside the JSON
- Use the book context method if provided
- Show all steps with results
- Make it suitable for an exam answer
═══════════════════════════════════════════════════
"""

    try:
        response = requests.post(
            f"{LLM_URL.rstrip('/')}/api/generate",
            json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.4,  # Balanced: consistent but not too rigid
                "top_p": 0.85,
                "top_k": 30
            },
            timeout=300
        )

        response.raise_for_status()
        result = (response.json().get("response") or "").strip()

        # Validate JSON structure
        try:
            json.loads(result)
            return result
        except json.JSONDecodeError:
            logger.warning(f"LLM returned invalid JSON, attempting to fix...")
            # Try to extract JSON from response
            import re
            match = re.search(r'\{.*\}', result, re.DOTALL)
            if match:
                return match.group(0)
            logger.error(f"Could not extract valid JSON from LLM response")
            return result

    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        raise


def generate_methods_fallback(question: str) -> list:
    """
    Generate 2-3 CONCISE different solution methods for a question.
    Each method description is kept SHORT (1 sentence max).

    Returns:
        List of method descriptions (concise format)
    """
    import json
    import logging

    logger = logging.getLogger(__name__)

    try:
        # Build prompt for method generation - EMPHASIZE BREVITY
        prompt = f"""You are a mathematics teacher. For this question, list EXACTLY 2-3 DIFFERENT valid solution methods.

QUESTION: {question}

IMPORTANT: Each method must be described in ONE SHORT SENTENCE ONLY (max 12 words).
Format: "Method [N]: [Name] - [1 short sentence]"

Examples of correct format:
- "Method 1: Direct Formula - Apply the distance formula directly to coordinates"
- "Method 2: Pythagorean Theorem - Use coordinate differences as triangle sides"
- "Method 3: Vector Approach - Calculate magnitude of displacement vector"

Respond ONLY with valid JSON:
{{
  "methods": [
    "Method 1: [Name] - [SHORT description max 12 words]",
    "Method 2: [Name] - [SHORT description max 12 words]",
    "Method 3: [Name] - [SHORT description max 12 words]"
  ]
}}

Return ONLY the JSON object, nothing else."""

        response = requests.post(
            f"{LLM_URL.rstrip('/')}/api/generate",
            json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.2,
                "max_tokens": 300  # Limit tokens to force conciseness
            },
            timeout=120
        )

        response.raise_for_status()
        result = (response.json().get("response") or "").strip()

        # Try to parse JSON
        try:
            data = json.loads(result)
            methods = data.get("methods", [])
            if methods and len(methods) > 0:
                # Clean and truncate methods to ensure brevity
                methods = [m for m in methods if m and m.strip()]

                # Post-process: truncate any method longer than 120 chars
                methods = [
                    m[:120] + "..." if len(m) > 120 else m
                    for m in methods
                ]

                # Return up to 3 methods
                if methods:
                    return methods[:3]
        except:
            pass

        logger.info(
            f"[LLM Methods] Could not parse methods, using defaults for: {question[:50]}")

    except Exception as e:
        logger.error(f"[LLM Methods] Error: {str(e)}")

    # Fallback methods (concise format)
    return [
        "Method 1: Algebraic - Isolate variable using inverse operations",
        "Method 2: Substitution - Replace variables with known values",
        "Method 3: Graphical - Visualize problem geometrically to find solution"
    ]


# ═══════════════════════════════════════════════════════════════════
# PRODUCTION GEOMETRY SOLVER - LLM HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def extract_geometry_json(question: str) -> dict:
    """
    Extract structured geometry data from question.

    LLM ONLY parses structure - does NOT solve.
    Returns strict JSON with geometry components.

    CRITICAL: LLM must return parseable JSON only.

    Args:
        question: Geometry question text

    Returns:
        {
            "type": "triangle|circle|line|polygon|unknown",
            "entities": {
                "angles": [30, 60, 90],
                "lengths": {"base": 8, "height": 5},
                "points": [{"name": "A", "coords": [1, 2]}],
                "centers": [{"name": "O", "coords": [0, 0]}]
            },
            "requirements": ["perimeter", "area"],
            "constraints": ["right triangle"],
            "diagram_hint": "coordinate system",
            "verified": false
        }
    """

    import logging
    import re
    logger = logging.getLogger(__name__)

    GEOMETRY_EXTRACTION_PROMPT = """
You are a geometry parser. Your ONLY job is to EXTRACT structured geometry data from questions.

DO NOT SOLVE THE PROBLEM.
DO NOT CALCULATE ANYTHING.
ONLY PARSE AND STRUCTURE THE GEOMETRY INFORMATION.

CRITICAL: Be consistent. For the same inputs, always extract the SAME values.

Rules:
1. Type: triangle, circle, line, polygon, or unknown
2. Entities: Extract ALL numbers exactly as they appear
3. Requirements: What to find (area, perimeter, distance, etc)
4. Constraints: Properties (right triangle, isosceles, etc)
5. Diagram hint: coordinate system, simple shape, 3D, etc

Return ONLY valid JSON. No other text.

Example 1 - Simple Triangle:
Q: "Find the perimeter of a triangle with sides 3, 4, 5 cm."
{
  "type": "triangle",
  "entities": {
    "lengths": {"side1": 3, "side2": 4, "side3": 5}
  },
  "requirements": ["perimeter"],
  "constraints": ["right triangle"],
  "diagram_hint": "simple shape"
}

Example 2 - Coordinate Geometry:
Q: "Find the distance between points A(2, 3) and B(5, 7)."
{
  "type": "line",
  "entities": {
    "points": [
      {"name": "A", "coords": [2, 3]},
      {"name": "B", "coords": [5, 7]}
    ]
  },
  "requirements": ["distance"],
  "constraints": [],
  "diagram_hint": "coordinate system"
}

Now extract geometry data. Be exact and consistent:
Q: {question}
""".strip()

    try:
        # Use temperature 0 for maximum consistency (fully deterministic)
        response = requests.post(
            f"{LLM_URL.rstrip('/')}/api/generate",
            json={
                "model": LLM_MODEL,
                "prompt": GEOMETRY_EXTRACTION_PROMPT,
                "stream": False,
                "temperature": 0.0  # CHANGED: 0 = fully deterministic
            },
            timeout=120
        )

        response.raise_for_status()
        result = (response.json().get("response") or "").strip()

        logger.debug(f"[GeometryExtractor] LLM raw response: {result[:200]}")

        # Extract JSON from response - improved regex
        json_match = re.search(
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', result, re.DOTALL)

        if json_match:
            json_text = json_match.group(0)
            data = json.loads(json_text)

            # Validate and set defaults
            data.setdefault("type", "unknown")
            data.setdefault("entities", {})
            data.setdefault("requirements", [])
            data.setdefault("constraints", [])
            data.setdefault("diagram_hint", "unknown")
            data["verified"] = False

            # Normalize extracted data for consistency
            _normalize_extraction(data)

            logger.info(
                f"[GeometryExtractor] ✓ Extracted type: {data['type']} (temp=0.0)")
            return data
        else:
            logger.warning(
                f"[GeometryExtractor] Could not find JSON in response: {result[:100]}")

    except json.JSONDecodeError as e:
        logger.error(f"[GeometryExtractor] Invalid JSON from LLM: {e}")
    except Exception as e:
        logger.error(f"[GeometryExtractor] Error: {e}")

    # Safe fallback
    logger.warning("[GeometryExtractor] Using safe fallback")
    return {
        "type": "unknown",
        "entities": {},
        "requirements": [],
        "constraints": [],
        "diagram_hint": "unknown",
        "verified": False
    }


def _normalize_extraction(data: dict) -> None:
    """
    Normalize extracted geometry data for consistency.
    Ensures same values are used on repeated extractions.
    """
    import logging
    logger = logging.getLogger(__name__)

    # Ensure points are sorted consistently
    if "entities" in data and "points" in data["entities"]:
        points = data["entities"]["points"]
        if isinstance(points, list):
            # Sort by name for consistency
            try:
                points.sort(key=lambda p: p.get("name", ""))
                logger.debug("[Normalize] Sorted points by name")
            except:
                pass

    # Normalize requirements list
    if "requirements" in data and isinstance(data["requirements"], list):
        data["requirements"] = sorted(list(set(data["requirements"])))

    # Normalize constraints list
    if "constraints" in data and isinstance(data["constraints"], list):
        data["constraints"] = sorted(list(set(data["constraints"])))


def generate_explanation(solution_data: str, question: str) -> str:
    """
    Generate CBSE-style explanation for verified geometry solution.

    CRITICAL CONSTRAINTS:
    - Input: solution_data (JSON string with numbers)
    - Output: Explanation that does NOT change those numbers
    - If LLM changes numbers → will be detected and rejected

    Args:
        solution_data: JSON string of solution from solver
        question: Original question

    Returns:
        CBSE-formatted explanation text
    """

    import logging
    logger = logging.getLogger(__name__)

    EXPLANATION_PROMPT = f"""
You are a CBSE mathematics tutor. Your job is to EXPLAIN a verified geometry solution.

RULES (CRITICAL):
1. DO NOT CHANGE THE NUMBERS - they are verified by symbolic solver
2. EXPLAIN WHY each formula is used and HOW it's applied
3. Write for 14-16 year old students
4. Use teacher-like language: "We have...", "Therefore...", "Hence..."
5. Make it suitable for exam answers
6. Include verification step at the end

VERIFIED SOLUTION (DO NOT CHANGE NUMBERS):
{solution_data}

ORIGINAL QUESTION:
{question}

Now write a clear CBSE-style explanation. Make sure all numbers from the solution appear unchanged in your explanation.
""".strip()

    try:
        import logging
        logger = logging.getLogger(__name__)

        response = requests.post(
            f"{LLM_URL.rstrip('/')}/api/generate",
            json={
                "model": LLM_MODEL,
                "prompt": EXPLANATION_PROMPT,
                "stream": False,
                "temperature": 0.3  # Low for consistency
            },
            timeout=120
        )

        response.raise_for_status()
        explanation = (response.json().get("response") or "").strip()

        logger.info("[ExplanationGenerator] ✓ Generated explanation")
        return explanation

    except Exception as e:
        logger.error(f"[ExplanationGenerator] Error: {e}")
        return ""
