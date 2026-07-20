"""Built-in verification functions bundled with label_pizza.

This file ships inside the package so that the verification functions
referenced by shared question groups (e.g. the "Label Issues" group ->
`check_taxonomy_labeling`) are ALWAYS available after a plain
`git pull` + restart, regardless of the machine's `verification_config.json`
or the current working directory. The registry loads this folder via a
`__file__`-relative path (see verification_registry.auto_load_workspaces),
so it does not depend on cwd or on per-machine workspace folders existing.

Workspace copies of these functions (output/<workspace>/verify.py) may still
be registered from verification_config.json; identical duplicates are handled
gracefully by the registry (first-registered wins, no abort).
"""

from typing import Dict


# -----------------------------
GENERAL_DESC = "Does the sample violate any of Grice's Maxims?"
RELATION_DESC = "Relation: Does the sample contain irrelevant information?"
MANNER_DESC = "Manner: Does the sample contain information that cannot be uniquely mapped to a single referent?"
QUALITY_DESC = "Quality: Does the sample contain an incorrect ground-truth answer?"
QUANTITY_DESC = "Quantity: What is the minimal evidence sufficient to answer the question?"
BIAS = ["All sources", "Text only", "Audio only", "Single frame"]
# -----------------------------

def check_single_issue_type(answers: Dict[str, str]) -> None:
    """Validate consistency between GENERAL_DESC and sub-category selections.

    If GENERAL_DESC is No, none of the sub-categories should be selected.
    If GENERAL_DESC is Yes, exactly one of the following must hold:
    - RELATION_DESC is Yes
    - MANNER_DESC is Yes
    - QUALITY_DESC is Yes
    - QUANTITY_DESC is not "All sources"

    Args:
        answers: Dictionary mapping question text to answer value

    Raises:
        ValueError: If sub-categories are inconsistent with GENERAL_DESC.
    """
    conditions = [
        answers.get(RELATION_DESC) == "Yes",
        answers.get(MANNER_DESC) == "Yes",
        answers.get(QUALITY_DESC) == "Yes",
        answers.get(QUANTITY_DESC) != "All sources",
    ]
    count = sum(conditions)

    if answers.get(GENERAL_DESC) != "Yes":
        if count > 0:
            raise ValueError(
                "If there is no issue, all sub-categories must remain at their defaults "
                "(Relation/Manner/Quality must be No, Quantity must be 'All sources')"
            )
        return

    if count == 0:
        raise ValueError(
            "If there is an issue, you must specify exactly one type: "
            "Relation, Manner, Quality, or Quantity (not 'All sources')"
        )

    if count > 1:
        raise ValueError(
            "Only one issue type should be selected. "
            "Please choose the highest priority issue."
        )

def check_modification_provided(answers: Dict[str, str]) -> None:
    """Ensure that if there's an issue, at least one modification/rewrite is provided.

    Args:
        answers: Dictionary mapping question text to answer value

    Raises:
        ValueError: If an issue is reported but no modifications are provided.
    """
    has_issue = answers.get("Is there any issue?")

    if has_issue == "Yes":
        # Check if at least one modification field is filled
        modification_fields = [
            "A better description for Question.",
            "A better description for Option A.",
            "A better description for Option B.",
            "A better description for Option C.",
            "A better description for Option D.",
            "A better description for Option E.",
            "A better description for Option F."
        ]

        has_modification = any(
            answers.get(field) and answers.get(field).strip()
            for field in modification_fields
        )

        if not has_modification:
            raise ValueError(
                "If there is an issue, you must provide at least one modification "
                "(rewrite box cannot be empty)"
            )

def check_taxonomy_labeling(answers: Dict[str, str]) -> None:
    """Main verification function that runs all taxonomy checks.

    Args:
        answers: Dictionary mapping question text to answer value

    Raises:
        ValueError: If any validation check fails.
    """
    check_single_issue_type(answers)
    check_modification_provided(answers)
