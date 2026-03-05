 
SabiLens: A Multimodal AI Ecosystem for National Product Integrity
We are creating a verified multi-angle reference dataset using authentic manufacturer-sourced products. Each product is stored as a six-view embedding profile, and we compare incoming scans against that ground-truth baseline using similarity scoring and anomaly thresholds.

What reports the fake?
Our multi-signal fusion engine automatically generates a structured evidence file when authenticity confidence drops below threshold, which is then logged to the regulatory dashboard and optionally escalated with user consent.

Below is a clear end-to-end architecture breakdown + 7-Day execution table, explicitly split between:
•	AI Engineers (A1–A8) → Models, pipelines, intelligence, geo-analytics
•	Developers (D1–D8) → Mobile app, backend, APIs, database, dashboards, DevOps

Day 7 Must Show
During demo:
1.	Scan authentic worn product → Authentic (High Confidence)
2.	Scan counterfeit with typo → Suspicious / Fake
3.	Show purchase channel selection
4.	Dashboard shows geo cluster
5.	Voice says, “Do not buy this product.”
