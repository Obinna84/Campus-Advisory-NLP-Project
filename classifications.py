from __future__ import annotations

import pandas as pd

from campus_safety.data import enrich_dataframe, load_default_data
from campus_safety.nlp import DEFAULT_CLASSIFIER


def evaluate_sample_dataset() -> pd.DataFrame:
    raw_df = load_default_data().copy()
    raw_df["provided_category"] = raw_df.get("category", "")
    enriched_df = enrich_dataframe(raw_df)
    comparison = pd.DataFrame(
        {
            "description": enriched_df["description"],
            "provided_category": raw_df["provided_category"],
            "predicted_type": enriched_df["incident_type"],
            "predicted_family": enriched_df["incident_family"],
            "model_confidence": enriched_df["model_confidence"],
            "classification_source": enriched_df["classification_source"],
        }
    )
    comparison["correct_type"] = comparison["provided_category"].fillna("") == comparison["predicted_type"].fillna("")
    accuracy = float(comparison["correct_type"].mean()) if not comparison.empty else 0.0
    print(f"Rows evaluated: {len(comparison)}")
    print(f"Type accuracy against provided labels: {accuracy:.2%}")
    print("\nPredicted incident family counts:")
    print(comparison["predicted_family"].value_counts())
    print("\nExample predictions:")
    print(comparison[["provided_category", "predicted_type", "model_confidence", "classification_source"]].head(5).to_string(index=False))
    return comparison


def demo_predictions() -> None:
    samples = [
        "The Metropolitan Police Department is investigating a shooting near the 2200 Block of Georgia Avenue NW.",
        "A suspicious person was observed loitering near Blackburn University Center.",
        "A carjacking was reported near Howard University Hospital.",
    ]
    for sample in samples:
        label, confidence, source = DEFAULT_CLASSIFIER.predict_incident_type_from_keywords_or_model(sample)
        print(f"{sample}\n -> {label} | confidence={confidence:.2f} | source={source}\n")


if __name__ == "__main__":
    evaluate_sample_dataset()
    print("\n--- Demo predictions ---")
    demo_predictions()
