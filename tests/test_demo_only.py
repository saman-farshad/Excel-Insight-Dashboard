"""Safety regression tests for the public demo-only app."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_no_public_upload_logic():
    source = (ROOT / 'app.py').read_text(encoding='utf-8')
    assert 'file_uploader(' not in source
    assert 'st.sidebar.file_uploader' not in source
    assert 'uploaded.getvalue' not in source
    assert 'upload an Excel' not in source.lower()
    assert 'DATASETS = {' in source


def test_bundled_demo_data_are_tabular():
    for name in ('sample_sales.xlsx', 'sample_factory.xlsx', 'sample_website.xlsx'):
        path = ROOT / 'sample_data' / name
        assert path.is_file()
        data = pd.read_excel(path, engine='openpyxl')
        assert len(data) > 20
        assert data.select_dtypes(include='number').shape[1] >= 2
        assert not any(s in col.lower() for col in data.columns for s in ('email', 'phone', 'address'))
