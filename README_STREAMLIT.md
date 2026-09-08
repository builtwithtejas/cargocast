# CargoCast — Streamlit Cloud deployment

This package preserves the original CargoCast frontend design from `frontend/` by rendering it as a Streamlit custom component.

## Streamlit Cloud settings
- Repository: this GitHub repository
- Branch: `main`
- Main file path: `app.py`

## Important
The `.python-version` file pins Python to 3.11. The requirements intentionally use pandas 2.2.3 because Streamlit 1.40.0 requires pandas < 3.
