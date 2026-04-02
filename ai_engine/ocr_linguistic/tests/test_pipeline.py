import os
from ai_engine.ocr_linguistic.pipeline import run_pipeline

_SAMPLE = os.path.join(os.path.dirname(__file__), "sample_images", "vaseline.jpg")

def test_pipeline_runs():

    result = run_pipeline(_SAMPLE)

    assert "final_text_anomaly_score" in result